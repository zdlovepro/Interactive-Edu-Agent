package com.interactive.edu.service.qa;

import com.interactive.edu.service.courseware.CoursewareService;
import com.interactive.edu.service.courseware.CoursewareService.QaIngestPage;
import com.interactive.edu.service.lecture.LectureService;
import com.interactive.edu.service.python.PythonQaClient;
import com.interactive.edu.service.python.PythonQaIngestClient;
import com.interactive.edu.service.python.PythonQaIngestRequest;
import com.interactive.edu.service.python.PythonQaRequest;
import com.interactive.edu.service.python.PythonQaResponse;
import com.interactive.edu.service.record.LectureRecordService;
import com.interactive.edu.vo.courseware.ScriptSegmentView;
import com.interactive.edu.vo.qa.EvidenceItemView;
import com.interactive.edu.vo.qa.QaAnswerView;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;
import org.springframework.web.servlet.mvc.method.annotation.StreamingResponseBody;

import java.io.IOException;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ConcurrentMap;

@Service
@RequiredArgsConstructor
@Slf4j
public class QaService {

    private static final String STREAM_FALLBACK_MESSAGE = "当前问答服务暂时不可用，请稍后重试。";
    private static final int DEFAULT_TOP_K = 5;
    private static final int MAX_TOP_K = 10;
    private static final byte[] STREAM_FALLBACK_BYTES = (
            "data: {\"type\":\"error\",\"message\":\"" + STREAM_FALLBACK_MESSAGE + "\"}\n\n"
                    + "data: {\"type\":\"done\"}\n\n"
    ).getBytes(StandardCharsets.UTF_8);

    private final LectureService lectureService;
    private final CoursewareService coursewareService;
    private final PythonQaClient pythonQaClient;
    private final PythonQaIngestClient pythonQaIngestClient;
    private final LectureRecordService lectureRecordService;

    private final ConcurrentMap<String, String> indexedCoursewareSignatures = new ConcurrentHashMap<>();

    public QaAnswerView askText(String sessionId, String question) {
        return askText(sessionId, question, null);
    }

    public QaAnswerView askText(String sessionId, String question, Integer pageIndex) {
        String resolvedQuestion = validateQuestion(question);
        long startAt = System.currentTimeMillis();

        LectureService.SessionSnapshot session = lectureService.getSessionSnapshot(sessionId);
        int resolvedPageIndex = resolveRequestedPageIndex(session, pageIndex);
        syncSessionPageIfNeeded(session, resolvedPageIndex);

        ensureCoursewareIndexed(session.coursewareId());
        PythonQaRequest request = buildPythonQaRequest(session, resolvedQuestion, resolvedPageIndex, DEFAULT_TOP_K);
        PythonQaResponse pythonQaResponse = askPythonFirst(request);
        if (pythonQaResponse != null && pythonQaResponse.safeEvidence().isEmpty()) {
            rebuildCoursewareIndex(session.coursewareId());
            pythonQaResponse = askPythonFirst(request);
        }

        if (pythonQaResponse != null && StringUtils.hasText(pythonQaResponse.answer())) {
            long latencyMs = resolveLatencyMs(startAt, pythonQaResponse.latencyMs());
            QaAnswerView answerView = new QaAnswerView(
                    pythonQaResponse.answer(),
                    pythonQaResponse.safeEvidence().stream()
                            .map(this::toEvidenceItemView)
                            .toList(),
                    latencyMs
            );
            recordQaSafely(session, resolvedQuestion, resolvedPageIndex, answerView);
            log.info(
                    "QA answered by Python RAG. sessionId={}, coursewareId={}, pageIndex={}, latencyMs={}",
                    sessionId,
                    session.coursewareId(),
                    resolvedPageIndex,
                    latencyMs
            );
            return answerView;
        }

        List<ScriptSegmentView> segments = coursewareService.getScriptSegments(session.coursewareId());
        ScriptSegmentView current = coursewareService.getSegmentForPage(session.coursewareId(), resolvedPageIndex);
        ScriptSegmentView target = selectTargetSegment(segments, current, resolvedQuestion);

        String answer = buildAnswer(target);
        List<EvidenceItemView> evidence = buildEvidence(current, target);
        long latencyMs = Math.max(1, System.currentTimeMillis() - startAt);
        QaAnswerView answerView = new QaAnswerView(answer, evidence, latencyMs);
        recordQaSafely(session, resolvedQuestion, resolvedPageIndex, answerView);
        log.info(
                "QA answered by local fallback. sessionId={}, coursewareId={}, pageIndex={}, latencyMs={}",
                sessionId,
                session.coursewareId(),
                resolvedPageIndex,
                latencyMs
        );
        return answerView;
    }

