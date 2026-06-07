package com.interactive.edu.service.imports;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.interactive.edu.config.StorageProperties;
import com.interactive.edu.dto.CoursewareUploadResult;
import com.interactive.edu.entity.ChaoxingImportTaskEntity;
import com.interactive.edu.entity.ChaoxingResourceEntity;
import com.interactive.edu.enums.UnifiedTaskStatus;
import com.interactive.edu.exception.BusinessException;
import com.interactive.edu.exception.ErrorCode;
import com.interactive.edu.model.task.TaskStatePayload;
import com.interactive.edu.repository.ChaoxingImportTaskRepository;
import com.interactive.edu.repository.ChaoxingResourceRepository;
import com.interactive.edu.service.courseware.CoursewareService;
import com.interactive.edu.service.python.PythonCourseResourceImportClient;
import com.interactive.edu.service.python.PythonCourseResourceImportRequest;
import com.interactive.edu.service.task.TaskStateStore;
import com.interactive.edu.vo.imports.ChaoxingCoursewareBindView;
import com.interactive.edu.vo.imports.ChaoxingImportTaskView;
import com.interactive.edu.vo.imports.ChaoxingResourceView;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.core.task.TaskExecutor;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Instant;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.NoSuchElementException;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ConcurrentMap;

@Service
@RequiredArgsConstructor
@Slf4j
public class ChaoxingImportTaskService {

    private final PythonCourseResourceImportClient pythonCourseResourceImportClient;
    private final CoursewareService coursewareService;
    private final StorageProperties storageProperties;
    private final TaskStateStore taskStateStore;
    private final ObjectMapper objectMapper;
    @Qualifier("taskExecutor")
    private final TaskExecutor taskExecutor;
    private final ObjectProvider<ChaoxingImportTaskRepository> taskRepositoryProvider;
    private final ObjectProvider<ChaoxingResourceRepository> resourceRepositoryProvider;

    private final ConcurrentMap<String, ChaoxingImportTaskEntity> runtimeTaskStore = new ConcurrentHashMap<>();
    private final ConcurrentMap<String, List<ChaoxingResourceEntity>> runtimeResourceStore = new ConcurrentHashMap<>();

    public ChaoxingImportTaskView createTask(CreateRequest request, String userId) {
        validateCreateRequest(request);
        String taskId = "import_" + UUID.randomUUID().toString().replace("-", "");
        Path outputDir = importRoot().resolve(taskId).toAbsolutePath().normalize();
        String ownerUserId = StringUtils.hasText(userId) ? userId.trim() : "demo_user";

        ChaoxingImportTaskEntity entity = new ChaoxingImportTaskEntity();
        entity.setId(taskId);
        entity.setCourseUrl(request.courseUrl());
        entity.setCourseId(request.courseId());
        entity.setClazzId(request.clazzId());
        entity.setCpi(request.cpi());
        entity.setEnc(request.enc());
        entity.setOwnerUserId(ownerUserId);
        entity.setStatus(UnifiedTaskStatus.PENDING.name());
        entity.setStage("created");
        entity.setProgress(0);
        entity.setMessage("Import task created");
        entity.setOutputDir(outputDir.toString());
        saveTask(entity);
        saveTaskState(taskId, entity, null);

        taskExecutor.execute(() -> executeImport(entity, request));
        return toTaskView(entity, 0);
    }

    public ChaoxingImportTaskView getTask(String taskId) {
        ChaoxingImportTaskEntity entity = requireTask(taskId);
        int resourceCount = requireResources(taskId).size();
        return toTaskView(entity, resourceCount);
    }

    public List<ChaoxingResourceView> getResources(String taskId) {
        requireTask(taskId);
        return requireResources(taskId).stream()
                .map(this::toResourceView)
                .toList();
    }

    public ChaoxingCoursewareBindView createCourseware(String taskId) {
        ChaoxingImportTaskEntity entity = requireTask(taskId);
        if (!UnifiedTaskStatus.SUCCESS.name().equals(entity.getStatus()) || !StringUtils.hasText(entity.getParseReadyManifestPath())) {
            throw new BusinessException(ErrorCode.STATE_CONFLICT, "Import task is not ready for courseware creation");
        }

        Path parseReadyFile = pickPreferredParseReadyFile(Path.of(entity.getParseReadyManifestPath()));
        if (parseReadyFile == null || !Files.exists(parseReadyFile)) {
            throw new NoSuchElementException("No parse-ready courseware file found for this task");
        }

        CoursewareUploadResult uploadResult = coursewareService.importLocalFile(parseReadyFile, parseReadyFile.getFileName().toString());
        entity.setCoursewareId(uploadResult.getCoursewareId());
        saveTask(entity);
        coursewareService.bindSourceMetadata(uploadResult.getCoursewareId(), "CHAOXING", taskId);
        coursewareService.bindPageImageUrls(uploadResult.getCoursewareId(), collectPageImageMap(taskId));
        return new ChaoxingCoursewareBindView(taskId, uploadResult.getCoursewareId(), uploadResult.getStatus());
    }

