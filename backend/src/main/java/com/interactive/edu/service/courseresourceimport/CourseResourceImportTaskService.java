package com.interactive.edu.service.courseresourceimport;

import com.interactive.edu.config.StorageProperties;
import com.interactive.edu.dto.CoursewareUploadResult;
import com.interactive.edu.dto.courseresourceimport.CreateCourseResourceImportTaskRequest;
import com.interactive.edu.enums.CourseResourceImportTaskStatus;
import com.interactive.edu.exception.BusinessException;
import com.interactive.edu.exception.ErrorCode;
import com.interactive.edu.exception.ServiceException;
import com.interactive.edu.service.courseware.CoursewareService;
import com.interactive.edu.service.python.PythonCourseResourceImportClient;
import com.interactive.edu.service.python.PythonCourseResourceImportRequest;
import com.interactive.edu.vo.courseresourceimport.CourseResourceImportTaskCreateView;
import com.interactive.edu.vo.courseresourceimport.CourseResourceImportTaskFileItemView;
import com.interactive.edu.vo.courseresourceimport.CourseResourceImportTaskFilesView;
import com.interactive.edu.vo.courseresourceimport.CourseResourceImportTaskView;
import lombok.Getter;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.core.task.TaskExecutor;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;

import java.net.URI;
import java.net.URISyntaxException;
import java.nio.file.Path;
import java.time.Instant;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.NoSuchElementException;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ConcurrentMap;

@Service
@RequiredArgsConstructor
@Slf4j
public class CourseResourceImportTaskService {

    private static final String SOURCE_TYPE_CHAOXING_COURSE = "CHAOXING_COURSE";

    private final PythonCourseResourceImportClient pythonCourseResourceImportClient;
    private final CoursewareService coursewareService;
    private final StorageProperties storageProperties;
    @Qualifier("taskExecutor")
    private final TaskExecutor taskExecutor;

    private final ConcurrentMap<String, TaskState> taskStore = new ConcurrentHashMap<>();
    private final ConcurrentMap<String, TaskSecrets> taskSecretsStore = new ConcurrentHashMap<>();

    public CourseResourceImportTaskCreateView createTask(CreateCourseResourceImportTaskRequest request, String userId) {
        ImportCommand command = normalizeAndValidate(request);
        String taskId = "import_" + UUID.randomUUID().toString().replace("-", "");
        String ownerUserId = resolveUserId(userId);
        Path outputDir = importRoot().resolve(taskId).toAbsolutePath().normalize();

        TaskState state = new TaskState(taskId, ownerUserId, command.toRedactedSummary(), outputDir);
        taskStore.put(taskId, state);
        taskSecretsStore.put(taskId, new TaskSecrets(command.cookie(), command.authorization(), command.referer()));
        log.info("Course-resource import task created. taskId={}, userId={}, sourceType={}", taskId, ownerUserId, command.sourceType());

        taskExecutor.execute(() -> runTask(state, command));
        return new CourseResourceImportTaskCreateView(taskId, state.getStatus().name());
    }

    public CourseResourceImportTaskView getTask(String taskId, String userId) {
        TaskState state = requireOwnedTask(taskId, userId);
        return toTaskView(state);
    }

    public CourseResourceImportTaskFilesView getFiles(String taskId, String userId) {
        TaskState state = requireOwnedTask(taskId, userId);
        return new CourseResourceImportTaskFilesView(List.copyOf(state.getFiles()));
    }

    public CourseResourceImportTaskView retry(String taskId, String userId) {
        TaskState state = requireOwnedTask(taskId, userId);
        if (state.getStatus() != CourseResourceImportTaskStatus.FAILED
                && state.getStatus() != CourseResourceImportTaskStatus.CANCELLED) {
            throw new IllegalStateException("Only failed or cancelled tasks can be retried");
        }

        TaskSecrets secrets = taskSecretsStore.get(taskId);
        if (secrets == null) {
            throw new IllegalStateException("Retry is unavailable because the original credentials are no longer present");
        }

        ImportCommand command = state.getCommandSummary().restore(secrets);
        state.resetForRetry();
        taskExecutor.execute(() -> runTask(state, command));
        return toTaskView(state);
    }

