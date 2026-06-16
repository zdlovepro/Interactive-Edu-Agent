package com.interactive.edu.service.courseware;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.interactive.edu.dto.CoursewareUploadResult;
import com.interactive.edu.dto.courseware.UpdateCoursewareScriptRequest;
import com.interactive.edu.entity.Courseware;
import com.interactive.edu.entity.CoursewarePage;
import com.interactive.edu.entity.LectureScript;
import com.interactive.edu.enums.CoursewareStatus;
import com.interactive.edu.enums.TaskStatus;
import com.interactive.edu.exception.BusinessException;
import com.interactive.edu.exception.ErrorCode;
import com.interactive.edu.repository.CoursewarePageRepository;
import com.interactive.edu.repository.CoursewareRepository;
import com.interactive.edu.repository.LectureScriptRepository;
import com.interactive.edu.service.python.PythonParseClient;
import com.interactive.edu.service.python.PythonParseRequest;
import com.interactive.edu.service.python.PythonScriptClient;
import com.interactive.edu.service.python.PythonScriptRequest;
import com.interactive.edu.storage.StorageServiceFactory;
import com.interactive.edu.storage.StoredObject;
import com.interactive.edu.service.tts.TtsService;
import com.interactive.edu.vo.courseware.CoursewareDetailView;
import com.interactive.edu.vo.courseware.CoursewareListItem;
import com.interactive.edu.vo.courseware.CoursewareListView;
import com.interactive.edu.vo.courseware.CurrentNodeView;
import com.interactive.edu.vo.courseware.OutlineItemView;
import com.interactive.edu.vo.courseware.ScriptSegmentView;
import com.interactive.edu.vo.courseware.ScriptView;
import lombok.Getter;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.io.FileSystemResource;
import org.springframework.core.io.Resource;
import org.springframework.core.task.TaskExecutor;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;
import org.springframework.web.multipart.MultipartFile;

import java.io.File;
import java.io.IOException;
import java.io.InputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.time.Instant;
import java.time.LocalDateTime;
import java.time.ZoneId;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashSet;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.NoSuchElementException;
import java.util.Objects;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ConcurrentMap;
import java.util.concurrent.atomic.AtomicInteger;

@Service
@RequiredArgsConstructor
@Slf4j
public class CoursewareService {

    private static final TypeReference<List<String>> STRING_LIST_TYPE = new TypeReference<>() {
    };

    private final StorageServiceFactory storageServiceFactory;
    private final PythonParseClient pythonParseClient;
    private final PythonScriptClient pythonScriptClient;
    private final TaskExecutor taskExecutor;
    private final TtsService ttsService;
    private final ObjectMapper objectMapper;
    private final ObjectProvider<CoursewareRepository> coursewareRepositoryProvider;
    private final ObjectProvider<CoursewarePageRepository> coursewarePageRepositoryProvider;
    private final ObjectProvider<LectureScriptRepository> lectureScriptRepositoryProvider;

    @Value("${chain.strict:false}")
    private boolean strictChain;

    private final ConcurrentMap<String, CoursewareState> coursewareStore = new ConcurrentHashMap<>();
    private final ConcurrentMap<String, ParsedCourseware> parsedStore = new ConcurrentHashMap<>();
    private final ConcurrentMap<String, ScriptView> scriptStore = new ConcurrentHashMap<>();
    private final ConcurrentMap<String, String> scriptStatusStore = new ConcurrentHashMap<>();

    public CoursewareUploadResult importLocalFile(Path localFile, String requestedName) {
        if (localFile == null) {
            throw new IllegalArgumentException("localFile must not be null");
        }

        Path normalizedFile = localFile.toAbsolutePath().normalize();
        if (!Files.exists(normalizedFile) || !Files.isRegularFile(normalizedFile)) {
            throw new IllegalArgumentException("Imported local file does not exist: " + normalizedFile);
        }

        String coursewareId = newCoursewareId();
        String filename = normalizeFilename(normalizedFile.getFileName().toString());
        String displayName = resolveDisplayName(requestedName, filename);
        String contentType = probeContentType(normalizedFile);
        StoredObject storedObject = storageServiceFactory.get().save(
                coursewareId,
                new PathMultipartFile(normalizedFile, filename, contentType)
        );

        CoursewareState state = new CoursewareState(
                coursewareId,
                displayName,
                filename,
                storedObject.getKey(),
                storedObject.getStorageType(),
                contentType
        );
        state.setStatus(CoursewareStatus.PARSING.name());
        state.setCurrentTaskStatus(TaskStatus.RUNNING.name());

        coursewareStore.put(coursewareId, state);
        persistCoursewareState(state);
        taskExecutor.execute(() -> completeParse(state));

        log.info(
                "Courseware local import accepted. coursewareId={}, file={}, displayName={}, storageType={}",
                coursewareId,
                normalizedFile,
                displayName,
                storedObject.getStorageType()
        );
        return new CoursewareUploadResult(coursewareId, CoursewareStatus.UPLOADED.name());
    }

    public CoursewareUploadResult upload(MultipartFile file, String requestedName) {
        if (file == null || file.isEmpty()) {
            throw new IllegalArgumentException("Uploaded file must not be empty");
        }

        String coursewareId = newCoursewareId();
        String filename = normalizeFilename(file.getOriginalFilename());
        String displayName = resolveDisplayName(requestedName, filename);
        StoredObject storedObject = storageServiceFactory.get().save(coursewareId, file);

        CoursewareState state = new CoursewareState(
                coursewareId,
                displayName,
                filename,
                storedObject.getKey(),
                storedObject.getStorageType(),
                file.getContentType()
        );
        state.setStatus(CoursewareStatus.PARSING.name());
        state.setCurrentTaskStatus(TaskStatus.RUNNING.name());

        coursewareStore.put(coursewareId, state);
        persistCoursewareState(state);
        taskExecutor.execute(() -> completeParse(state));

        log.info(
                "Courseware upload accepted. coursewareId={}, filename={}, displayName={}",
                coursewareId,
                filename,
                displayName
        );
        return new CoursewareUploadResult(coursewareId, CoursewareStatus.UPLOADED.name());
    }

    public CoursewareListView list(int page, int pageSize, String status) {
        if (page <= 0 || pageSize <= 0) {
            throw new IllegalArgumentException("page and pageSize must be greater than 0");
        }

        if (isPersistentMode()) {
            List<Courseware> filtered = coursewareRepository().findAll().stream()
                    .filter(item -> !StringUtils.hasText(status) || status.equalsIgnoreCase(item.getStatus()))
                    .sorted(Comparator.comparing(
                            Courseware::getCreateTime,
                            Comparator.nullsLast(Comparator.reverseOrder())
                    ))
                    .toList();

            int fromIndex = Math.min((page - 1) * pageSize, filtered.size());
            int toIndex = Math.min(fromIndex + pageSize, filtered.size());
            List<CoursewareListItem> items = filtered.subList(fromIndex, toIndex).stream()
                    .map(this::toListItem)
                    .toList();
            return new CoursewareListView(items, filtered.size(), page, pageSize);
        }

        List<CoursewareState> filtered = coursewareStore.values().stream()
                .filter(item -> !StringUtils.hasText(status) || status.equalsIgnoreCase(item.getStatus()))
                .sorted(Comparator.comparing(CoursewareState::getCreatedAt).reversed())
                .toList();

        int fromIndex = Math.min((page - 1) * pageSize, filtered.size());
        int toIndex = Math.min(fromIndex + pageSize, filtered.size());
        List<CoursewareListItem> items = filtered.subList(fromIndex, toIndex).stream()
                .map(item -> new CoursewareListItem(
                        item.getId(),
                        item.getName(),
                        item.getStatus(),
                        item.getCreatedAt().toString(),
                        item.getCurrentTaskStatus()
                ))
                .toList();
        return new CoursewareListView(items, filtered.size(), page, pageSize);
    }

