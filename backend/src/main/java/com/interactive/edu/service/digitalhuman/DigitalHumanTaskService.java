package com.interactive.edu.service.digitalhuman;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.interactive.edu.entity.DigitalHumanTaskEntity;
import com.interactive.edu.entity.HlsAssetEntity;
import com.interactive.edu.entity.VideoAssetEntity;
import com.interactive.edu.enums.UnifiedTaskStatus;
import com.interactive.edu.exception.BusinessException;
import com.interactive.edu.exception.ErrorCode;
import com.interactive.edu.model.task.TaskStatePayload;
import com.interactive.edu.repository.DigitalHumanTaskRepository;
import com.interactive.edu.repository.HlsAssetRepository;
import com.interactive.edu.repository.VideoAssetRepository;
import com.interactive.edu.service.courseware.CoursewareService;
import com.interactive.edu.service.python.PythonDigitalHumanClient;
import com.interactive.edu.service.task.TaskStateStore;
import com.interactive.edu.service.video.VideoAssetService;
import com.interactive.edu.vo.digitalhuman.DigitalHumanTaskResultView;
import com.interactive.edu.vo.digitalhuman.DigitalHumanTaskView;
import com.interactive.edu.vo.video.VideoAssetView;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;

import java.time.LocalDateTime;
import java.time.Instant;
import java.util.List;
import java.util.Map;
import java.util.NoSuchElementException;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ConcurrentMap;

@Service
@RequiredArgsConstructor
@Slf4j
public class DigitalHumanTaskService {

    private final PythonDigitalHumanClient pythonDigitalHumanClient;
    private final CoursewareService coursewareService;
    private final VideoAssetService videoAssetService;
    private final TaskStateStore taskStateStore;
    private final ObjectMapper objectMapper;
    private final ObjectProvider<DigitalHumanTaskRepository> taskRepositoryProvider;
    private final ObjectProvider<VideoAssetRepository> videoAssetRepositoryProvider;
    private final ObjectProvider<HlsAssetRepository> hlsAssetRepositoryProvider;

    private final ConcurrentMap<String, DigitalHumanTaskEntity> runtimeStore = new ConcurrentHashMap<>();

    public DigitalHumanTaskView createTask(CreateRequest request) {
        if (request == null || !StringUtils.hasText(request.coursewareId())) {
            throw new IllegalArgumentException("coursewareId must not be blank");
        }
        int pageNo = request.pageNo() == null || request.pageNo() <= 0 ? 1 : request.pageNo();
        String taskId = "dh_" + UUID.randomUUID().toString().replace("-", "");
        String scriptId = StringUtils.hasText(request.scriptId())
                ? request.scriptId()
                : coursewareService.findScriptIdByPage(request.coursewareId(), pageNo);
        String audioUrl = StringUtils.hasText(request.audioUrl())
                ? request.audioUrl()
                : coursewareService.getCurrentNode(request.coursewareId(), pageNo).audioUrl();
        String scriptText = coursewareService.getSegmentForPage(request.coursewareId(), pageNo).content();

        DigitalHumanTaskEntity entity = new DigitalHumanTaskEntity();
        entity.setId(taskId);
        entity.setCoursewareId(request.coursewareId());
        entity.setPageNo(pageNo);
        entity.setScriptId(scriptId);
        entity.setAudioUrl(audioUrl);
        entity.setMode(StringUtils.hasText(request.mode()) ? request.mode() : "MOCK");
        entity.setStatus(UnifiedTaskStatus.RUNNING.name());
        entity.setStage("audio-drive");
        entity.setProgress(20);
        entity.setMessage("Digital-human audio-drive is running");
        save(entity);
        saveTaskState(entity);

        try {
            PythonDigitalHumanClient.AudioDriveResult result = pythonDigitalHumanClient.generateAudioDrive(
                    PythonDigitalHumanClient.AudioDriveRequest.builder()
                            .coursewareId(request.coursewareId())
                            .pageIndex(pageNo)
                            .scriptText(scriptText)
                            .audioUrl(audioUrl)
                            .audioDurationMs(4000)
                            .protocolFormat("both")
                            .avatarId("default-avatar")
                            .sdkVersion("vendor-neutral-v1")
                            .build()
            );

            entity.setStatus(UnifiedTaskStatus.SUCCESS.name());
            entity.setStage("completed");
            entity.setProgress(100);
            entity.setMessage("Digital-human task completed");
            entity.setAudioJson(writeJson(result.audio()));
            entity.setTimelineJson(writeJson(result.safeTokens()));
            entity.setPhonemesJson(writeJson(result.safePhonemes()));
            entity.setActionFramesJson(writeJson(result.safeFrames()));
            entity.setProtocolJson(writeJson(result.protocolJson()));
            entity.setProtocolXml(result.protocolXml());
            entity.setWarningsJson(writeJson(result.safeWarnings()));
            save(entity);
            saveTaskState(entity);
            return toView(entity);
        } catch (Exception ex) {
            log.error("Digital-human task failed. taskId={}", taskId, ex);
            entity.setStatus(UnifiedTaskStatus.FAILED.name());
            entity.setStage("failed");
            entity.setProgress(100);
            entity.setMessage("Digital-human task failed");
            entity.setErrorMessage(ex.getMessage());
            save(entity);
            saveTaskState(entity);
            return toView(entity);
        }
    }