    private void executeImport(ChaoxingImportTaskEntity entity, CreateRequest request) {
        try {
            updateTask(entity, UnifiedTaskStatus.RUNNING, "discovering", 15, "Discovering and downloading Chaoxing resources", null);
            Files.createDirectories(Path.of(entity.getOutputDir()));
            PythonCourseResourceImportClient.ImportExecutionResult result = pythonCourseResourceImportClient.executeImport(
                    entity.getId(),
                    PythonCourseResourceImportRequest.builder()
                            .sourceType("CHAOXING_COURSE")
                            .url(request.courseUrl())
                            .courseid(request.courseId())
                            .clazzid(request.clazzId())
                            .cpi(request.cpi())
                            .enc(request.enc())
                            .cookie(request.cookie())
                            .authorization(request.authorization())
                            .referer(StringUtils.hasText(request.courseUrl()) ? request.courseUrl() : request.referer())
                            .buildPdf(true)
                            .autoParse(false)
                            .outputDir(Path.of(entity.getOutputDir()))
                            .build()
            );

            persistResources(entity.getId(), result.getFiles());
            entity.setManifestPath(result.getManifestPath());
            entity.setParseReadyManifestPath(result.getParseReadyManifest());
            entity.setGeneratedPdf(result.getGeneratedPdf());
            updateTask(entity, UnifiedTaskStatus.SUCCESS, "completed", 100, "Chaoxing import finished", null);
        } catch (Exception ex) {
            log.error("Chaoxing import task failed. taskId={}", entity.getId(), ex);
            updateTask(entity, UnifiedTaskStatus.FAILED, "failed", 100, "Chaoxing import failed", ex.getMessage());
        }
    }

    private void updateTask(
            ChaoxingImportTaskEntity entity,
            UnifiedTaskStatus status,
            String stage,
            Integer progress,
            String message,
            String errorMessage
    ) {
        entity.setStatus(status.name());
        entity.setStage(stage);
        entity.setProgress(progress);
        entity.setMessage(message);
        entity.setErrorMessage(errorMessage);
        saveTask(entity);
        saveTaskState(entity.getId(), entity, errorMessage);
    }

    private void saveTask(ChaoxingImportTaskEntity entity) {
        runtimeTaskStore.put(entity.getId(), entity);
        ChaoxingImportTaskRepository repository = taskRepositoryProvider.getIfAvailable();
        if (repository != null) {
            repository.save(entity);
        }
    }

    private void saveTaskState(String taskId, ChaoxingImportTaskEntity entity, String errorMessage) {
        taskStateStore.save(
                "chaoxing_import:" + taskId,
                TaskStatePayload.builder()
                        .taskId(taskId)
                        .status(UnifiedTaskStatus.valueOf(entity.getStatus()))
                        .stage(entity.getStage())
                        .progress(entity.getProgress())
                        .message(entity.getMessage())
                        .errorMessage(errorMessage)
                        .updatedAt(Instant.now())
                        .metadata(Map.of(
                                "generatedPdf", entity.getGeneratedPdf() == null ? "" : entity.getGeneratedPdf(),
                                "coursewareId", entity.getCoursewareId() == null ? "" : entity.getCoursewareId()
                        ))
                        .build()
        );
    }

    private void persistResources(String taskId, List<PythonCourseResourceImportClient.ImportFileResult> files) {
        List<ChaoxingResourceEntity> resources = new ArrayList<>();
        for (PythonCourseResourceImportClient.ImportFileResult file : files) {
            ChaoxingResourceEntity entity = new ChaoxingResourceEntity();
            entity.setTaskId(taskId);
            entity.setResourceId(file.getResourceId());
            entity.setTitle(file.getTitle());
            entity.setFileName(file.getFileName());
            entity.setResourceKind(file.getResourceKind());
            entity.setStatus(file.getStatus());
            entity.setLocalPath(file.getLocalPath());
            entity.setMimeType(file.getMimeType());
            entity.setSourceUrl(file.getSourceUrl());
            entity.setConfidence(file.getConfidence());
            entity.setReason(file.getReason());
            resources.add(entity);
        }
        runtimeResourceStore.put(taskId, List.copyOf(resources));
        ChaoxingResourceRepository repository = resourceRepositoryProvider.getIfAvailable();
        if (repository != null) {
            repository.deleteByTaskId(taskId);
            repository.saveAll(resources);
        }
    }