    public CoursewareDetailView getDetail(String coursewareId) {
        if (isPersistentMode()) {
            return toDetailView(requirePersistedCourseware(coursewareId));
        }

        CoursewareState state = requireCourseware(coursewareId);
        return new CoursewareDetailView(
                state.getId(),
                state.getName(),
                state.getStatus(),
                state.getCurrentTaskStatus(),
                state.getFileType(),
                state.getCreatedAt().toString(),
                state.getUpdatedAt().toString()
        );
    }

    public String triggerScriptGeneration(String coursewareId) {
        ensureCoursewareId(coursewareId);
        CoursewareState state = requireCourseware(coursewareId);
        ScriptView existingScript = findExistingScript(coursewareId);

        if (existingScript != null) {
            if (shouldBackfillMissingAudio(existingScript)) {
                String currentStatus = scriptStatusStore.get(coursewareId);
                if (CoursewareStatus.GENERATING_SCRIPT.name().equals(currentStatus)) {
                    return currentStatus;
                }

                scriptStatusStore.put(coursewareId, CoursewareStatus.GENERATING_SCRIPT.name());
                state.setStatus(CoursewareStatus.GENERATING_SCRIPT.name());
                state.setCurrentTaskStatus(TaskStatus.RUNNING.name());
                state.touch();
                persistCoursewareState(state);

                long missingAudioCount = countMissingAudioSegments(existingScript);
                log.info(
                        "Script audio backfill scheduled. coursewareId={}, missingAudioSegments={}",
                        coursewareId,
                        missingAudioCount
                );
                taskExecutor.execute(() -> backfillMissingSegmentAudio(coursewareId, state, existingScript));
                return CoursewareStatus.GENERATING_SCRIPT.name();
            }

            if (!CoursewareStatus.READY.name().equals(state.getStatus())) {
                state.setStatus(CoursewareStatus.READY.name());
                if (!StringUtils.hasText(state.getCurrentTaskStatus())
                        || TaskStatus.RUNNING.name().equals(state.getCurrentTaskStatus())) {
                    state.setCurrentTaskStatus(TaskStatus.SUCCESS.name());
                }
                state.touch();
                persistCoursewareState(state);
            }
            scriptStatusStore.put(coursewareId, CoursewareStatus.READY.name());
            return CoursewareStatus.READY.name();
        }

        ParsedCourseware parsedCourseware = loadParsedCourseware(coursewareId);
        if (parsedCourseware == null) {
            throw new BusinessException(ErrorCode.STATE_CONFLICT, "Courseware has not been parsed yet");
        }

        String currentStatus = scriptStatusStore.get(coursewareId);
        if (CoursewareStatus.GENERATING_SCRIPT.name().equals(currentStatus)) {
            return currentStatus;
        }

        scriptStatusStore.put(coursewareId, CoursewareStatus.GENERATING_SCRIPT.name());
        state.setStatus(CoursewareStatus.GENERATING_SCRIPT.name());
        state.setCurrentTaskStatus(TaskStatus.RUNNING.name());
        state.touch();
        persistCoursewareState(state);

        log.info("Script generation scheduled. coursewareId={}", coursewareId);
        taskExecutor.execute(() -> buildScript(coursewareId, state.getName(), parsedCourseware));
        return CoursewareStatus.GENERATING_SCRIPT.name();
    }

    public ScriptView getScript(String coursewareId) {
        ensureCoursewareId(coursewareId);
        requireCourseware(coursewareId);

        ScriptView script = findExistingScript(coursewareId);
        if (script != null) {
            return script;
        }

        if (CoursewareStatus.FAILED.name().equals(getScriptStatus(coursewareId))) {
            return new ScriptView(
                    coursewareId,
                    List.of(),
                    List.of(),
                    CoursewareStatus.FAILED.name(),
                    null,
                    null
            );
        }
        return null;
    }

    public ScriptView updateScript(String coursewareId, UpdateCoursewareScriptRequest request) {
        ensureCoursewareId(coursewareId);
        requireCourseware(coursewareId);

        if (request == null || request.getSegments() == null || request.getSegments().isEmpty()) {
            throw new IllegalArgumentException("Script segments must not be empty");
        }

        ScriptView existing = requireScript(coursewareId);
        Map<String, UpdateCoursewareScriptRequest.Segment> updatesById = new LinkedHashMap<>();
        for (UpdateCoursewareScriptRequest.Segment segment : request.getSegments()) {
            updatesById.put(segment.getId(), segment);
        }

        List<ScriptSegmentView> rewrittenSegments = new ArrayList<>(existing.segments().size());
        List<OutlineItemView> rewrittenOutline = new ArrayList<>(existing.segments().size());
        Set<String> editedSegmentIds = new HashSet<>();
        boolean hasChanges = false;

        for (ScriptSegmentView segment : existing.segments()) {
            UpdateCoursewareScriptRequest.Segment update = updatesById.remove(segment.id());
            if (update == null) {
                update = updatesById.remove(segment.nodeId());
            }

            if (update == null) {
                rewrittenSegments.add(segment);
                rewrittenOutline.add(new OutlineItemView(segment.id(), segment.title()));
                continue;
            }

            String resolvedTitle = defaultText(update.getTitle(), segment.title());
            String resolvedContent = defaultText(update.getContent(), segment.content());
            boolean resolvedDigitalHumanEnabled = update.getDigitalHumanEnabled() != null
                    ? update.getDigitalHumanEnabled()
                    : segment.digitalHumanEnabled();
            boolean contentChanged = !Objects.equals(resolvedTitle, segment.title())
                    || !Objects.equals(resolvedContent, segment.content());
            boolean digitalHumanChanged = resolvedDigitalHumanEnabled != segment.digitalHumanEnabled();
            boolean changed = contentChanged || digitalHumanChanged;
            boolean needsAudioRefresh = contentChanged || !StringUtils.hasText(segment.audioUrl());

            if (changed) {
                editedSegmentIds.add(segment.id());
                hasChanges = true;
            }

            ScriptSegmentView rewrittenSegment = new ScriptSegmentView(
                    segment.id(),
                    segment.nodeId(),
                    segment.pageIndex(),
                    resolvedTitle,
                    resolvedContent,
                    segment.knowledgePoints(),
                    needsAudioRefresh ? null : segment.audioUrl(),
                    segment.pageImagePath(),
                    segment.pageImageUrl(),
                    segment.visualSummary(),
                    segment.visualObjects(),
                    resolvedDigitalHumanEnabled
            );
            rewrittenSegments.add(rewrittenSegment);
            rewrittenOutline.add(new OutlineItemView(segment.id(), resolvedTitle));
        }

        if (!updatesById.isEmpty()) {
            throw new IllegalArgumentException("Unknown script segment id: " + updatesById.keySet().iterator().next());
        }

        if (!hasChanges && !shouldBackfillMissingAudio(existing)) {
            return existing;
        }

        CoursewareState state = requireCourseware(coursewareId);
        TtsBatchResult ttsBatchResult = request.isRegenerateAudio()
                ? synthesizeSegmentAudioUrls(coursewareId, rewrittenSegments)
                : summarizeCurrentAudioState(rewrittenSegments);

        ScriptView updated = new ScriptView(
                existing.coursewareId(),
                List.copyOf(rewrittenOutline),
                ttsBatchResult.segments(),
                CoursewareStatus.READY.name(),
                existing.opening(),
                existing.closing()
        );

        scriptStore.put(coursewareId, updated);
        markScriptReady(state, resolveScriptTaskStatus(ttsBatchResult), updated, editedSegmentIds);
        return updated;
    }