    public DigitalHumanTaskView getTask(String taskId) {
        return toView(requireTask(taskId));
    }

    public DigitalHumanTaskResultView getResult(String taskId) {
        DigitalHumanTaskEntity entity = requireTask(taskId);
        return new DigitalHumanTaskResultView(
                entity.getId(),
                entity.getStatus(),
                readJson(entity.getAudioJson(), Object.class),
                readJson(entity.getTimelineJson(), Object.class),
                readJson(entity.getPhonemesJson(), Object.class),
                readJson(entity.getActionFramesJson(), Object.class),
                readJson(entity.getProtocolJson(), Object.class),
                entity.getProtocolXml(),
                readJson(entity.getWarningsJson(), Object.class),
                entity.getVideoUrl(),
                entity.getHlsUrl()
        );
    }

    public DigitalHumanTaskView bindVideo(String taskId, BindVideoRequest request) {
        DigitalHumanTaskEntity entity = requireTask(taskId);
        if (!StringUtils.hasText(request.videoAssetId())) {
            throw new IllegalArgumentException("videoAssetId must not be blank");
        }
        VideoAssetView assetView = videoAssetService.get(request.videoAssetId());
        entity.setVideoAssetId(assetView.id());
        entity.setVideoUrl(assetView.sourceUrl());
        persistVideoAssetSnapshot(assetView);
        save(entity);
        saveTaskState(entity);
        return toView(entity);
    }

    public DigitalHumanTaskView bindHls(String taskId, BindHlsRequest request) {
        DigitalHumanTaskEntity entity = requireTask(taskId);
        String videoAssetId = StringUtils.hasText(request.videoAssetId()) ? request.videoAssetId() : entity.getVideoAssetId();
        String hlsUrl = request.hlsUrl();
        if (!StringUtils.hasText(videoAssetId) && !StringUtils.hasText(hlsUrl)) {
            throw new IllegalArgumentException("videoAssetId or hlsUrl must not be blank");
        }

        if (StringUtils.hasText(videoAssetId)) {
            VideoAssetView assetView = videoAssetService.get(videoAssetId);
            entity.setVideoAssetId(assetView.id());
            entity.setVideoUrl(assetView.sourceUrl());
            if (!StringUtils.hasText(hlsUrl)) {
                hlsUrl = assetView.playlistUrl();
            }
            persistVideoAssetSnapshot(assetView);
            persistHlsSnapshot(assetView);
        }
        entity.setHlsAssetId(videoAssetId);
        entity.setHlsUrl(hlsUrl);
        save(entity);
        saveTaskState(entity);
        return toView(entity);
    }

    public DigitalHumanTaskEntity findLatestByCoursewareAndPage(String coursewareId, Integer pageNo) {
        DigitalHumanTaskRepository repository = taskRepositoryProvider.getIfAvailable();
        if (repository != null) {
            return repository.findFirstByCoursewareIdAndPageNoOrderByCreateTimeDesc(coursewareId, pageNo).orElse(null);
        }
        return runtimeStore.values().stream()
                .filter(item -> coursewareId.equals(item.getCoursewareId()) && pageNo.equals(item.getPageNo()))
                .sorted((left, right) -> {
                    LocalDateTime rightTime = resolveSortTime(right);
                    LocalDateTime leftTime = resolveSortTime(left);
                    int compareTime = rightTime.compareTo(leftTime);
                    if (compareTime != 0) {
                        return compareTime;
                    }
                    return right.getId().compareTo(left.getId());
                })
                .findFirst()
                .orElse(null);
    }

    private void save(DigitalHumanTaskEntity entity) {
        LocalDateTime now = LocalDateTime.now();
        if (entity.getCreateTime() == null) {
            entity.setCreateTime(now);
        }
        entity.setUpdateTime(now);
        runtimeStore.put(entity.getId(), entity);
        DigitalHumanTaskRepository repository = taskRepositoryProvider.getIfAvailable();
        if (repository != null) {
            repository.save(entity);
        }
    }