    public CourseResourceImportTaskView cancel(String taskId, String userId) {
        TaskState state = requireOwnedTask(taskId, userId);
        if (state.isTerminal()) {
            return toTaskView(state);
        }
        state.setCancelRequested(true);
        state.setStatus(CourseResourceImportTaskStatus.CANCELLED);
        state.setProgress(progressOf(CourseResourceImportTaskStatus.CANCELLED));
        state.setMessage("Import task cancelled");
        state.touch();
        return toTaskView(state);
    }

    private void runTask(TaskState state, ImportCommand command) {
        try {
            updateStage(state, CourseResourceImportTaskStatus.FETCHING, "Fetching authorized course page");
            checkCancelled(state);

            updateStage(state, CourseResourceImportTaskStatus.DISCOVERING, "Discovering courseware resources");
            checkCancelled(state);

            updateStage(state, CourseResourceImportTaskStatus.CLASSIFYING, "Classifying courseware resources");
            checkCancelled(state);

            updateStage(state, CourseResourceImportTaskStatus.DOWNLOADING, "Downloading courseware resources");
            PythonCourseResourceImportClient.ImportExecutionResult importResult = pythonCourseResourceImportClient.executeImport(
                    state.getTaskId(),
                    PythonCourseResourceImportRequest.builder()
                            .sourceType(command.sourceType())
                            .url(command.url())
                            .courseid(command.courseid())
                            .clazzid(command.clazzid())
                            .cpi(command.cpi())
                            .enc(command.enc())
                            .cookie(command.cookie())
                            .authorization(command.authorization())
                            .referer(command.referer())
                            .buildPdf(command.buildPdf())
                            .autoParse(command.autoParse())
                            .outputDir(state.getOutputDir())
                            .build()
            );

            checkCancelled(state);
            state.setDiscoveredCount(importResult.getDiscoveredCount());
            state.setSelectedCount(importResult.getSelectedCount());
            state.setDownloadedCount(importResult.getDownloadedCount());
            state.setIgnoredCount(importResult.getIgnoredCount());
            state.setGeneratedPdf(importResult.getGeneratedPdf());
            state.setFiles(toFileViews(importResult.getFiles()));
            state.touch();

            if (StringUtils.hasText(importResult.getGeneratedPdf())) {
                updateStage(state, CourseResourceImportTaskStatus.BUILDING_PDF, "Building PDF from slide images");
                checkCancelled(state);
            }

            if (command.autoParse()) {
                updateStage(state, CourseResourceImportTaskStatus.PARSING, "Triggering existing courseware parse flow");
                checkCancelled(state);

                Path parseReadyFile = pickPreferredParseReadyFile(importResult);
                if (parseReadyFile == null) {
                    state.setStatus(CourseResourceImportTaskStatus.READY);
                    state.setProgress(progressOf(CourseResourceImportTaskStatus.READY));
                    state.setMessage("Import completed. TODO: no parse-ready .pdf or .pptx file is available for auto-parse.");
                    state.touch();
                    return;
                }

                CoursewareUploadResult uploadResult = coursewareService.importLocalFile(
                        parseReadyFile,
                        parseReadyFile.getFileName().toString()
                );
                state.setCoursewareId(uploadResult.getCoursewareId());
                state.setStatus(CourseResourceImportTaskStatus.READY);
                state.setProgress(progressOf(CourseResourceImportTaskStatus.READY));
                state.setMessage("Import completed and existing courseware parse was triggered");
                state.touch();
                return;
            }

            state.setStatus(CourseResourceImportTaskStatus.READY);
            state.setProgress(progressOf(CourseResourceImportTaskStatus.READY));
            state.setMessage("Import completed");
            state.touch();
        } catch (TaskCancelledException ex) {
            state.setStatus(CourseResourceImportTaskStatus.CANCELLED);
            state.setProgress(progressOf(CourseResourceImportTaskStatus.CANCELLED));
            state.setMessage("Import task cancelled");
            state.touch();
        } catch (ServiceException ex) {
            state.setStatus(CourseResourceImportTaskStatus.FAILED);
            state.setProgress(progressOf(CourseResourceImportTaskStatus.FAILED));
            state.setMessage(ex.getFriendlyMessage());
            state.touch();
            throw ex;
        } catch (Exception ex) {
            if (state.isCancelRequested()) {
                state.setStatus(CourseResourceImportTaskStatus.CANCELLED);
                state.setProgress(progressOf(CourseResourceImportTaskStatus.CANCELLED));
                state.setMessage("Import task cancelled");
                state.touch();
                return;
            }
            log.error("Course-resource import task failed. taskId={}", state.getTaskId(), ex);
            state.setStatus(CourseResourceImportTaskStatus.FAILED);
            state.setProgress(progressOf(CourseResourceImportTaskStatus.FAILED));
            state.setMessage(ex.getMessage());
            state.touch();
        }
    }