    public String getScriptStatus(String coursewareId) {
        ensureCoursewareId(coursewareId);
        if (isPersistentMode()) {
            return defaultText(requirePersistedCourseware(coursewareId).getStatus(), CoursewareStatus.UPLOADED.name());
        }
        CoursewareState state = requireCourseware(coursewareId);
        return scriptStatusStore.getOrDefault(coursewareId, state.getStatus());
    }

    public ScriptView requireScript(String coursewareId) {
        ScriptView script = getScript(coursewareId);
        if (script == null) {
            throw new BusinessException(ErrorCode.STATE_CONFLICT, "Script has not been generated yet");
        }
        return script;
    }

    public List<ScriptSegmentView> getScriptSegments(String coursewareId) {
        return requireScript(coursewareId).segments();
    }

    public ScriptSegmentView getSegmentForPage(String coursewareId, int pageIndex) {
        List<ScriptSegmentView> segments = getScriptSegments(coursewareId);
        return segments.stream()
                .filter(segment -> segment.pageIndex() == pageIndex)
                .findFirst()
                .orElse(segments.get(0));
    }

    public QaIngestPage getQaPageForPage(String coursewareId, int pageIndex) {
        ensureCoursewareId(coursewareId);

        ScriptView scriptView = findExistingScript(coursewareId);
        if (scriptView != null && scriptView.segments() != null && !scriptView.segments().isEmpty()) {
            return scriptView.segments().stream()
                    .filter(segment -> segment.pageIndex() == pageIndex)
                    .findFirst()
                    .map(this::toQaIngestPage)
                    .orElseGet(() -> toQaIngestPage(scriptView.segments().get(0)));
        }

        ParsedCourseware parsedCourseware = loadParsedCourseware(coursewareId);
        if (parsedCourseware != null && !parsedCourseware.segments().isEmpty()) {
            return parsedCourseware.segments().stream()
                    .filter(segment -> segment.pageIndex() == pageIndex)
                    .findFirst()
                    .map(this::toQaIngestPage)
                    .orElseGet(() -> toQaIngestPage(parsedCourseware.segments().get(0)));
        }

        return null;
    }

    public List<QaIngestPage> getQaIngestPages(String coursewareId) {
        ensureCoursewareId(coursewareId);

        ScriptView scriptView = findExistingScript(coursewareId);
        if (scriptView != null && scriptView.segments() != null && !scriptView.segments().isEmpty()) {
            return scriptView.segments().stream()
                    .map(this::toQaIngestPage)
                    .toList();
        }

        ParsedCourseware parsedCourseware = loadParsedCourseware(coursewareId);
        if (parsedCourseware != null && !parsedCourseware.segments().isEmpty()) {
            return parsedCourseware.segments().stream()
                    .map(this::toQaIngestPage)
                    .toList();
        }

        return List.of();
    }

    private QaIngestPage toQaIngestPage(ParsedSegment segment) {
        return new QaIngestPage(
                segment.pageIndex(),
                segment.title(),
                segment.content(),
                List.copyOf(segment.knowledgePoints()),
                segment.pageImagePath(),
                segment.visualSummary(),
                List.copyOf(segment.visualObjects())
        );
    }

    private QaIngestPage toQaIngestPage(ScriptSegmentView segment) {
        return new QaIngestPage(
                segment.pageIndex(),
                segment.title(),
                segment.content(),
                segment.knowledgePoints() == null ? List.of() : List.copyOf(segment.knowledgePoints()),
                segment.pageImagePath(),
                segment.visualSummary(),
                segment.visualObjects() == null ? List.of() : List.copyOf(segment.visualObjects())
        );
    }

    public CurrentNodeView getCurrentNode(String coursewareId, int pageIndex) {
        ScriptSegmentView segment = getSegmentForPage(coursewareId, pageIndex);
        return new CurrentNodeView(segment.nodeId(), segment.pageIndex(), segment.content(), segment.audioUrl());
    }

    public PageMediaResource getScriptPageImageResource(String coursewareId, int pageIndex) {
        ScriptSegmentView segment = getSegmentForPage(coursewareId, pageIndex);
        if (!StringUtils.hasText(segment.pageImagePath())) {
            throw new NoSuchElementException("Page image not found");
        }

        if (isHttpUrl(segment.pageImagePath())) {
            throw new IllegalStateException("Remote page images should be accessed directly via pageImageUrl");
        }

        Path imagePath = Path.of(segment.pageImagePath()).toAbsolutePath().normalize();
        if (!Files.exists(imagePath) || !Files.isRegularFile(imagePath)) {
            throw new NoSuchElementException("Page image not found");
        }

        return new PageMediaResource(
                new FileSystemResource(imagePath),
                resolveMediaType(imagePath)
        );
    }

    private boolean shouldBackfillMissingAudio(ScriptView script) {
        return script != null
                && ttsService.canGenerateAudio()
                && countMissingAudioSegments(script) > 0;
    }

    private long countMissingAudioSegments(ScriptView script) {
        return script.segments().stream()
                .filter(segment -> !StringUtils.hasText(segment.audioUrl()))
                .count();
    }

    private void backfillMissingSegmentAudio(String coursewareId, CoursewareState state, ScriptView existingScript) {
        try {
            TtsBatchResult ttsBatchResult = synthesizeSegmentAudioUrls(coursewareId, existingScript.segments());
            ScriptView scriptView = new ScriptView(
                    existingScript.coursewareId(),
                    existingScript.outline(),
                    ttsBatchResult.segments(),
                    CoursewareStatus.READY.name(),
                    existingScript.opening(),
                    existingScript.closing()
            );

            scriptStore.put(coursewareId, scriptView);
            TaskStatus taskStatus = resolveScriptTaskStatus(ttsBatchResult);
            markScriptReady(state, taskStatus, scriptView);

            log.info(
                    "Script audio backfill completed. coursewareId={}, segments={}, ttsSuccessCount={}, ttsFailureCount={}, taskStatus={}",
                    coursewareId,
                    scriptView.segments().size(),
                    ttsBatchResult.successCount(),
                    ttsBatchResult.failureCount(),
                    taskStatus.name()
            );
        } catch (Exception ex) {
            log.error("Script audio backfill failed. coursewareId={}", coursewareId, ex);
            scriptStore.put(coursewareId, existingScript);
            scriptStatusStore.put(coursewareId, CoursewareStatus.READY.name());
            state.setStatus(CoursewareStatus.READY.name());
            state.setCurrentTaskStatus(TaskStatus.PARTIAL_SUCCESS.name());
            state.touch();
            persistCoursewareState(state);
        }
    }