    public StreamingResponseBody streamText(String sessionId, String question, Integer topK) {
        return streamText(sessionId, question, null, topK);
    }

    public StreamingResponseBody streamText(String sessionId, String question, Integer pageIndex, Integer topK) {
        String resolvedQuestion = validateQuestion(question);
        int resolvedTopK = resolveTopK(topK);
        LectureService.SessionSnapshot session = lectureService.getSessionSnapshot(sessionId);
        int resolvedPageIndex = resolveRequestedPageIndex(session, pageIndex);
        syncSessionPageIfNeeded(session, resolvedPageIndex);
        ensureCoursewareIndexed(session.coursewareId());

        PythonQaRequest request = buildPythonQaRequest(session, resolvedQuestion, resolvedPageIndex, resolvedTopK);
        return outputStream -> streamWithPythonFallback(session, request, resolvedPageIndex, outputStream);
    }

    private PythonQaResponse askPythonFirst(PythonQaRequest request) {
        try {
            return pythonQaClient.askText(request);
        } catch (Exception ex) {
            log.warn(
                    "Python QA unavailable, fallback to local template. sessionId={}, coursewareId={}, pageIndex={}, reason={}",
                    request.getSessionId(),
                    request.getCoursewareId(),
                    request.getPageIndex(),
                    ex.getMessage()
            );
            return null;
        }
    }

    private void streamWithPythonFallback(
            LectureService.SessionSnapshot session,
            PythonQaRequest request,
            int resolvedPageIndex,
            OutputStream outputStream
    ) throws IOException {
        try {
            pythonQaClient.streamText(request, outputStream);
            log.info(
                    "QA stream proxied from Python. sessionId={}, coursewareId={}, pageIndex={}, topK={}",
                    session.sessionId(),
                    session.coursewareId(),
                    resolvedPageIndex,
                    request.getTopK()
            );
            return;
        } catch (Exception ex) {
            log.warn(
                    "Python QA stream failed on first attempt. sessionId={}, coursewareId={}, pageIndex={}, reason={}",
                    session.sessionId(),
                    session.coursewareId(),
                    resolvedPageIndex,
                    ex.getMessage()
            );
        }

        rebuildCoursewareIndex(session.coursewareId());
        try {
            pythonQaClient.streamText(request, outputStream);
            log.info(
                    "QA stream recovered after courseware reindex. sessionId={}, coursewareId={}, pageIndex={}, topK={}",
                    session.sessionId(),
                    session.coursewareId(),
                    resolvedPageIndex,
                    request.getTopK()
            );
        } catch (Exception ex) {
            log.warn(
                    "Python QA stream unavailable, fallback to static SSE. sessionId={}, coursewareId={}, pageIndex={}, reason={}",
                    session.sessionId(),
                    session.coursewareId(),
                    resolvedPageIndex,
                    ex.getMessage()
            );
            outputStream.write(STREAM_FALLBACK_BYTES);
            outputStream.flush();
        }
    }

    private void ensureCoursewareIndexed(String coursewareId) {
        List<QaIngestPage> pages = coursewareService.getQaIngestPages(coursewareId);
        String signature = buildQaIndexSignature(coursewareId, pages);
        if (signature.equals(indexedCoursewareSignatures.get(coursewareId))) {
            return;
        }
        rebuildCoursewareIndex(coursewareId, pages, signature);
    }

    private void rebuildCoursewareIndex(String coursewareId) {
        List<QaIngestPage> pages = coursewareService.getQaIngestPages(coursewareId);
        rebuildCoursewareIndex(coursewareId, pages, buildQaIndexSignature(coursewareId, pages));
    }