    private TaskState requireOwnedTask(String taskId, String userId) {
        TaskState state = taskStore.get(taskId);
        if (state == null) {
            throw new NoSuchElementException("Course-resource import task not found");
        }
        String ownerUserId = resolveUserId(userId);
        if (!state.getUserId().equals(ownerUserId)) {
            throw new BusinessException(ErrorCode.FORBIDDEN, "You are not allowed to access this import task");
        }
        return state;
    }

    private void updateStage(TaskState state, CourseResourceImportTaskStatus status, String message) {
        state.setStatus(status);
        state.setProgress(progressOf(status));
        state.setMessage(message);
        state.touch();
    }

    private void checkCancelled(TaskState state) {
        if (state.isCancelRequested()) {
            state.setStatus(CourseResourceImportTaskStatus.CANCELLED);
            state.setProgress(progressOf(CourseResourceImportTaskStatus.CANCELLED));
            state.setMessage("Import task cancelled");
            state.touch();
            throw new TaskCancelledException();
        }
    }

    private CourseResourceImportTaskView toTaskView(TaskState state) {
        return new CourseResourceImportTaskView(
                state.getTaskId(),
                state.getStatus().name(),
                state.getProgress(),
                state.getDiscoveredCount(),
                state.getSelectedCount(),
                state.getDownloadedCount(),
                state.getIgnoredCount(),
                state.getGeneratedPdf(),
                state.getMessage(),
                state.getCoursewareId()
        );
    }

    private List<CourseResourceImportTaskFileItemView> toFileViews(List<PythonCourseResourceImportClient.ImportFileResult> files) {
        List<CourseResourceImportTaskFileItemView> items = new ArrayList<>();
        for (PythonCourseResourceImportClient.ImportFileResult file : files) {
            items.add(new CourseResourceImportTaskFileItemView(
                    file.getFileName(),
                    file.getResourceKind(),
                    file.getStatus(),
                    file.getLocalPath(),
                    file.getConfidence(),
                    file.getReason()
            ));
        }
        return List.copyOf(items);
    }

    private Path pickPreferredParseReadyFile(PythonCourseResourceImportClient.ImportExecutionResult importResult) {
        Path parseReadyManifest = Path.of(importResult.getParseReadyManifest()).toAbsolutePath().normalize();
        try {
            List<Map<?, ?>> items = List.of();
            // The mock client already writes parse_ready_manifest.json. Keep parsing lightweight here.
            String json = java.nio.file.Files.readString(parseReadyManifest);
            com.fasterxml.jackson.databind.JsonNode root = new ObjectMapperHolder().readTree(json);
            com.fasterxml.jackson.databind.JsonNode parseReadyFiles = root.path("parse_ready_files");
            if (!parseReadyFiles.isArray()) {
                return null;
            }
            List<Path> candidates = new ArrayList<>();
            for (com.fasterxml.jackson.databind.JsonNode node : parseReadyFiles) {
                String rawPath = node.path("path").asText("");
                if (!StringUtils.hasText(rawPath)) {
                    continue;
                }
                Path file = Path.of(rawPath).toAbsolutePath().normalize();
                String suffix = file.getFileName().toString().toLowerCase(Locale.ROOT);
                if (suffix.endsWith(".pdf") || suffix.endsWith(".pptx")) {
                    candidates.add(file);
                }
            }
            return candidates.stream()
                    .sorted(Comparator.comparingInt(this::parsePriority))
                    .findFirst()
                    .orElse(null);
        } catch (Exception ex) {
            throw new ServiceException(ErrorCode.PYTHON_SERVICE_ERROR, "Failed to read parse_ready_manifest.json", ex);
        }
    }

    private int parsePriority(Path path) {
        String name = path.getFileName().toString().toLowerCase(Locale.ROOT);
        if (name.endsWith(".pdf") && !name.contains("courseware_from_images")) {
            return 0;
        }
        if (name.endsWith(".pptx")) {
            return 1;
        }
        if (name.endsWith(".pdf")) {
            return 2;
        }
        return 10;
    }