    private void completeParse(CoursewareState state) {
        try {
            log.info("Courseware parsing started. coursewareId={}", state.getId());
            PythonParseClient.ParsePayload payload = null;
            try {
                payload = pythonParseClient.parse(new PythonParseRequest(
                        state.getId(),
                        state.getStorageType(),
                        state.getStorageKey(),
                        state.getOriginalFilename(),
                        state.getFileType()
                ));
            } catch (Exception ex) {
                log.warn(
                        "Python parsing unavailable, fallback to local parsing. coursewareId={}, reason={}",
                        state.getId(),
                        ex.getMessage()
                );
                if (strictChain) {
                    throw new IllegalStateException("Python parse failed in strict chain mode", ex);
                }
            }

            if (strictChain && (payload == null || payload.safeSegments().isEmpty())) {
                throw new IllegalStateException("Python parse returned no segments in strict chain mode");
            }

            ParsedCourseware parsedCourseware = toParsedCourseware(state, payload);
            parsedStore.put(state.getId(), parsedCourseware);
            state.setStatus(CoursewareStatus.PARSED.name());
            state.setCurrentTaskStatus(TaskStatus.SUCCESS.name());
            state.touch();
            persistParsedCourseware(state, parsedCourseware);

            log.info(
                    "Courseware parsing completed. coursewareId={}, segments={}",
                    state.getId(),
                    parsedCourseware.segments().size()
            );
        } catch (Exception ex) {
            log.error("Courseware parsing failed. coursewareId={}", state.getId(), ex);
            parsedStore.remove(state.getId());
            state.setStatus(CoursewareStatus.FAILED.name());
            state.setCurrentTaskStatus(TaskStatus.FAILED.name());
            state.touch();
            persistCoursewareState(state);
        }
    }

    private ParsedCourseware toParsedCourseware(CoursewareState state, PythonParseClient.ParsePayload payload) {
        List<ParsedSegment> segments = new ArrayList<>();
        if (payload != null && !payload.safeSegments().isEmpty()) {
            int index = 1;
            for (PythonParseClient.ParseSegment segment : payload.safeSegments()) {
                int pageIndex = segment.pageIndex() > 0 ? segment.pageIndex() : index;
                segments.add(new ParsedSegment(
                        pageIndex,
                        defaultText(segment.title(), "第 " + pageIndex + " 页"),
                        defaultText(segment.content(), "本页内容正在整理中。"),
                        segment.safeKnowledgePoints(),
                        segment.pageImagePath(),
                        segment.visualSummary(),
                        segment.safeVisualObjects()
                ));
                index++;
            }
        }

        if (segments.isEmpty()) {
            segments = buildFallbackSegments(state.getName(), state.getOriginalFilename());
        }
        return new ParsedCourseware(state.getId(), List.copyOf(segments));
    }

    private void buildScript(String coursewareId, String coursewareName, ParsedCourseware parsedCourseware) {
        CoursewareState state = requireCourseware(coursewareId);
        try {
            GeneratedScriptDraft draft = buildScriptDraft(coursewareId, coursewareName, parsedCourseware);
            ScriptView baseScriptView = toScriptView(coursewareId, parsedCourseware, draft);
            TtsBatchResult ttsBatchResult = synthesizeSegmentAudioUrls(coursewareId, baseScriptView.segments());
            TaskStatus taskStatus = resolveScriptTaskStatus(ttsBatchResult);

            ScriptView scriptView = new ScriptView(
                    baseScriptView.coursewareId(),
                    baseScriptView.outline(),
                    ttsBatchResult.segments(),
                    baseScriptView.status(),
                    baseScriptView.opening(),
                    baseScriptView.closing()
            );

            scriptStore.put(coursewareId, scriptView);
            markScriptReady(state, taskStatus, scriptView);

            log.info(
                    "Script generation completed. coursewareId={}, segments={}, ttsSuccessCount={}, ttsFailureCount={}, taskStatus={}",
                    coursewareId,
                    scriptView.segments().size(),
                    ttsBatchResult.successCount(),
                    ttsBatchResult.failureCount(),
                    taskStatus.name()
            );
        } catch (Exception ex) {
            log.error("Script generation failed. coursewareId={}", coursewareId, ex);
            scriptStore.remove(coursewareId);
            scriptStatusStore.put(coursewareId, CoursewareStatus.FAILED.name());
            state.setStatus(CoursewareStatus.FAILED.name());
            state.setCurrentTaskStatus(TaskStatus.FAILED.name());
            state.touch();
            persistCoursewareState(state);
        }
    }

    private GeneratedScriptDraft buildScriptDraft(
            String coursewareId,
            String coursewareName,
            ParsedCourseware parsedCourseware
    ) {
        try {
            return buildScriptDraftFromPython(coursewareId, coursewareName, parsedCourseware);
        } catch (Exception ex) {
            log.warn(
                    "Python script generation unavailable, fallback to local template. coursewareId={}, reason={}",
                    coursewareId,
                    ex.getMessage()
            );
            if (strictChain) {
                throw new IllegalStateException("Python script generation failed in strict chain mode", ex);
            }
            return buildLocalScriptDraft(coursewareName, parsedCourseware);
        }
    }

    private GeneratedScriptDraft buildScriptDraftFromPython(
            String coursewareId,
            String coursewareName,
            ParsedCourseware parsedCourseware
    ) {
        PythonScriptClient.ScriptPayload payload = pythonScriptClient.generate(
                new PythonScriptRequest(
                        coursewareId,
                        coursewareName,
                        null,
                        parsedCourseware.segments().stream()
                                .map(segment -> new PythonScriptRequest.PageContent(
                                        segment.pageIndex(),
                                        segment.title(),
                                        segment.content(),
                                        segment.knowledgePoints(),
                                        segment.pageImagePath(),
                                        segment.visualSummary(),
                                        segment.visualObjects()
                                ))
                                .toList(),
                        null
                )
        );

        List<GeneratedPage> generatedPages = payload.safePages().stream()
                .map(page -> new GeneratedPage(page.pageIndex(), page.script(), page.transition()))
                .toList();

        if (generatedPages.isEmpty()) {
            throw new IllegalStateException("Python script generation returned empty pages");
        }
        if (generatedPages.size() != parsedCourseware.segments().size()) {
            log.warn(
                    "Python script page count mismatch. coursewareId={}, parsedPages={}, generatedPages={}",
                    coursewareId,
                    parsedCourseware.segments().size(),
                    generatedPages.size()
            );
        }

        return new GeneratedScriptDraft(payload.opening(), generatedPages, payload.closing());
    }

    private GeneratedScriptDraft buildLocalScriptDraft(String coursewareName, ParsedCourseware parsedCourseware) {
        List<GeneratedPage> pages = new ArrayList<>();
        int totalPages = parsedCourseware.segments().size();
        for (int index = 0; index < totalPages; index++) {
            ParsedSegment parsedSegment = parsedCourseware.segments().get(index);
            pages.add(new GeneratedPage(
                    parsedSegment.pageIndex(),
                    buildFallbackPageScript(parsedSegment, index + 1, totalPages),
                    buildFallbackTransition(index + 1, totalPages, nextTitle(parsedCourseware, index))
            ));
        }

        return new GeneratedScriptDraft(
                "这节内容会围绕课件里的核心知识点展开，尽量把概念、关系和计算逻辑讲清楚。",
                List.copyOf(pages),
                "这部分核心内容先梳理到这里，后面可以再把关键概念和计算关系连起来复习。"
        );
    }

