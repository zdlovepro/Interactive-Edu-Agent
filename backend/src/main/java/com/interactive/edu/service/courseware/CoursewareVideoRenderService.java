package com.interactive.edu.service.courseware;

import com.interactive.edu.entity.CoursewareVideoRenderTask;
import com.interactive.edu.exception.BusinessException;
import com.interactive.edu.exception.ErrorCode;
import com.interactive.edu.exception.ServiceException;
import com.interactive.edu.repository.CoursewareVideoRenderTaskRepository;
import com.interactive.edu.service.python.PythonVideoRenderClient;
import com.interactive.edu.service.python.PythonVideoRenderRequest;
import com.interactive.edu.vo.courseware.CoursewareVideoRenderTaskView;
import com.interactive.edu.vo.courseware.ScriptSegmentView;
import com.interactive.edu.vo.courseware.ScriptView;
import lombok.Getter;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.io.FileSystemResource;
import org.springframework.core.io.Resource;
import org.springframework.core.task.TaskExecutor;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;

import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Instant;
import java.util.List;
import java.util.Locale;
import java.util.NoSuchElementException;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ConcurrentMap;

@Slf4j
@Service
@RequiredArgsConstructor
public class CoursewareVideoRenderService {

    private static final String HLS_URL_TEMPLATE = "/api/v1/courseware/%s/video/hls/index.m3u8";

    private final CoursewareService coursewareService;
    private final PythonVideoRenderClient pythonVideoRenderClient;
    private final ObjectProvider<CoursewareVideoRenderTaskRepository> taskRepositoryProvider;
    @Qualifier("taskExecutor")
    private final TaskExecutor taskExecutor;

    @Value("${video.render.base-dir:./data/render}")
    private String renderBaseDir;

    @Value("${video.render.backend-base-url:http://localhost:8080}")
    private String backendBaseUrl;

    @Value("${video.asset.hls-segment-seconds:6}")
    private int hlsSegmentSeconds;

    private final ConcurrentMap<String, VideoRenderTaskState> taskStore = new ConcurrentHashMap<>();
    private final ConcurrentMap<String, Boolean> activeRenderJobs = new ConcurrentHashMap<>();

    public CoursewareVideoRenderTaskView triggerRender(String coursewareId) {
        ensureCoursewareId(coursewareId);
        ScriptView script = coursewareService.requireScript(coursewareId);
        if (script.segments() == null || script.segments().isEmpty()) {
            throw new BusinessException(ErrorCode.STATE_CONFLICT, "Script is empty, cannot render video");
        }

        VideoRenderTaskState existing = loadTaskState(coursewareId);
        if (existing != null && "RENDERING".equals(existing.getStatus())) {
            if (Boolean.TRUE.equals(activeRenderJobs.get(coursewareId))) {
                return toView(existing);
            }

            log.warn(
                    "Restarting stale courseware video render task. coursewareId={}, lastUpdate={}, message={}",
                    coursewareId,
                    existing.getUpdatedAt(),
                    existing.getMessage()
            );
        }

        VideoRenderTaskState state = new VideoRenderTaskState(coursewareId, outputDirFor(coursewareId));
        taskStore.put(coursewareId, state);
        persistTaskState(state);
        activeRenderJobs.put(coursewareId, Boolean.TRUE);
        taskExecutor.execute(() -> runRender(state, script));
        return toView(state);
    }

    public CoursewareVideoRenderTaskView getTask(String coursewareId) {
        ensureCoursewareId(coursewareId);
        VideoRenderTaskState state = loadTaskState(coursewareId);
        if (state == null) {
            throw new NoSuchElementException("Courseware video render task not found");
        }
        return toView(state);
    }

    public MediaResource getHlsResource(String coursewareId, String relativePath) {
        VideoRenderTaskState state = requireReadyTask(coursewareId);
        if (!StringUtils.hasText(relativePath)) {
            throw new NoSuchElementException("HLS file not found");
        }

        Path hlsDir = Path.of(state.getHlsPlaylistPath()).toAbsolutePath().normalize().getParent();
        Path requestedFile = hlsDir.resolve(relativePath).normalize();
        if (!requestedFile.startsWith(hlsDir) || !Files.exists(requestedFile) || !Files.isRegularFile(requestedFile)) {
            throw new NoSuchElementException("HLS file not found");
        }
        return new MediaResource(new FileSystemResource(requestedFile), resolveMediaType(requestedFile));
    }