    private int progressOf(CourseResourceImportTaskStatus status) {
        return switch (status) {
            case PENDING -> 0;
            case FETCHING -> 10;
            case DISCOVERING -> 20;
            case CLASSIFYING -> 35;
            case DOWNLOADING -> 60;
            case BUILDING_PDF -> 80;
            case PARSING -> 90;
            case READY -> 100;
            case FAILED, CANCELLED -> 100;
        };
    }

    private ImportCommand normalizeAndValidate(CreateCourseResourceImportTaskRequest request) {
        if (request == null) {
            throw new IllegalArgumentException("Request body must not be null");
        }
        if (!SOURCE_TYPE_CHAOXING_COURSE.equalsIgnoreCase(request.getSourceType())) {
            throw new IllegalArgumentException("Only CHAOXING_COURSE sourceType is supported");
        }
        if (!StringUtils.hasText(request.getCookie()) && !StringUtils.hasText(request.getAuthorization())) {
            throw new IllegalArgumentException("Either cookie or authorization must be provided");
        }

        String url = StringUtils.hasText(request.getUrl()) ? request.getUrl().trim() : null;
        String courseid = StringUtils.hasText(request.getCourseid()) ? request.getCourseid().trim() : null;
        String clazzid = StringUtils.hasText(request.getClazzid()) ? request.getClazzid().trim() : null;
        String cpi = StringUtils.hasText(request.getCpi()) ? request.getCpi().trim() : null;
        String enc = StringUtils.hasText(request.getEnc()) ? request.getEnc().trim() : null;

        if (!StringUtils.hasText(url) && !StringUtils.hasText(courseid)) {
            throw new IllegalArgumentException("Either url or courseid must be provided");
        }

        String resolvedUrl = url;
        if (StringUtils.hasText(url)) {
            validateChaoxingUrl(url);
        } else {
            resolvedUrl = buildCourseUrl(courseid, clazzid, cpi, enc);
            validateChaoxingUrl(resolvedUrl);
        }

        return new ImportCommand(
                SOURCE_TYPE_CHAOXING_COURSE,
                resolvedUrl,
                courseid,
                clazzid,
                cpi,
                enc,
                request.getCookie(),
                request.getAuthorization(),
                StringUtils.hasText(request.getReferer()) ? request.getReferer().trim() : resolvedUrl,
                Boolean.TRUE.equals(request.getBuildPdf()),
                Boolean.TRUE.equals(request.getAutoParse())
        );
    }

    private void validateChaoxingUrl(String rawUrl) {
        try {
            URI uri = new URI(rawUrl);
            String scheme = uri.getScheme();
            String host = uri.getHost();
            if (!StringUtils.hasText(scheme) || (!"http".equalsIgnoreCase(scheme) && !"https".equalsIgnoreCase(scheme))) {
                throw new IllegalArgumentException("Only http/https URLs are allowed");
            }
            if (!isAllowedChaoxingHost(host)) {
                throw new IllegalArgumentException("Only chaoxing.com URLs are allowed");
            }
        } catch (URISyntaxException ex) {
            throw new IllegalArgumentException("Invalid course URL", ex);
        }
    }

    private boolean isAllowedChaoxingHost(String host) {
        if (!StringUtils.hasText(host)) {
            return false;
        }
        String normalized = host.toLowerCase(Locale.ROOT).replaceAll("\\.+$", "");
        return "chaoxing.com".equals(normalized) || normalized.endsWith(".chaoxing.com");
    }

    private String buildCourseUrl(String courseid, String clazzid, String cpi, String enc) {
        StringBuilder builder = new StringBuilder("https://mooc2-ans.chaoxing.com/mooc2-ans/mycourse/stu?courseid=")
                .append(courseid);
        if (StringUtils.hasText(clazzid)) {
            builder.append("&clazzid=").append(clazzid);
        }
        if (StringUtils.hasText(cpi)) {
            builder.append("&cpi=").append(cpi);
        }
        if (StringUtils.hasText(enc)) {
            builder.append("&enc=").append(enc);
        }
        builder.append("&pageHeader=0&v=0&hideHead=0");
        return builder.toString();
    }

    private Path importRoot() {
        Path localBaseDir = Path.of(storageProperties.getLocalBaseDir()).toAbsolutePath().normalize();
        Path dataDir = localBaseDir.getParent() == null ? localBaseDir : localBaseDir.getParent();
        return dataDir.resolve("course-resource-import");
    }