    private ChaoxingImportTaskEntity requireTask(String taskId) {
        if (!StringUtils.hasText(taskId)) {
            throw new IllegalArgumentException("taskId must not be blank");
        }
        ChaoxingImportTaskEntity runtimeEntity = runtimeTaskStore.get(taskId);
        if (runtimeEntity != null) {
            return runtimeEntity;
        }
        ChaoxingImportTaskRepository repository = taskRepositoryProvider.getIfAvailable();
        if (repository != null) {
            return repository.findById(taskId).orElseThrow(() -> new NoSuchElementException("Chaoxing import task not found"));
        }
        throw new NoSuchElementException("Chaoxing import task not found");
    }

    private List<ChaoxingResourceEntity> requireResources(String taskId) {
        List<ChaoxingResourceEntity> runtimeResources = runtimeResourceStore.get(taskId);
        if (runtimeResources != null) {
            return runtimeResources;
        }
        ChaoxingResourceRepository repository = resourceRepositoryProvider.getIfAvailable();
        if (repository != null) {
            return repository.findByTaskIdOrderByIdAsc(taskId);
        }
        return List.of();
    }

    private Path importRoot() {
        Path localBaseDir = Path.of(storageProperties.getLocalBaseDir()).toAbsolutePath().normalize();
        Path dataDir = localBaseDir.getParent() == null ? localBaseDir : localBaseDir.getParent();
        return dataDir.resolve("chaoxing-import");
    }

    private void validateCreateRequest(CreateRequest request) {
        if (request == null) {
            throw new IllegalArgumentException("Request body must not be null");
        }
        if (!StringUtils.hasText(request.courseUrl()) && !StringUtils.hasText(request.courseId())) {
            throw new IllegalArgumentException("courseUrl or courseId is required");
        }
        if (!StringUtils.hasText(request.cookie()) && !StringUtils.hasText(request.authorization())) {
            throw new IllegalArgumentException("cookie or authorization is required");
        }
    }

    private Path pickPreferredParseReadyFile(Path parseReadyManifest) {
        try {
            JsonNode root = objectMapper.readTree(Files.readString(parseReadyManifest));
            List<Path> candidates = new ArrayList<>();
            for (JsonNode item : root.path("parse_ready_files")) {
                String rawPath = item.path("path").asText("");
                if (!StringUtils.hasText(rawPath)) {
                    continue;
                }
                Path path = Path.of(rawPath).toAbsolutePath().normalize();
                String type = item.path("type").asText("");
                if ("pdf".equalsIgnoreCase(type) || "courseware_file".equalsIgnoreCase(type)) {
                    candidates.add(path);
                }
            }
            return candidates.stream()
                    .sorted(Comparator.comparingInt(this::parsePriority))
                    .findFirst()
                    .orElse(null);
        } catch (IOException ex) {
            throw new IllegalStateException("Failed to read parse ready manifest", ex);
        }
    }

    private int parsePriority(Path path) {
        String name = path.getFileName().toString().toLowerCase();
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

    private Map<Integer, String> collectPageImageMap(String taskId) {
        List<ChaoxingResourceEntity> resources = requireResources(taskId).stream()
                .filter(item -> "slide_image".equalsIgnoreCase(item.getResourceKind()))
                .sorted(Comparator.comparing(ChaoxingResourceEntity::getFileName))
                .toList();
        Map<Integer, String> pageImages = new LinkedHashMap<>();
        int pageNo = 1;
        for (ChaoxingResourceEntity resource : resources) {
            if (StringUtils.hasText(resource.getLocalPath())) {
                pageImages.put(pageNo++, resource.getLocalPath());
            }
        }
        return pageImages;
    }

    private ChaoxingImportTaskView toTaskView(ChaoxingImportTaskEntity entity, int resourceCount) {
        return new ChaoxingImportTaskView(
                entity.getId(),
                entity.getStatus(),
                entity.getStage(),
                entity.getProgress(),
                entity.getMessage(),
                entity.getErrorMessage(),
                entity.getCourseUrl(),
                entity.getGeneratedPdf(),
                entity.getCoursewareId(),
                resourceCount
        );
    }

    private ChaoxingResourceView toResourceView(ChaoxingResourceEntity entity) {
        return new ChaoxingResourceView(
                entity.getResourceId(),
                entity.getTitle(),
                entity.getFileName(),
                entity.getResourceKind(),
                entity.getStatus(),
                entity.getLocalPath(),
                entity.getMimeType(),
                entity.getSourceUrl(),
                entity.getConfidence(),
                entity.getReason()
        );
    }

    public record CreateRequest(
            String courseUrl,
            String courseId,
            String clazzId,
            String cpi,
            String enc,
            String cookie,
            String authorization,
            String referer,
            String userAgent
    ) {
    }
}