    public MediaResource getSourceResource(String coursewareId) {
        VideoRenderTaskState state = requireReadyTask(coursewareId);
        Path file = Path.of(state.getMp4Path()).toAbsolutePath().normalize();
        if (!Files.exists(file) || !Files.isRegularFile(file)) {
            throw new NoSuchElementException("Rendered MP4 not found");
        }
        return new MediaResource(new FileSystemResource(file), MediaType.parseMediaType("video/mp4"));
    }

    private void runRender(VideoRenderTaskState state, ScriptView script) {
        try {
            state.markRendering("Preparing render input");
            persistTaskState(state);

            PythonVideoRenderRequest request = PythonVideoRenderRequest.builder()
                    .coursewareId(state.getCoursewareId())
                    .outputDir(state.getOutputDir().toString())
                    .backendBaseUrl(backendBaseUrl)
                    .hlsSegmentSeconds(Math.max(1, hlsSegmentSeconds))
                    .segments(toPythonSegments(script.segments()))
                    .build();

            PythonVideoRenderClient.VideoRenderResult result = pythonVideoRenderClient.render(request);
            state.markReady(result);
            persistTaskState(state);
        } catch (Exception ex) {
            log.error("Courseware video render failed. coursewareId={}", state.getCoursewareId(), ex);
            state.markFailed(ex instanceof ServiceException serviceException
                    ? serviceException.getFriendlyMessage()
                    : ex.getMessage());
            persistTaskState(state);
        } finally {
            activeRenderJobs.remove(state.getCoursewareId());
        }
    }

    private List<PythonVideoRenderRequest.Segment> toPythonSegments(List<ScriptSegmentView> segments) {
        return segments.stream()
                .map(segment -> {
                    if (!StringUtils.hasText(segment.pageImagePath())) {
                        throw new BusinessException(
                                ErrorCode.STATE_CONFLICT,
                                "Page image is missing for page " + segment.pageIndex()
                        );
                    }
                    return new PythonVideoRenderRequest.Segment(
                            segment.id(),
                            segment.pageIndex(),
                            segment.title(),
                            segment.content(),
                            segment.pageImagePath(),
                            segment.knowledgePoints(),
                            segment.visualSummary(),
                            segment.audioUrl()
                    );
                })
                .toList();
    }

    private VideoRenderTaskState requireReadyTask(String coursewareId) {
        VideoRenderTaskState state = loadTaskState(coursewareId);
        if (state == null || !"READY".equals(state.getStatus())) {
            throw new NoSuchElementException("Courseware rendered video is not ready");
        }
        return state;
    }

    private VideoRenderTaskState loadTaskState(String coursewareId) {
        VideoRenderTaskState cached = taskStore.get(coursewareId);
        if (cached != null) {
            return cached;
        }

        if (!isPersistentMode()) {
            return null;
        }

        return taskRepository().findById(coursewareId)
                .map(entity -> {
                    VideoRenderTaskState state = VideoRenderTaskState.fromEntity(entity, outputDirFor(coursewareId));
                    taskStore.put(coursewareId, state);
                    return state;
                })
                .orElse(null);
    }

    private void persistTaskState(VideoRenderTaskState state) {
        if (!isPersistentMode()) {
            return;
        }

        CoursewareVideoRenderTask entity = taskRepository().findById(state.getCoursewareId())
                .orElseGet(CoursewareVideoRenderTask::new);
        entity.setCoursewareId(state.getCoursewareId());
        entity.setStatus(state.getStatus());
        entity.setProgress(state.getProgress());
        entity.setMessage(state.getMessage());
        entity.setMp4Path(state.getMp4Path());
        entity.setHlsPlaylistPath(state.getHlsPlaylistPath());
        entity.setDurationMs(state.getDurationMs());
        entity.setSegmentCount(state.getSegmentCount());
        entity.setErrorMessage(state.getErrorMessage());
        taskRepository().save(entity);
    }

    private boolean isPersistentMode() {
        return taskRepositoryProvider.getIfAvailable() != null;
    }

    private CoursewareVideoRenderTaskRepository taskRepository() {
        CoursewareVideoRenderTaskRepository repository = taskRepositoryProvider.getIfAvailable();
        if (repository == null) {
            throw new IllegalStateException("CoursewareVideoRenderTaskRepository is unavailable in the current profile");
        }
        return repository;
    }

    private CoursewareVideoRenderTaskView toView(VideoRenderTaskState state) {
        return new CoursewareVideoRenderTaskView(
                state.getCoursewareId(),
                state.getStatus(),
                state.getProgress(),
                state.getMessage(),
                state.getMp4Path(),
                state.getHlsPlaylistPath(),
                state.getHlsPlaylistPath() == null ? null : HLS_URL_TEMPLATE.formatted(state.getCoursewareId()),
                state.getDurationMs(),
                state.getSegmentCount(),
                state.getErrorMessage()
        );
    }

