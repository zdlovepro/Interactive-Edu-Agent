package com.interactive.edu.service.record;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.interactive.edu.entity.LectureInterruptRecord;
import com.interactive.edu.entity.LectureSession;
import com.interactive.edu.entity.QaRecord;
import com.interactive.edu.exception.BusinessException;
import com.interactive.edu.exception.ErrorCode;
import com.interactive.edu.repository.LectureInterruptRecordRepository;
import com.interactive.edu.repository.LectureSessionRepository;
import com.interactive.edu.repository.QaRecordRepository;
import com.interactive.edu.service.courseware.CoursewareService;
import com.interactive.edu.vo.qa.EvidenceItemView;
import com.interactive.edu.vo.record.InterruptRecordView;
import com.interactive.edu.vo.record.QaRecordView;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.time.Instant;
import java.time.LocalDateTime;
import java.time.ZoneId;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ConcurrentMap;

@Service
@Slf4j
public class LectureRecordService {

    private static final String INTERRUPTED = "INTERRUPTED";
    private static final String ANSWERED = "ANSWERED";
    private static final String RESUMED = "RESUMED";
    private static final TypeReference<List<EvidenceItemView>> EVIDENCE_TYPE = new TypeReference<>() {
    };

    private final ObjectMapper objectMapper;
    private final Path recordBaseDir;
    private final ObjectProvider<LectureInterruptRecordRepository> interruptRepositoryProvider;
    private final ObjectProvider<QaRecordRepository> qaRecordRepositoryProvider;
    private final ObjectProvider<LectureSessionRepository> lectureSessionRepositoryProvider;
    private final ObjectProvider<CoursewareService> coursewareServiceProvider;
    private final ConcurrentMap<String, SessionRecordState> recordStore = new ConcurrentHashMap<>();

    @Autowired
    public LectureRecordService(
            ObjectMapper objectMapper,
            @Value("${record.local-base-dir:./data/records}") String recordBaseDir,
            ObjectProvider<LectureInterruptRecordRepository> interruptRepositoryProvider,
            ObjectProvider<QaRecordRepository> qaRecordRepositoryProvider,
            ObjectProvider<LectureSessionRepository> lectureSessionRepositoryProvider,
            ObjectProvider<CoursewareService> coursewareServiceProvider
    ) {
        this.objectMapper = objectMapper;
        this.recordBaseDir = Path.of(recordBaseDir);
        this.interruptRepositoryProvider = interruptRepositoryProvider;
        this.qaRecordRepositoryProvider = qaRecordRepositoryProvider;
        this.lectureSessionRepositoryProvider = lectureSessionRepositoryProvider;
        this.coursewareServiceProvider = coursewareServiceProvider;
    }

    public InterruptRecordView createInterruptRecord(
            String sessionId,
            String coursewareId,
            Integer pageIndex,
            Double currentTime
    ) {
        validateSessionId(sessionId);
        validateCoursewareId(coursewareId);
        ensureSessionExists(sessionId.trim());

        Instant now = Instant.now();
        InterruptRecordView record = new InterruptRecordView(
                "intr_" + UUID.randomUUID().toString().replace("-", ""),
                sessionId.trim(),
                coursewareId.trim(),
                pageIndex,
                currentTime,
                null,
                INTERRUPTED,
                now,
                now
        );

        syncInterrupt(record);
        if (isPersistentMode()) {
            LectureInterruptRecord entity = new LectureInterruptRecord();
            entity.setId(record.interruptId());
            entity.setSessionId(record.sessionId());
            entity.setCoursewareId(record.coursewareId());
            entity.setPageIndex(record.pageIndex());
            entity.setCurrentTime(record.currentTime());
            entity.setAsrText(record.asrText());
            entity.setStatus(record.status());
            interruptRepository().save(entity);
        }
        persistSafely(record.sessionId(), "interrupt", record);
        return record;
    }