    private void rebuildCoursewareIndex(String coursewareId, List<QaIngestPage> pages, String signature) {
        try {
            if (pages.isEmpty()) {
                indexedCoursewareSignatures.remove(coursewareId);
                log.warn("Skip QA ingest because no page context is available. coursewareId={}", coursewareId);
                return;
            }

            List<PythonQaIngestRequest.PagePayload> pagePayloads = pages.stream()
                    .map(page -> new PythonQaIngestRequest.PagePayload(
                            page.pageIndex(),
                            page.title(),
                            page.content(),
                            page.knowledgePoints(),
                            page.pageImagePath(),
                            page.visualSummary(),
                            page.visualObjects()
                    ))
                    .toList();

            pythonQaIngestClient.ingestPages(new PythonQaIngestRequest(
                    coursewareId,
                    pagePayloads,
                    500,
                    80,
                    Boolean.TRUE
            ));
            indexedCoursewareSignatures.put(coursewareId, signature);
            log.info("QA ingest completed. coursewareId={}, pageCount={}", coursewareId, pagePayloads.size());
        } catch (Exception ex) {
            indexedCoursewareSignatures.remove(coursewareId);
            log.warn("QA ingest failed. coursewareId={}, reason={}", coursewareId, ex.getMessage());
        }
    }

    private PythonQaRequest buildPythonQaRequest(
            LectureService.SessionSnapshot session,
            String question,
            int pageIndex,
            int topK
    ) {
        QaIngestPage currentPage = coursewareService.getQaPageForPage(session.coursewareId(), pageIndex);
        List<PythonQaRequest.CoursewarePagePayload> coursewarePages = coursewareService.getQaIngestPages(session.coursewareId())
                .stream()
                .map(page -> new PythonQaRequest.CoursewarePagePayload(
                        page.pageIndex(),
                        page.title(),
                        page.content(),
                        page.knowledgePoints(),
                        page.visualSummary(),
                        page.visualObjects()
                ))
                .toList();
        return new PythonQaRequest(
                session.sessionId(),
                session.coursewareId(),
                pageIndex,
                question,
                topK,
                currentPage == null ? null : currentPage.title(),
                currentPage == null ? null : currentPage.content(),
                currentPage == null ? null : currentPage.pageImagePath(),
                currentPage == null ? null : currentPage.visualSummary(),
                currentPage == null ? List.of() : currentPage.knowledgePoints(),
                currentPage == null ? List.of() : currentPage.visualObjects(),
                coursewarePages
        );
    }

    private void syncSessionPageIfNeeded(LectureService.SessionSnapshot session, int resolvedPageIndex) {
        if (resolvedPageIndex == session.currentPageIndex()) {
            return;
        }

        try {
            lectureService.updateBreakpoint(session.sessionId(), resolvedPageIndex, null);
        } catch (Exception ex) {
            log.warn(
                    "Failed to sync QA page index into lecture session. sessionId={}, pageIndex={}, reason={}",
                    session.sessionId(),
                    resolvedPageIndex,
                    ex.getMessage()
            );
        }
    }

    private void recordQaSafely(
            LectureService.SessionSnapshot session,
            String question,
            int pageIndex,
            QaAnswerView answerView
    ) {
        try {
            lectureRecordService.createQaRecord(
                    session.sessionId(),
                    session.coursewareId(),
                    pageIndex,
                    question,
                    answerView.answer(),
                    answerView.evidence(),
                    answerView.latencyMs()
            );
        } catch (Exception ex) {
            log.warn(
                    "Failed to persist QA record. sessionId={}, coursewareId={}, pageIndex={}, reason={}",
                    session.sessionId(),
                    session.coursewareId(),
                    pageIndex,
                    ex.getMessage()
            );
        }
    }

    private ScriptSegmentView selectTargetSegment(
            List<ScriptSegmentView> segments,
            ScriptSegmentView current,
            String question
    ) {
        if (segments == null || segments.isEmpty()) {
            return current;
        }

        for (ScriptSegmentView segment : segments) {
            if (segment == null) {
                continue;
            }
            if (StringUtils.hasText(segment.title()) && question.contains(segment.title())) {
                return segment;
            }

            List<String> knowledgePoints = segment.knowledgePoints() == null ? List.of() : segment.knowledgePoints();
            for (String knowledgePoint : knowledgePoints) {
                if (StringUtils.hasText(knowledgePoint) && question.contains(knowledgePoint)) {
                    return segment;
                }
            }
        }

        return current;
    }

