package com.interactive.edu.service.courseware;

import com.interactive.edu.exception.BusinessException;
import com.interactive.edu.exception.ErrorCode;
import com.interactive.edu.exception.ServiceException;
import com.interactive.edu.service.python.PythonVideoRenderClient;
import com.interactive.edu.service.python.PythonVideoRenderRequest;
import com.interactive.edu.vo.courseware.CoursewareVideoRenderTaskView;
import com.interactive.edu.vo.courseware.ScriptSegmentView;
import com.interactive.edu.vo.courseware.ScriptView;
import lombok.Getter;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
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
    @Qualifier("taskExecutor")
    private final TaskExecutor taskExecutor;

    @Value("${video.render.base-dir:./data/render}")
    private String renderBaseDir;

    @Value("${video.render.backend-base-url:http://localhost:8080}")
    private String backendBaseUrl;

    @Value("${video.asset.hls-segment-seconds:6}")
    private int hlsSegmentSeconds;

    private final ConcurrentMap<String, VideoRenderTaskState> taskStore = new ConcurrentHashMap<>();

    public CoursewareVideoRenderTaskView triggerRender(String coursewareId) {
        ensureCoursewareId(coursewareId);
        ScriptView script = coursewareService.requireScript(coursewareId);
        if (script.segments() == null || script.segments().isEmpty()) {
            throw new BusinessException(ErrorCode.STATE_CONFLICT, "Script is empty, cannot render video");
        }

        VideoRenderTaskState existing = taskStore.get(coursewareId);
        if (existing != null && "RENDERING".equals(existing.getStatus())) {
            return toView(existing);
        }

        VideoRenderTaskState state = new VideoRenderTaskState(coursewareId, outputDirFor(coursewareId));
        taskStore.put(coursewareId, state);
        taskExecutor.execute(() -> runRender(state, script));
        return toView(state);
    }

    public CoursewareVideoRenderTaskView getTask(String coursewareId) {
        ensureCoursewareId(coursewareId);
        VideoRenderTaskState state = taskStore.get(coursewareId);
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
            PythonVideoRenderRequest request = PythonVideoRenderRequest.builder()
                    .coursewareId(state.getCoursewareId())
                    .outputDir(state.getOutputDir().toString())
                    .backendBaseUrl(backendBaseUrl)
                    .hlsSegmentSeconds(Math.max(1, hlsSegmentSeconds))
                    .segments(toPythonSegments(script.segments()))
                    .build();

            PythonVideoRenderClient.VideoRenderResult result = pythonVideoRenderClient.render(request);
            state.markReady(result);
        } catch (Exception ex) {
            log.error("Courseware video render failed. coursewareId={}", state.getCoursewareId(), ex);
            state.markFailed(ex instanceof ServiceException serviceException
                    ? serviceException.getFriendlyMessage()
                    : ex.getMessage());
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
                            segment.audioUrl()
                    );
                })
                .toList();
    }

    private VideoRenderTaskState requireReadyTask(String coursewareId) {
        VideoRenderTaskState state = taskStore.get(coursewareId);
        if (state == null || !"READY".equals(state.getStatus())) {
            throw new NoSuchElementException("Courseware rendered video is not ready");
        }
        return state;
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
        private final Instant createdAt = Instant.now();
        private volatile Instant updatedAt = createdAt;
        private volatile String status = "PENDING";
        private volatile int progress = 0;
        private volatile String message = "Video render task pending";
        private volatile String mp4Path;
        private volatile String hlsPlaylistPath;
        private volatile Long durationMs;
        private volatile Integer segmentCount;
        private volatile String errorMessage;

        private VideoRenderTaskState(String coursewareId, Path outputDir) {
            this.coursewareId = coursewareId;
            this.outputDir = outputDir;
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