    private String resolveUserId(String userId) {
        return StringUtils.hasText(userId) ? userId.trim() : "demo_user";
    }

    private record ImportCommand(
            String sourceType,
            String url,
            String courseid,
            String clazzid,
            String cpi,
            String enc,
            String cookie,
            String authorization,
            String referer,
            boolean buildPdf,
            boolean autoParse
    ) {
        private CommandSummary toRedactedSummary() {
            return new CommandSummary(sourceType, url, courseid, clazzid, cpi, enc, referer, buildPdf, autoParse);
        }
    }

    private record CommandSummary(
            String sourceType,
            String url,
            String courseid,
            String clazzid,
            String cpi,
            String enc,
            String referer,
            boolean buildPdf,
            boolean autoParse
    ) {
        private ImportCommand restore(TaskSecrets secrets) {
            return new ImportCommand(
                    sourceType,
                    url,
                    courseid,
                    clazzid,
                    cpi,
                    enc,
                    secrets.cookie(),
                    secrets.authorization(),
                    StringUtils.hasText(secrets.referer()) ? secrets.referer() : referer,
                    buildPdf,
                    autoParse
            );
        }
    }

    private record TaskSecrets(String cookie, String authorization, String referer) {
    }

    @Getter
    private static final class TaskState {
        private final String taskId;
        private final String userId;
        private final CommandSummary commandSummary;
        private final Path outputDir;
        private final Instant createdAt = Instant.now();
        private volatile Instant updatedAt = createdAt;
        private volatile CourseResourceImportTaskStatus status = CourseResourceImportTaskStatus.PENDING;
        private volatile int progress = 0;
        private volatile int discoveredCount = 0;
        private volatile int selectedCount = 0;
        private volatile int downloadedCount = 0;
        private volatile int ignoredCount = 0;
        private volatile String generatedPdf;
        private volatile String message = "Task pending";
        private volatile String coursewareId;
        private volatile boolean cancelRequested = false;
        private volatile List<CourseResourceImportTaskFileItemView> files = List.of();

        private TaskState(String taskId, String userId, CommandSummary commandSummary, Path outputDir) {
            this.taskId = taskId;
            this.userId = userId;
            this.commandSummary = commandSummary;
            this.outputDir = outputDir;
        }

        private boolean isTerminal() {
            return status == CourseResourceImportTaskStatus.READY
                    || status == CourseResourceImportTaskStatus.FAILED
                    || status == CourseResourceImportTaskStatus.CANCELLED;
        }

        private void resetForRetry() {
            this.status = CourseResourceImportTaskStatus.PENDING;
            this.progress = 0;
            this.discoveredCount = 0;
            this.selectedCount = 0;
            this.downloadedCount = 0;
            this.ignoredCount = 0;
            this.generatedPdf = null;
            this.message = "Task pending";
            this.coursewareId = null;
            this.cancelRequested = false;
            this.files = List.of();
            touch();
        }

        private void setStatus(CourseResourceImportTaskStatus status) {
            this.status = status;
        }

        private void setProgress(int progress) {
            this.progress = progress;
        }

        private void setDiscoveredCount(int discoveredCount) {
            this.discoveredCount = discoveredCount;
        }

        private void setSelectedCount(int selectedCount) {
            this.selectedCount = selectedCount;
        }

        private void setDownloadedCount(int downloadedCount) {
            this.downloadedCount = downloadedCount;
        }

        private void setIgnoredCount(int ignoredCount) {
            this.ignoredCount = ignoredCount;
        }

        private void setGeneratedPdf(String generatedPdf) {
            this.generatedPdf = generatedPdf;
        }

        private void setMessage(String message) {
            this.message = message;
        }

        private void setCoursewareId(String coursewareId) {
            this.coursewareId = coursewareId;
        }

        private void setCancelRequested(boolean cancelRequested) {
            this.cancelRequested = cancelRequested;
        }

        private void setFiles(List<CourseResourceImportTaskFileItemView> files) {
            this.files = files;
        }

        private void touch() {
            this.updatedAt = Instant.now();
        }
    }

    private static final class ObjectMapperHolder extends com.fasterxml.jackson.databind.ObjectMapper {
    }

    private static final class TaskCancelledException extends RuntimeException {
    }
}