    public InterruptRecordView updateLatestInterruptAsrText(String sessionId, String asrText) {
        validateSessionId(sessionId);
        if (!StringUtils.hasText(asrText)) {
            if (isPersistentMode()) {
                return toInterruptView(requireLatestInterruptEntity(sessionId.trim()));
            }
            return requireLatestInterrupt(stateForExistingSession(sessionId));
        }

        InterruptRecordView updated;
        if (isPersistentMode()) {
            LectureInterruptRecord entity = requireLatestInterruptEntity(sessionId.trim());
            entity.setAsrText(asrText.trim());
            interruptRepository().save(entity);
            updated = toInterruptView(entity);
        } else {
            SessionRecordState state = stateForExistingSession(sessionId);
            synchronized (state) {
                InterruptRecordView latest = requireLatestInterrupt(state);
                updated = new InterruptRecordView(
                        latest.interruptId(),
                        latest.sessionId(),
                        latest.coursewareId(),
                        latest.pageIndex(),
                        latest.currentTime(),
                        asrText.trim(),
                        latest.status(),
                        latest.createdAt(),
                        Instant.now()
                );
            }
        }

        syncInterrupt(updated);
        persistSafely(updated.sessionId(), "interrupt", updated);
        return updated;
    }

    public InterruptRecordView markLatestInterruptAnswered(String sessionId) {
        return updateLatestInterruptStatus(sessionId, ANSWERED);
    }

    public InterruptRecordView markLatestInterruptResumed(String sessionId) {
        return updateLatestInterruptStatus(sessionId, RESUMED);
    }

    public QaRecordView createQaRecord(
            String sessionId,
            String coursewareId,
            Integer pageIndex,
            String question,
            String answer,
            List<EvidenceItemView> evidence,
            long latencyMs
    ) {
        validateSessionId(sessionId);
        validateCoursewareId(coursewareId);
        ensureSessionExists(sessionId.trim());
        if (!StringUtils.hasText(question)) {
            throw new BusinessException(ErrorCode.PARAM_ERROR, "question must not be blank");
        }
        if (!StringUtils.hasText(answer)) {
            throw new BusinessException(ErrorCode.BUSINESS_VALIDATION_FAILED, "answer must not be blank");
        }

        List<EvidenceItemView> copiedEvidence = copyEvidence(evidence);
        QaRecordView record;
        if (isPersistentMode()) {
            QaRecord entity = new QaRecord();
            entity.setSessionId(sessionId.trim());
            entity.setCoursewareId(coursewareId.trim());
            entity.setPageIndex(pageIndex);
            entity.setNodeId(resolveNodeId(coursewareId.trim(), pageIndex));
            entity.setUserId(resolveUserId(sessionId.trim()));
            entity.setAskText(question.trim());
            entity.setAnswerText(answer.trim());
            entity.setReferenceFragments(copiedEvidence.isEmpty() ? null : objectMapper.valueToTree(copiedEvidence));
            entity.setLatencyMs(Math.max(1, latencyMs));
            QaRecord saved = qaRecordRepository().save(entity);
            record = toQaRecordView(saved);
        } else {
            record = new QaRecordView(
                    "qa_" + UUID.randomUUID().toString().replace("-", ""),
                    sessionId.trim(),
                    coursewareId.trim(),
                    pageIndex,
                    question.trim(),
                    answer.trim(),
                    copiedEvidence,
                    Math.max(1, latencyMs),
                    Instant.now()
            );
        }

        syncQa(record);
        persistSafely(record.sessionId(), "qa", record);
        tryMarkLatestInterruptAnswered(record.sessionId());
        return record;
    }

    public SessionRecordsSnapshot getSessionRecords(String sessionId) {
        validateSessionId(sessionId);
        String normalizedSessionId = sessionId.trim();

        if (isPersistentMode()) {
            if (!lectureSessionRepository().existsById(normalizedSessionId)) {
                SessionRecordState localState = tryLoadLocalState(normalizedSessionId);
                if (localState == null) {
                    throw new BusinessException(ErrorCode.NOT_FOUND, "lecture session not found");
                }
                return new SessionRecordsSnapshot(
                        new ArrayList<>(localState.interrupts.values()),
                        new ArrayList<>(localState.qaRecords.values())
                );
            }
            return new SessionRecordsSnapshot(
                    interruptRepository().findBySessionIdOrderByCreateTimeAsc(normalizedSessionId).stream()
                            .map(this::toInterruptView)
                            .toList(),
                    qaRecordRepository().findBySessionIdOrderByCreateTimeAsc(normalizedSessionId).stream()
                            .map(this::toQaRecordView)
                            .toList()
            );
        }

        SessionRecordState state = stateFor(normalizedSessionId);
        synchronized (state) {
            if (!state.knownSession) {
                loadFromJsonlIfPresent(normalizedSessionId, state);
            }
            if (!state.knownSession) {
                throw new BusinessException(ErrorCode.NOT_FOUND, "lecture session not found");
            }
            return new SessionRecordsSnapshot(
                    new ArrayList<>(state.interrupts.values()),
                    new ArrayList<>(state.qaRecords.values())
            );
        }
    }