    private ScriptView toScriptView(String coursewareId, ParsedCourseware parsedCourseware, GeneratedScriptDraft draft) {
        Map<Integer, GeneratedPage> generatedByPageIndex = new HashMap<>();
        for (GeneratedPage page : draft.pages()) {
            generatedByPageIndex.putIfAbsent(page.pageIndex(), page);
        }

        String opening = defaultText(draft.opening(), "");
        String closing = defaultText(draft.closing(), "");
        List<OutlineItemView> outline = new ArrayList<>();
        List<ScriptSegmentView> segments = new ArrayList<>();
        int totalPages = parsedCourseware.segments().size();

        for (int index = 0; index < totalPages; index++) {
            ParsedSegment parsedSegment = parsedCourseware.segments().get(index);
            GeneratedPage generatedPage = generatedByPageIndex.get(parsedSegment.pageIndex());
            String scriptBody = generatedPage != null && StringUtils.hasText(generatedPage.script())
                    ? generatedPage.script().trim()
                    : buildFallbackPageScript(parsedSegment, index + 1, totalPages);
            String transition = generatedPage != null
                    ? defaultText(generatedPage.transition(), "")
                    : buildFallbackTransition(index + 1, totalPages, nextTitle(parsedCourseware, index));

            String nodeId = coursewareId + "_node_" + String.format("%03d", index + 1);
            String content = composeSegmentContent(
                    scriptBody,
                    transition,
                    index == 0 ? opening : null,
                    index == totalPages - 1 ? closing : null
            );

            outline.add(new OutlineItemView(nodeId, parsedSegment.title()));
            segments.add(new ScriptSegmentView(
                    nodeId,
                    nodeId,
                    parsedSegment.pageIndex(),
                    parsedSegment.title(),
                    content,
                    parsedSegment.knowledgePoints(),
                    null,
                    parsedSegment.pageImagePath(),
                    resolvePageImageAccessUrl(coursewareId, parsedSegment.pageIndex(), parsedSegment.pageImagePath()),
                    parsedSegment.visualSummary(),
                    parsedSegment.visualObjects(),
                    false
            ));
        }

        return new ScriptView(
                coursewareId,
                List.copyOf(outline),
                List.copyOf(segments),
                CoursewareStatus.READY.name(),
                StringUtils.hasText(opening) ? opening : null,
                StringUtils.hasText(closing) ? closing : null
        );
    }

    private String composeSegmentContent(String scriptBody, String transition, String opening, String closing) {
        List<String> parts = new ArrayList<>();
        if (StringUtils.hasText(opening)) {
            parts.add(opening.trim());
        }
        if (StringUtils.hasText(scriptBody)) {
            parts.add(scriptBody.trim());
        }
        return String.join(" ", parts);
    }

    private TtsBatchResult synthesizeSegmentAudioUrls(String coursewareId, List<ScriptSegmentView> segments) {
        if (segments.isEmpty()) {
            return new TtsBatchResult(List.of(), 0, 0);
        }

        int reusedCount = (int) segments.stream()
                .filter(segment -> StringUtils.hasText(segment.audioUrl()))
                .count();
        int queuedCount = segments.size() - reusedCount;
        AtomicInteger completedCount = new AtomicInteger();
        List<CompletableFuture<SegmentAudioOutcome>> futures = new ArrayList<>(segments.size());

        log.info(
                "TTS batch synthesis started. coursewareId={}, totalSegments={}, queuedCount={}, reusedCount={}",
                coursewareId,
                segments.size(),
                queuedCount,
                reusedCount
        );

        for (ScriptSegmentView segment : segments) {
            if (StringUtils.hasText(segment.audioUrl())) {
                futures.add(CompletableFuture.completedFuture(new SegmentAudioOutcome(segment, segment.audioUrl())));
                continue;
            }

            CompletableFuture<String> audioFuture = ttsService.synthesizeToAudioUrlAsync(segment.content());
            if (audioFuture == null) {
                log.warn(
                        "TTS async future is null, degrade to text-only segment. coursewareId={}, nodeId={}, pageIndex={}",
                        coursewareId,
                        segment.nodeId(),
                        segment.pageIndex()
                );
                audioFuture = CompletableFuture.completedFuture(null);
            }

            CompletableFuture<SegmentAudioOutcome> future = audioFuture
                    .thenApply(audioUrl -> {
                        int completed = completedCount.incrementAndGet();
                        if (StringUtils.hasText(audioUrl)) {
                            log.info(
                                    "TTS segment generated. coursewareId={}, nodeId={}, pageIndex={}, textLength={}, progress={}/{}",
                                    coursewareId,
                                    segment.nodeId(),
                                    segment.pageIndex(),
                                    segment.content().length(),
                                    completed,
                                    queuedCount
                            );
                        } else {
                            log.info(
                                    "TTS segment unavailable. coursewareId={}, nodeId={}, pageIndex={}, textLength={}, progress={}/{}",
                                    coursewareId,
                                    segment.nodeId(),
                                    segment.pageIndex(),
                                    segment.content().length(),
                                    completed,
                                    queuedCount
                            );
                        }
                        return new SegmentAudioOutcome(segment, audioUrl);
                    })
                    .exceptionally(ex -> {
                        int completed = completedCount.incrementAndGet();
                        log.warn(
                                "TTS segment future failed unexpectedly. coursewareId={}, nodeId={}, pageIndex={}, progress={}/{}, reason={}",
                                coursewareId,
                                segment.nodeId(),
                                segment.pageIndex(),
                                completed,
                                queuedCount,
                                ex.getMessage()
                        );
                        return new SegmentAudioOutcome(segment, null);
                    });
            futures.add(future);
        }

        CompletableFuture.allOf(futures.toArray(CompletableFuture[]::new)).join();

        List<ScriptSegmentView> enrichedSegments = new ArrayList<>(segments.size());
        int successCount = 0;
        int failureCount = 0;

        for (CompletableFuture<SegmentAudioOutcome> future : futures) {
            SegmentAudioOutcome outcome = future.join();
            ScriptSegmentView segment = outcome.segment();
            String resolvedAudioUrl = StringUtils.hasText(outcome.audioUrl())
                    ? outcome.audioUrl()
                    : segment.audioUrl();

            if (StringUtils.hasText(resolvedAudioUrl)) {
                successCount++;
            } else {
                failureCount++;
            }

            enrichedSegments.add(new ScriptSegmentView(
                    segment.id(),
                    segment.nodeId(),
                    segment.pageIndex(),
                    segment.title(),
                    segment.content(),
                    segment.knowledgePoints(),
                    resolvedAudioUrl,
                    segment.pageImagePath(),
                    segment.pageImageUrl(),
                    segment.visualSummary(),
                    segment.visualObjects(),
                    segment.digitalHumanEnabled()
            ));
        }

        log.info(
                "TTS batch synthesis finished. coursewareId={}, totalSegments={}, queuedCount={}, reusedCount={}, successCount={}, failureCount={}",
                coursewareId,
                segments.size(),
                queuedCount,
                reusedCount,
                successCount,
                failureCount
        );
        return new TtsBatchResult(List.copyOf(enrichedSegments), successCount, failureCount);
    }