    private void saveTaskState(DigitalHumanTaskEntity entity) {
        taskStateStore.save(
                "digital_human:" + entity.getId(),
                TaskStatePayload.builder()
                        .taskId(entity.getId())
                        .status(UnifiedTaskStatus.valueOf(entity.getStatus()))
                        .stage(entity.getStage())
                        .progress(entity.getProgress())
                        .message(entity.getMessage())
                        .errorMessage(entity.getErrorMessage())
                        .updatedAt(Instant.now())
                        .metadata(Map.of(
                                "coursewareId", entity.getCoursewareId(),
                                "pageNo", entity.getPageNo() == null ? 1 : entity.getPageNo(),
                                "videoUrl", entity.getVideoUrl() == null ? "" : entity.getVideoUrl(),
                                "hlsUrl", entity.getHlsUrl() == null ? "" : entity.getHlsUrl()
                        ))
                        .build()
        );
    }

    private DigitalHumanTaskEntity requireTask(String taskId) {
        if (!StringUtils.hasText(taskId)) {
            throw new IllegalArgumentException("taskId must not be blank");
        }
        DigitalHumanTaskEntity runtimeEntity = runtimeStore.get(taskId);
        if (runtimeEntity != null) {
            return runtimeEntity;
        }
        DigitalHumanTaskRepository repository = taskRepositoryProvider.getIfAvailable();
        if (repository != null) {
            return repository.findById(taskId).orElseThrow(() -> new NoSuchElementException("Digital-human task not found"));
        }
        throw new NoSuchElementException("Digital-human task not found");
    }

    private void persistVideoAssetSnapshot(VideoAssetView assetView) {
        VideoAssetRepository repository = videoAssetRepositoryProvider.getIfAvailable();
        if (repository == null) {
            return;
        }
        VideoAssetEntity entity = repository.findById(assetView.id()).orElseGet(VideoAssetEntity::new);
        entity.setId(assetView.id());
        entity.setName(assetView.name());
        entity.setOriginalFilename(assetView.originalFilename());
        entity.setStatus(assetView.status());
        entity.setSourceUrl(assetView.sourceUrl());
        entity.setSample(assetView.sample());
        repository.save(entity);
    }

    private void persistHlsSnapshot(VideoAssetView assetView) {
        if (!StringUtils.hasText(assetView.playlistUrl())) {
            return;
        }
        HlsAssetRepository repository = hlsAssetRepositoryProvider.getIfAvailable();
        if (repository == null) {
            return;
        }
        HlsAssetEntity entity = repository.findFirstByVideoAssetIdOrderByCreateTimeDesc(assetView.id()).orElseGet(HlsAssetEntity::new);
        entity.setVideoAssetId(assetView.id());
        entity.setPlaylistUrl(assetView.playlistUrl());
        entity.setSegmentUrlsJson(writeJson(assetView.segmentUrls()));
        entity.setStatus(assetView.status());
        repository.save(entity);
    }

    private LocalDateTime resolveSortTime(DigitalHumanTaskEntity entity) {
        if (entity.getUpdateTime() != null) {
            return entity.getUpdateTime();
        }
        if (entity.getCreateTime() != null) {
            return entity.getCreateTime();
        }
        return LocalDateTime.MIN;
    }

    private String writeJson(Object value) {
        try {
            return objectMapper.writeValueAsString(value);
        } catch (JsonProcessingException ex) {
            throw new IllegalStateException("Failed to serialize digital-human payload", ex);
        }
    }

    private <T> T readJson(String raw, Class<T> type) {
        if (!StringUtils.hasText(raw)) {
            return null;
        }
        try {
            return objectMapper.readValue(raw, type);
        } catch (Exception ex) {
            throw new IllegalStateException("Failed to deserialize digital-human payload", ex);
        }
    }

    private DigitalHumanTaskView toView(DigitalHumanTaskEntity entity) {
        return new DigitalHumanTaskView(
                entity.getId(),
                entity.getStatus(),
                entity.getStage(),
                entity.getProgress(),
                entity.getCoursewareId(),
                entity.getPageNo(),
                entity.getScriptId(),
                entity.getAudioUrl(),
                entity.getVideoUrl(),
                entity.getHlsUrl(),
                entity.getMessage(),
                entity.getErrorMessage()
        );
    }

    public record CreateRequest(
            String coursewareId,
            Integer pageNo,
            String scriptId,
            String audioUrl,
            String mode
    ) {
    }

    public record BindVideoRequest(String videoAssetId) {
    }

    public record BindHlsRequest(String videoAssetId, String hlsUrl) {
    }
}