    public void registerSession(String sessionId) {
        validateSessionId(sessionId);
        SessionRecordState state = stateFor(sessionId.trim());
        synchronized (state) {
            state.knownSession = true;
        }
    }

    public void tryMarkLatestInterruptAnswered(String sessionId) {
        tryUpdateLatestInterruptStatus(sessionId, ANSWERED);
    }

    public void tryMarkLatestInterruptResumed(String sessionId) {
        tryUpdateLatestInterruptStatus(sessionId, RESUMED);
    }

    private InterruptRecordView updateLatestInterruptStatus(String sessionId, String status) {
        validateSessionId(sessionId);

        InterruptRecordView updated;
        if (isPersistentMode()) {
            LectureInterruptRecord entity = requireLatestInterruptEntity(sessionId.trim());
            entity.setStatus(status);
            interruptRepository().save(entity);
            updated = toInterruptView(entity);
        } else {
            SessionRecordState state = stateForExistingSession(sessionId);
            synchronized (state) {
                InterruptRecordView latest = requireLatestInterrupt(state);
                updated = new InterruptRecordView(
                        latest.interruptId(),
                        latest.sessionId(),
                        latest.coursewareId(),
                        latest.pageIndex(),
                        latest.currentTime(),
                        latest.asrText(),
                        status,
                        latest.createdAt(),
                        Instant.now()
                );
            }
        }

        syncInterrupt(updated);
        persistSafely(updated.sessionId(), "interrupt", updated);
        return updated;
    }

    private void tryUpdateLatestInterruptStatus(String sessionId, String status) {
        try {
            updateLatestInterruptStatus(sessionId, status);
        } catch (BusinessException ex) {
            if (ex.getErrorCode() != ErrorCode.NOT_FOUND) {
                throw ex;
            }
        }
    }

    private void syncInterrupt(InterruptRecordView record) {
        SessionRecordState state = stateFor(record.sessionId());
        synchronized (state) {
            state.interrupts.put(record.interruptId(), record);
            state.knownSession = true;
        }
    }

    private void syncQa(QaRecordView record) {
        SessionRecordState state = stateFor(record.sessionId());
        synchronized (state) {
            state.qaRecords.put(record.qaRecordId(), record);
            state.knownSession = true;
        }
    }

    private SessionRecordState stateFor(String sessionId) {
        return recordStore.computeIfAbsent(sessionId, ignored -> new SessionRecordState());
    }

    private SessionRecordState stateForExistingSession(String sessionId) {
        SessionRecordState state = stateFor(sessionId.trim());
        synchronized (state) {
            if (!state.knownSession) {
                loadFromJsonlIfPresent(sessionId.trim(), state);
            }
            if (!state.knownSession) {
                throw new BusinessException(ErrorCode.NOT_FOUND, "lecture session not found");
            }
            return state;
        }
    }

    private SessionRecordState tryLoadLocalState(String sessionId) {
        SessionRecordState state = stateFor(sessionId);
        synchronized (state) {
            if (!state.knownSession) {
                loadFromJsonlIfPresent(sessionId, state);
            }
            return state.knownSession ? state : null;
        }
    }

    private InterruptRecordView requireLatestInterrupt(SessionRecordState state) {
        List<InterruptRecordView> records = new ArrayList<>(state.interrupts.values());
        if (records.isEmpty()) {
            throw new BusinessException(ErrorCode.NOT_FOUND, "interrupt record not found");
        }
        return records.get(records.size() - 1);
    }