    private String buildAnswer(ScriptSegmentView target) {
        if (target == null) {
            return STREAM_FALLBACK_MESSAGE;
        }

        StringBuilder builder = new StringBuilder();
        builder.append("结合当前课件内容，可以先这样回答：");
        builder.append(target.content());

        List<String> knowledgePoints = target.knowledgePoints() == null ? List.of() : target.knowledgePoints();
        if (!knowledgePoints.isEmpty()) {
            builder.append(" 建议重点关注：")
                    .append(String.join("、", knowledgePoints))
                    .append("。");
        }

        return builder.toString();
    }

    private List<EvidenceItemView> buildEvidence(ScriptSegmentView current, ScriptSegmentView target) {
        List<EvidenceItemView> evidence = new ArrayList<>();
        if (target != null) {
            evidence.add(new EvidenceItemView(
                    "page_" + target.pageIndex(),
                    summarize(target.content()),
                    target.pageIndex(),
                    target.nodeId()
            ));
        }

        if (current != null && target != null && !target.id().equals(current.id())) {
            evidence.add(new EvidenceItemView(
                    "page_" + current.pageIndex(),
                    summarize(current.content()),
                    current.pageIndex(),
                    current.nodeId()
            ));
        }

        return evidence;
    }

    private EvidenceItemView toEvidenceItemView(PythonQaResponse.EvidencePayload evidencePayload) {
        return new EvidenceItemView(
                evidencePayload.source(),
                evidencePayload.text(),
                evidencePayload.pageIndex(),
                evidencePayload.chunkId()
        );
    }

    private String summarize(String text) {
        if (!StringUtils.hasText(text)) {
            return "";
        }
        return text.length() <= 120 ? text : text.substring(0, 120) + "...";
    }

    private long resolveLatencyMs(long startAt, long pythonLatencyMs) {
        long measuredLatency = Math.max(1, System.currentTimeMillis() - startAt);
        return pythonLatencyMs > 0 ? pythonLatencyMs : measuredLatency;
    }

    private int resolveRequestedPageIndex(LectureService.SessionSnapshot session, Integer pageIndex) {
        if (pageIndex == null) {
            return session.currentPageIndex();
        }
        if (pageIndex <= 0) {
            throw new IllegalArgumentException("pageIndex must be positive");
        }
        return pageIndex;
    }

    private int resolveTopK(Integer topK) {
        if (topK == null) {
            return DEFAULT_TOP_K;
        }
        return Math.min(MAX_TOP_K, Math.max(1, topK));
    }

    private String validateQuestion(String question) {
        String resolvedQuestion = StringUtils.hasText(question) ? question.trim() : "";
        if (!StringUtils.hasText(resolvedQuestion)) {
            throw new IllegalArgumentException("question must not be blank");
        }
        return resolvedQuestion;
    }

    private String buildQaIndexSignature(String coursewareId, List<QaIngestPage> pages) {
        if (pages == null || pages.isEmpty()) {
            return coursewareId + ":empty";
        }

        StringBuilder builder = new StringBuilder(coursewareId).append('|').append(pages.size());
        for (QaIngestPage page : pages) {
            builder.append('|')
                    .append(page.pageIndex())
                    .append('|')
                    .append(normalizeSignatureText(page.title()))
                    .append('|')
                    .append(normalizeSignatureText(page.content()))
                    .append('|')
                    .append(normalizeSignatureText(page.visualSummary()))
                    .append('|')
                    .append(String.join(",", page.knowledgePoints() == null ? List.of() : page.knowledgePoints()))
                    .append('|')
                    .append(String.join(",", page.visualObjects() == null ? List.of() : page.visualObjects()));
        }

        try {
            byte[] digest = MessageDigest.getInstance("SHA-256")
                    .digest(builder.toString().getBytes(StandardCharsets.UTF_8));
            return bytesToHex(digest);
        } catch (NoSuchAlgorithmException ex) {
            return Integer.toHexString(builder.toString().hashCode()).toLowerCase(Locale.ROOT);
        }
    }

    private String normalizeSignatureText(String value) {
        return StringUtils.hasText(value) ? value.trim() : "";
    }

    private String bytesToHex(byte[] bytes) {
        StringBuilder hex = new StringBuilder(bytes.length * 2);
        for (byte value : bytes) {
            hex.append(Character.forDigit((value >> 4) & 0xF, 16));
            hex.append(Character.forDigit(value & 0xF, 16));
        }
        return hex.toString();
    }
}