    private TtsBatchResult summarizeCurrentAudioState(List<ScriptSegmentView> segments) {
        int successCount = 0;
        int failureCount = 0;
        for (ScriptSegmentView segment : segments) {
            if (StringUtils.hasText(segment.audioUrl())) {
                successCount++;
            } else {
                failureCount++;
            }
        }
        return new TtsBatchResult(List.copyOf(segments), successCount, failureCount);
    }

    private List<ParsedSegment> buildFallbackSegments(String displayName, String originalFilename) {
        String topic = stripExtension(StringUtils.hasText(displayName) ? displayName : originalFilename);
        return List.of(
                new ParsedSegment(
                        1,
                        "课程导入",
                        "这份课件《" + topic + "》会先帮助学生建立主题背景，并说明本节课的学习目标。",
                        List.of(topic, "学习目标"),
                        null,
                        null,
                        List.of()
                ),
                new ParsedSegment(
                        2,
                        "核心概念",
                        "中间部分会围绕关键概念、典型例子和应用场景展开，帮助学生建立完整理解。",
                        List.of("核心概念", "案例分析"),
                        null,
                        null,
                        List.of()
                ),
                new ParsedSegment(
                        3,
                        "总结回顾",
                        "最后会回顾重点知识，并提示学生如何把本节内容迁移到后续练习中。",
                        List.of("知识总结", "课后迁移"),
                        null,
                        null,
                        List.of()
                )
        );
    }

    private String buildFallbackPageScript(ParsedSegment parsedSegment, int index, int totalPages) {
        String title = defaultText(parsedSegment.title(), "").trim();
        String content = defaultText(parsedSegment.content(), "本页内容正在整理中。").trim();
        if (!StringUtils.hasText(title)) {
            return content;
        }

        if (content.contains(title)) {
            return content;
        }

        return "这里重点讲“" + title + "”。 " + content;
    }

    private String buildFallbackTransition(int index, int totalPages, String nextTitle) {
        return "";
    }

    private String nextTitle(ParsedCourseware parsedCourseware, int currentIndex) {
        int nextIndex = currentIndex + 1;
        if (nextIndex >= parsedCourseware.segments().size()) {
            return null;
        }
        return parsedCourseware.segments().get(nextIndex).title();
    }

    private TaskStatus resolveScriptTaskStatus(TtsBatchResult ttsBatchResult) {
        return ttsBatchResult.failureCount() == 0
                ? TaskStatus.SUCCESS
                : TaskStatus.PARTIAL_SUCCESS;
    }

    private void markScriptReady(CoursewareState state, TaskStatus taskStatus, ScriptView scriptView) {
        markScriptReady(state, taskStatus, scriptView, Set.of());
    }

    private void markScriptReady(
            CoursewareState state,
            TaskStatus taskStatus,
            ScriptView scriptView,
            Set<String> editedSegmentIds
    ) {
        scriptStatusStore.put(state.getId(), CoursewareStatus.READY.name());
        state.setStatus(CoursewareStatus.READY.name());
        state.setCurrentTaskStatus(taskStatus.name());
        state.touch();
        persistScriptView(state, scriptView, editedSegmentIds);
    }

    private ParsedCourseware loadParsedCourseware(String coursewareId) {
        ParsedCourseware cached = parsedStore.get(coursewareId);
        if (cached != null) {
            return cached;
        }
        ParsedCourseware persisted = loadParsedCoursewareFromDatabase(coursewareId);
        if (persisted != null) {
            parsedStore.put(coursewareId, persisted);
        }
        return persisted;
    }

    private ParsedCourseware loadParsedCoursewareFromDatabase(String coursewareId) {
        if (!isPersistentMode()) {
            return null;
        }

        List<CoursewarePage> pages = coursewarePageRepository().findByCoursewareIdOrderByPageIndexAsc(coursewareId);
        if (pages.isEmpty()) {
            return null;
        }

        List<ParsedSegment> segments = pages.stream()
                .map(page -> new ParsedSegment(
                        page.getPageIndex(),
                        defaultText(page.getTitle(), "第 " + page.getPageIndex() + " 页"),
                        defaultText(page.getOriginalText(), "本页内容正在整理中。"),
                        deserializeList(page.getKnowledgePointsJson()),
                        page.getImageUrl(),
                        page.getVisualSummary(),
                        deserializeList(page.getVisualObjectsJson())
                ))
                .toList();
        return new ParsedCourseware(coursewareId, List.copyOf(segments));
    }

    private ScriptView findExistingScript(String coursewareId) {
        if (isPersistentMode()) {
            ScriptView persisted = loadScriptFromDatabase(coursewareId);
            if (persisted != null) {
                return persisted;
            }
        }
        return scriptStore.get(coursewareId);
    }

    private ScriptView loadScriptFromDatabase(String coursewareId) {
        if (!isPersistentMode()) {
            return null;
        }

        Courseware courseware = coursewareRepository().findById(coursewareId).orElse(null);
        if (courseware == null) {
            return null;
        }

        List<LectureScript> scripts = lectureScriptRepository().findByCoursewareIdOrderByPageIndexAsc(coursewareId);
        if (scripts.isEmpty()) {
            return null;
        }

        List<OutlineItemView> outline = scripts.stream()
                .map(script -> new OutlineItemView(
                        script.getId(),
                        defaultText(script.getTitle(), "第 " + script.getPageIndex() + " 页")
                ))
                .toList();

        List<ScriptSegmentView> segments = scripts.stream()
                .map(this::toSegmentView)
                .toList();

        ScriptView scriptView = new ScriptView(
                coursewareId,
                outline,
                segments,
                defaultText(courseware.getStatus(), CoursewareStatus.READY.name()),
                courseware.getScriptOpening(),
                courseware.getScriptClosing()
        );
        scriptStore.put(coursewareId, scriptView);
        return scriptView;
    }

    private ScriptSegmentView toSegmentView(LectureScript script) {
        return new ScriptSegmentView(
                script.getId(),
                script.getNodeId(),
                script.getPageIndex(),
                defaultText(script.getTitle(), "第 " + script.getPageIndex() + " 页"),
                defaultText(script.getContent(), ""),
                deserializeList(script.getKnowledgePointsJson()),
                script.getAudioUrl(),
                script.getPageImageUrl(),
                resolvePageImageAccessUrl(script.getCoursewareId(), script.getPageIndex(), script.getPageImageUrl()),
                script.getVisualSummary(),
                deserializeList(script.getVisualObjectsJson()),
                Boolean.TRUE.equals(script.getDigitalHumanEnabled())
        );
    }

    private void persistParsedCourseware(CoursewareState state, ParsedCourseware parsedCourseware) {
        if (!isPersistentMode()) {
            return;
        }

        CoursewarePageRepository pageRepository = coursewarePageRepository();
        pageRepository.deleteByCoursewareId(state.getId());

        List<CoursewarePage> pages = new ArrayList<>();
        for (ParsedSegment segment : parsedCourseware.segments()) {
            CoursewarePage page = new CoursewarePage();
            page.setCoursewareId(state.getId());
            page.setPageIndex(segment.pageIndex());
            page.setTitle(segment.title());
            page.setOriginalText(segment.content());
            page.setKnowledgePointsJson(serializeList(segment.knowledgePoints()));
            page.setImageUrl(segment.pageImagePath());
            page.setVisualSummary(segment.visualSummary());
            page.setVisualObjectsJson(serializeList(segment.visualObjects()));
            pages.add(page);
        }

        pageRepository.saveAll(pages);
        persistCoursewareState(state);
    }