    private LectureInterruptRecord requireLatestInterruptEntity(String sessionId) {
        ensureSessionExists(sessionId);
        return interruptRepository().findTopBySessionIdOrderByUpdateTimeDescIdDesc(sessionId)
                .orElseThrow(() -> new BusinessException(ErrorCode.NOT_FOUND, "interrupt record not found"));
    }

    private void ensureSessionExists(String sessionId) {
        if (isPersistentMode()) {
            if (!lectureSessionRepository().existsById(sessionId)) {
                throw new BusinessException(ErrorCode.NOT_FOUND, "lecture session not found");
            }
            return;
        }

        SessionRecordState state = stateFor(sessionId);
        synchronized (state) {
            if (!state.knownSession) {
                loadFromJsonlIfPresent(sessionId, state);
            }
            if (!state.knownSession) {
                throw new BusinessException(ErrorCode.NOT_FOUND, "lecture session not found");
            }
        }
    }

    private void loadFromJsonlIfPresent(String sessionId, SessionRecordState state) {
        Path recordFile = resolveRecordFile(sessionId);
        if (!Files.exists(recordFile)) {
            return;
        }
        try {
            for (String line : Files.readAllLines(recordFile, StandardCharsets.UTF_8)) {
                if (!StringUtils.hasText(line)) {
                    continue;
                }
                applyPersistedLine(state, objectMapper.readTree(line));
            }
            if (!state.interrupts.isEmpty() || !state.qaRecords.isEmpty()) {
                state.knownSession = true;
            }
        } catch (IOException ex) {
            log.warn("Failed to load lecture records from jsonl. sessionId={}, reason={}", sessionId, ex.getMessage());
        }
    }

    private void applyPersistedLine(SessionRecordState state, JsonNode lineNode) {
        String recordType = lineNode.path("recordType").asText("");
        JsonNode payloadNode = lineNode.path("payload");
        if (!payloadNode.isObject()) {
            return;
        }
        if ("interrupt".equals(recordType)) {
            InterruptRecordView record = objectMapper.convertValue(payloadNode, InterruptRecordView.class);
            state.interrupts.put(record.interruptId(), record);
        } else if ("qa".equals(recordType)) {
            QaRecordView record = objectMapper.convertValue(payloadNode, QaRecordView.class);
            state.qaRecords.put(record.qaRecordId(), record);
        }
    }

    private void persistSafely(String sessionId, String recordType, Object payload) {
        try {
            Files.createDirectories(recordBaseDir);
            String jsonLine = objectMapper.writeValueAsString(Map.of(
                    "recordType", recordType,
                    "payload", payload
            ));
            Files.writeString(
                    resolveRecordFile(sessionId),
                    jsonLine + System.lineSeparator(),
                    StandardCharsets.UTF_8,
                    StandardOpenOption.CREATE,
                    StandardOpenOption.WRITE,
                    StandardOpenOption.APPEND
            );
        } catch (Exception ex) {
            log.warn(
                    "Failed to persist lecture record locally. sessionId={}, recordType={}, reason={}",
                    sessionId,
                    recordType,
                    ex.getMessage()
            );
        }
    }

    private Path resolveRecordFile(String sessionId) {
        return recordBaseDir.resolve(sessionId + ".jsonl");
    }

    private List<EvidenceItemView> copyEvidence(List<EvidenceItemView> evidence) {
        if (evidence == null || evidence.isEmpty()) {
            return List.of();
        }
        List<EvidenceItemView> copied = new ArrayList<>(evidence.size());
        for (EvidenceItemView item : evidence) {
            if (item == null) {
                continue;
            }
            copied.add(new EvidenceItemView(
                    item.source(),
                    item.text(),
                    item.pageIndex(),
                    item.chunkId()
            ));
        }
        return List.copyOf(copied);
    }

    private List<EvidenceItemView> deserializeEvidence(JsonNode node) {
        if (node == null || node.isNull() || node.isMissingNode()) {
            return List.of();
        }
        try {
            return List.copyOf(objectMapper.convertValue(node, EVIDENCE_TYPE));
        } catch (Exception ex) {
            log.warn("Failed to deserialize QA evidence. reason={}", ex.getMessage());
            return List.of();
        }
    }