    private Path outputDirFor(String coursewareId) {
        return Path.of(renderBaseDir)
                .toAbsolutePath()
                .normalize()
                .resolve(coursewareId)
                .resolve("video")
                .normalize();
    }

    private void ensureCoursewareId(String coursewareId) {
        if (!StringUtils.hasText(coursewareId)) {
            throw new IllegalArgumentException("coursewareId must not be blank");
        }
    }

    private MediaType resolveMediaType(Path file) {
        String lowerName = file.getFileName().toString().toLowerCase(Locale.ROOT);
        if (lowerName.endsWith(".m3u8")) {
            return MediaType.parseMediaType("application/vnd.apple.mpegurl");
        }
        if (lowerName.endsWith(".ts")) {
            return MediaType.parseMediaType("video/mp2t");
        }
        if (lowerName.endsWith(".mp4")) {
            return MediaType.parseMediaType("video/mp4");
        }
        return MediaType.APPLICATION_OCTET_STREAM;
    }

    public record MediaResource(Resource resource, MediaType mediaType) {
    }

    @Getter
    private static final class VideoRenderTaskState {
        private final String coursewareId;
        private final Path outputDir;
        private final Instant createdAt;
        private volatile Instant updatedAt;
        private volatile String status;
        private volatile int progress;
        private volatile String message;
        private volatile String mp4Path;
        private volatile String hlsPlaylistPath;
        private volatile Long durationMs;
        private volatile Integer segmentCount;
        private volatile String errorMessage;

        private VideoRenderTaskState(String coursewareId, Path outputDir) {
            this(coursewareId, outputDir, Instant.now(), Instant.now(), "PENDING", 0, "Video render task pending", null, null, null, null, null);
        }

        private VideoRenderTaskState(
                String coursewareId,
                Path outputDir,
                Instant createdAt,
                Instant updatedAt,
                String status,
                int progress,
                String message,
                String mp4Path,
                String hlsPlaylistPath,
                Long durationMs,
                Integer segmentCount,
                String errorMessage
        ) {
            this.coursewareId = coursewareId;
            this.outputDir = outputDir;
            this.createdAt = createdAt;
            this.updatedAt = updatedAt;
            this.status = status;
            this.progress = progress;
            this.message = message;
            this.mp4Path = mp4Path;
            this.hlsPlaylistPath = hlsPlaylistPath;
            this.durationMs = durationMs;
            this.segmentCount = segmentCount;
            this.errorMessage = errorMessage;
        }

        private static VideoRenderTaskState fromEntity(CoursewareVideoRenderTask entity, Path outputDir) {
            return new VideoRenderTaskState(
                    entity.getCoursewareId(),
                    outputDir,
                    entity.getCreateTime() == null ? Instant.now() : entity.getCreateTime().atZone(java.time.ZoneId.systemDefault()).toInstant(),
                    entity.getUpdateTime() == null ? Instant.now() : entity.getUpdateTime().atZone(java.time.ZoneId.systemDefault()).toInstant(),
                    entity.getStatus(),
                    entity.getProgress() == null ? 0 : entity.getProgress(),
                    StringUtils.hasText(entity.getMessage()) ? entity.getMessage() : "Video render task pending",
                    entity.getMp4Path(),
                    entity.getHlsPlaylistPath(),
                    entity.getDurationMs(),
                    entity.getSegmentCount(),
                    entity.getErrorMessage()
            );
        }

        private void markRendering(String message) {
            this.status = "RENDERING";
            this.progress = 20;
            this.message = message;
            this.errorMessage = null;
            touch();
        }

        private void markReady(PythonVideoRenderClient.VideoRenderResult result) {
            this.status = "READY";
            this.progress = 100;
            this.message = "Courseware lecture video rendered";
            this.mp4Path = result.getMp4Path();
            this.hlsPlaylistPath = result.getHlsPlaylistPath();
            this.durationMs = result.getDurationMs();
            this.segmentCount = result.getSegmentCount();
            this.errorMessage = null;
            touch();
        }

        private void markFailed(String errorMessage) {
            this.status = "FAILED";
            this.progress = 100;
            this.message = "Courseware lecture video render failed";
            this.errorMessage = errorMessage;
            touch();
        }

        private void touch() {
            this.updatedAt = Instant.now();
        }
    }
}