    private void persistScriptView(CoursewareState state, ScriptView scriptView) {
        persistScriptView(state, scriptView, Set.of());
    }

    private void persistScriptView(CoursewareState state, ScriptView scriptView, Set<String> editedSegmentIds) {
        if (!isPersistentMode()) {
            return;
        }

        LectureScriptRepository scriptRepository = lectureScriptRepository();
        List<LectureScript> existingScripts = scriptRepository.findByCoursewareIdOrderByPageIndexAsc(state.getId());
        Map<String, String> existingEditStatus = existingScripts.stream()
                .collect(java.util.stream.Collectors.toMap(
                        LectureScript::getNodeId,
                        script -> defaultText(script.getEditStatus(), "AUTO"),
                        (left, right) -> right
                ));

        scriptRepository.deleteByCoursewareId(state.getId());

        List<LectureScript> scripts = new ArrayList<>();
        for (ScriptSegmentView segment : scriptView.segments()) {
            LectureScript script = new LectureScript();
            script.setId(StringUtils.hasText(segment.id())
                    ? segment.id()
                    : "script_" + UUID.randomUUID().toString().replace("-", ""));
            script.setCoursewareId(state.getId());
            script.setPageIndex(segment.pageIndex());
            script.setNodeId(segment.nodeId());
            script.setTitle(segment.title());
            script.setContent(segment.content());
            script.setKnowledgePointsJson(serializeList(segment.knowledgePoints()));
            script.setAudioUrl(segment.audioUrl());
            script.setPageImageUrl(segment.pageImagePath());
            script.setVisualSummary(segment.visualSummary());
            script.setVisualObjectsJson(serializeList(segment.visualObjects()));
            script.setDigitalHumanEnabled(segment.digitalHumanEnabled());
            script.setEditStatus(editedSegmentIds.contains(segment.id())
                    ? "EDITED"
                    : existingEditStatus.getOrDefault(segment.nodeId(), "AUTO"));
            scripts.add(script);
        }

        scriptRepository.saveAll(scripts);

        Courseware courseware = coursewareRepository().findById(state.getId()).orElseGet(Courseware::new);
        applyStateToCourseware(courseware, state);
        courseware.setScriptOpening(scriptView.opening());
        courseware.setScriptClosing(scriptView.closing());
        coursewareRepository().save(courseware);
    }

    private void persistCoursewareState(CoursewareState state) {
        if (!isPersistentMode()) {
            return;
        }

        Courseware courseware = coursewareRepository().findById(state.getId()).orElseGet(Courseware::new);
        applyStateToCourseware(courseware, state);
        coursewareRepository().save(courseware);
    }

    private void applyStateToCourseware(Courseware courseware, CoursewareState state) {
        courseware.setId(state.getId());
        courseware.setName(state.getName());
        courseware.setFileUrl(state.getStorageKey());
        courseware.setStorageType(defaultText(state.getStorageType(), "local"));
        courseware.setOriginalFilename(state.getOriginalFilename());
        courseware.setFileType(state.getFileType());
        courseware.setStatus(state.getStatus());
        courseware.setCurrentTaskStatus(state.getCurrentTaskStatus());
    }

    private CoursewareState requireCourseware(String coursewareId) {
        ensureCoursewareId(coursewareId);

        CoursewareState cached = coursewareStore.get(coursewareId);
        if (cached != null) {
            return cached;
        }

        if (isPersistentMode()) {
            Courseware courseware = requirePersistedCourseware(coursewareId);
            CoursewareState state = CoursewareState.fromEntity(courseware);
            coursewareStore.put(coursewareId, state);
            return state;
        }

        throw new NoSuchElementException("Courseware not found");
    }

    private Courseware requirePersistedCourseware(String coursewareId) {
        return coursewareRepository().findById(coursewareId)
                .orElseThrow(() -> new NoSuchElementException("Courseware not found"));
    }

    private CoursewareListItem toListItem(Courseware courseware) {
        return new CoursewareListItem(
                courseware.getId(),
                courseware.getName(),
                courseware.getStatus(),
                textOf(courseware.getCreateTime()),
                courseware.getCurrentTaskStatus()
        );
    }

    private CoursewareDetailView toDetailView(Courseware courseware) {
        return new CoursewareDetailView(
                courseware.getId(),
                courseware.getName(),
                courseware.getStatus(),
                courseware.getCurrentTaskStatus(),
                courseware.getFileType(),
                textOf(courseware.getCreateTime()),
                textOf(courseware.getUpdateTime())
        );
    }

    private boolean isPersistentMode() {
        return coursewareRepositoryProvider.getIfAvailable() != null
                && coursewarePageRepositoryProvider.getIfAvailable() != null
                && lectureScriptRepositoryProvider.getIfAvailable() != null;
    }

    private CoursewareRepository coursewareRepository() {
        CoursewareRepository repository = coursewareRepositoryProvider.getIfAvailable();
        if (repository == null) {
            throw new IllegalStateException("CoursewareRepository is unavailable in the current profile");
        }
        return repository;
    }

    private CoursewarePageRepository coursewarePageRepository() {
        CoursewarePageRepository repository = coursewarePageRepositoryProvider.getIfAvailable();
        if (repository == null) {
            throw new IllegalStateException("CoursewarePageRepository is unavailable in the current profile");
        }
        return repository;
    }

    private LectureScriptRepository lectureScriptRepository() {
        LectureScriptRepository repository = lectureScriptRepositoryProvider.getIfAvailable();
        if (repository == null) {
            throw new IllegalStateException("LectureScriptRepository is unavailable in the current profile");
        }
        return repository;
    }

    private String serializeList(List<String> values) {
        if (values == null || values.isEmpty()) {
            return null;
        }
        try {
            return objectMapper.writeValueAsString(values);
        } catch (Exception ex) {
            throw new IllegalStateException("Failed to serialize JSON list", ex);
        }
    }

    private List<String> deserializeList(String rawValue) {
        if (!StringUtils.hasText(rawValue)) {
            return List.of();
        }
        try {
            return List.copyOf(objectMapper.readValue(rawValue, STRING_LIST_TYPE));
        } catch (Exception ex) {
            log.warn("Failed to deserialize JSON list. rawValue={}", rawValue);
            return List.of();
        }
    }

    private String newCoursewareId() {
        return "cware_" + UUID.randomUUID().toString().replace("-", "");
    }

    private void ensureCoursewareId(String coursewareId) {
        if (!StringUtils.hasText(coursewareId)) {
            throw new IllegalArgumentException("coursewareId must not be blank");
        }
    }

    private String resolveDisplayName(String requestedName, String filename) {
        if (StringUtils.hasText(requestedName)) {
            return requestedName.trim();
        }
        return stripExtension(filename);
    }

    private String normalizeFilename(String originalFilename) {
        if (!StringUtils.hasText(originalFilename)) {
            return "courseware.bin";
        }

        String filename = originalFilename.replace('\u0000', ' ').trim().replace('\\', '/');
        int lastSlash = filename.lastIndexOf('/');
        if (lastSlash >= 0) {
            filename = filename.substring(lastSlash + 1);
        }
        return StringUtils.hasText(filename) ? filename : "courseware.bin";
    }