    private String resolveUserId(String sessionId) {
        if (!isPersistentMode()) {
            return "demo_user";
        }
        return lectureSessionRepository().findById(sessionId)
                .map(LectureSession::getUserId)
                .filter(StringUtils::hasText)
                .orElse("demo_user");
    }

    private String resolveNodeId(String coursewareId, Integer pageIndex) {
        if (pageIndex == null || pageIndex <= 0) {
            return null;
        }
        CoursewareService coursewareService = coursewareServiceProvider.getIfAvailable();
        if (coursewareService == null) {
            return null;
        }
        try {
            return coursewareService.getCurrentNode(coursewareId, pageIndex).nodeId();
        } catch (Exception ex) {
            log.debug("Failed to resolve node id for QA record. coursewareId={}, pageIndex={}, reason={}",
                    coursewareId, pageIndex, ex.getMessage());
            return null;
        }
    }

    private InterruptRecordView toInterruptView(LectureInterruptRecord entity) {
        return new InterruptRecordView(
                entity.getId(),
                entity.getSessionId(),
                entity.getCoursewareId(),
                entity.getPageIndex(),
                entity.getCurrentTime(),
                entity.getAsrText(),
                entity.getStatus(),
                toInstant(entity.getCreateTime()),
                toInstant(entity.getUpdateTime())
        );
    }

    private QaRecordView toQaRecordView(QaRecord entity) {
        return new QaRecordView(
                "qa_" + entity.getId(),
                entity.getSessionId(),
                entity.getCoursewareId(),
                entity.getPageIndex(),
                entity.getAskText(),
                entity.getAnswerText(),
                deserializeEvidence(entity.getReferenceFragments()),
                entity.getLatencyMs() == null ? 1L : entity.getLatencyMs(),
                toInstant(entity.getCreateTime())
        );
    }

    private void validateSessionId(String sessionId) {
        if (!StringUtils.hasText(sessionId)) {
            throw new BusinessException(ErrorCode.PARAM_ERROR, "sessionId must not be blank");
        }
    }

    private void validateCoursewareId(String coursewareId) {
        if (!StringUtils.hasText(coursewareId)) {
            throw new BusinessException(ErrorCode.PARAM_ERROR, "coursewareId must not be blank");
        }
    }

    private boolean isPersistentMode() {
        return interruptRepositoryProvider.getIfAvailable() != null
                && qaRecordRepositoryProvider.getIfAvailable() != null
                && lectureSessionRepositoryProvider.getIfAvailable() != null;
    }

    private LectureInterruptRecordRepository interruptRepository() {
        LectureInterruptRecordRepository repository = interruptRepositoryProvider.getIfAvailable();
        if (repository == null) {
            throw new IllegalStateException("LectureInterruptRecordRepository is unavailable in the current profile");
        }
        return repository;
    }

    private QaRecordRepository qaRecordRepository() {
        QaRecordRepository repository = qaRecordRepositoryProvider.getIfAvailable();
        if (repository == null) {
            throw new IllegalStateException("QaRecordRepository is unavailable in the current profile");
        }
        return repository;
    }

    private LectureSessionRepository lectureSessionRepository() {
        LectureSessionRepository repository = lectureSessionRepositoryProvider.getIfAvailable();
        if (repository == null) {
            throw new IllegalStateException("LectureSessionRepository is unavailable in the current profile");
        }
        return repository;
    }

    private static Instant toInstant(LocalDateTime time) {
        return time == null ? Instant.now() : time.atZone(ZoneId.systemDefault()).toInstant();
    }

    public record SessionRecordsSnapshot(
            List<InterruptRecordView> interrupts,
            List<QaRecordView> qaRecords
    ) {
    }

    private static final class SessionRecordState {
        private final Map<String, InterruptRecordView> interrupts = new LinkedHashMap<>();
        private final Map<String, QaRecordView> qaRecords = new LinkedHashMap<>();
        private boolean knownSession;
    }
}