    private String stripExtension(String filename) {
        if (!StringUtils.hasText(filename)) {
            return "未命名课件";
        }

        int dotIndex = filename.lastIndexOf('.');
        return dotIndex > 0 ? filename.substring(0, dotIndex) : filename;
    }

    private String defaultText(String text, String fallback) {
        return StringUtils.hasText(text) ? text.trim() : fallback;
    }

    private String resolvePageImageAccessUrl(String coursewareId, int pageIndex, String pageImagePath) {
        if (!StringUtils.hasText(pageImagePath)) {
            return null;
        }
        if (isHttpUrl(pageImagePath)) {
            return pageImagePath;
        }
        return "/api/v1/courseware/%s/pages/%s/image".formatted(coursewareId, pageIndex);
    }

    private boolean isHttpUrl(String value) {
        if (!StringUtils.hasText(value)) {
            return false;
        }
        String normalized = value.trim().toLowerCase(Locale.ROOT);
        return normalized.startsWith("http://") || normalized.startsWith("https://");
    }

    private String textOf(LocalDateTime dateTime) {
        return dateTime == null ? null : dateTime.toString();
    }

    private MediaType resolveMediaType(Path file) {
        try {
            return MediaType.parseMediaType(probeContentType(file));
        } catch (Exception ignored) {
            return MediaType.APPLICATION_OCTET_STREAM;
        }
    }

    private String probeContentType(Path path) {
        try {
            String detected = Files.probeContentType(path);
            if (StringUtils.hasText(detected)) {
                return detected;
            }
        } catch (Exception ignored) {
            // fall through to extension-based detection
        }

        String lowerName = path.getFileName().toString().toLowerCase(Locale.ROOT);
        if (lowerName.endsWith(".pdf")) {
            return "application/pdf";
        }
        if (lowerName.endsWith(".pptx")) {
            return "application/vnd.openxmlformats-officedocument.presentationml.presentation";
        }
        if (lowerName.endsWith(".ppt")) {
            return "application/vnd.ms-powerpoint";
        }
        if (lowerName.endsWith(".png")) {
            return "image/png";
        }
        if (lowerName.endsWith(".jpg") || lowerName.endsWith(".jpeg")) {
            return "image/jpeg";
        }
        if (lowerName.endsWith(".webp")) {
            return "image/webp";
        }
        return "application/octet-stream";
    }

    private static Instant toInstant(LocalDateTime time) {
        if (time == null) {
            return Instant.now();
        }
        return time.atZone(ZoneId.systemDefault()).toInstant();
    }

    public record PageMediaResource(Resource resource, MediaType mediaType) {
    }

    private static final class PathMultipartFile implements MultipartFile {
        private final Path sourcePath;
        private final String originalFilename;
        private final String contentType;

        private PathMultipartFile(Path sourcePath, String originalFilename, String contentType) {
            this.sourcePath = sourcePath;
            this.originalFilename = originalFilename;
            this.contentType = contentType;
        }

        @Override
        public String getName() {
            return originalFilename;
        }

        @Override
        public String getOriginalFilename() {
            return originalFilename;
        }

        @Override
        public String getContentType() {
            return contentType;
        }

        @Override
        public boolean isEmpty() {
            try {
                return Files.size(sourcePath) <= 0;
            } catch (IOException ex) {
                return true;
            }
        }

        @Override
        public long getSize() {
            try {
                return Files.size(sourcePath);
            } catch (IOException ex) {
                throw new IllegalStateException("Failed to read file size for imported courseware", ex);
            }
        }

        @Override
        public byte[] getBytes() throws IOException {
            return Files.readAllBytes(sourcePath);
        }

        @Override
        public InputStream getInputStream() throws IOException {
            return Files.newInputStream(sourcePath);
        }

        @Override
        public void transferTo(File dest) throws IOException {
            Path targetPath = dest.toPath().toAbsolutePath().normalize();
            Path parent = targetPath.getParent();
            if (parent != null) {
                Files.createDirectories(parent);
            }
            Files.copy(sourcePath, targetPath, StandardCopyOption.REPLACE_EXISTING);
        }
    }

    private record ParsedCourseware(String coursewareId, List<ParsedSegment> segments) {
    }

    private record ParsedSegment(
            int pageIndex,
            String title,
            String content,
            List<String> knowledgePoints,
            String pageImagePath,
            String visualSummary,
            List<String> visualObjects
    ) {
    }

    private record GeneratedScriptDraft(String opening, List<GeneratedPage> pages, String closing) {
    }

    private record GeneratedPage(int pageIndex, String script, String transition) {
    }

    public record QaIngestPage(
            int pageIndex,
            String title,
            String content,
            List<String> knowledgePoints,
            String pageImagePath,
            String visualSummary,
            List<String> visualObjects
    ) {
    }

    private record TtsBatchResult(List<ScriptSegmentView> segments, int successCount, int failureCount) {
    }

    private record SegmentAudioOutcome(ScriptSegmentView segment, String audioUrl) {
    }

    @Getter
    private static final class CoursewareState {
        private final String id;
        private final String name;
        private final String originalFilename;
        private final String storageKey;
        private final String storageType;
        private final String fileType;
        private final Instant createdAt;
        private volatile Instant updatedAt;
        private volatile String status;
        private volatile String currentTaskStatus;

        private CoursewareState(
                String id,
                String name,
                String originalFilename,
                String storageKey,
                String storageType,
                String fileType
        ) {
            this(
                    id,
                    name,
                    originalFilename,
                    storageKey,
                    storageType,
                    fileType,
                    Instant.now(),
                    Instant.now(),
                    CoursewareStatus.UPLOADED.name(),
                    TaskStatus.PENDING.name()
            );
        }

        private CoursewareState(
                String id,
                String name,
                String originalFilename,
                String storageKey,
                String storageType,
                String fileType,
                Instant createdAt,
                Instant updatedAt,
                String status,
                String currentTaskStatus
        ) {
            this.id = id;
            this.name = name;
            this.originalFilename = originalFilename;
            this.storageKey = storageKey;
            this.storageType = storageType;
            this.fileType = StringUtils.hasText(fileType)
                    ? fileType.toUpperCase(Locale.ROOT)
                    : "APPLICATION/OCTET-STREAM";
            this.createdAt = createdAt;
            this.updatedAt = updatedAt;
            this.status = status;
            this.currentTaskStatus = currentTaskStatus;
        }

        private static CoursewareState fromEntity(Courseware courseware) {
            return new CoursewareState(
                    courseware.getId(),
                    courseware.getName(),
                    courseware.getOriginalFilename(),
                    courseware.getFileUrl(),
                    courseware.getStorageType(),
                    courseware.getFileType(),
                    toInstant(courseware.getCreateTime()),
                    toInstant(courseware.getUpdateTime()),
                    courseware.getStatus(),
                    courseware.getCurrentTaskStatus()
            );
        }

        private void setStatus(String status) {
            this.status = status;
        }

        private void setCurrentTaskStatus(String currentTaskStatus) {
            this.currentTaskStatus = currentTaskStatus;
        }

        private void touch() {
            this.updatedAt = Instant.now();
        }
    }
}
