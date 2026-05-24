package com.interactive.edu.service.video;

import com.interactive.edu.config.VideoAssetProperties;
import com.interactive.edu.enums.VideoAssetStatus;
import com.interactive.edu.vo.video.VideoAssetListView;
import com.interactive.edu.vo.video.VideoAssetView;
import lombok.Getter;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Service;
import org.springframework.util.FileSystemUtils;
import org.springframework.util.StringUtils;
import org.springframework.web.multipart.MultipartFile;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.time.Instant;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Locale;
import java.util.NoSuchElementException;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ConcurrentMap;

@Service
@RequiredArgsConstructor
@Slf4j
public class VideoAssetService {

    private static final String SOURCE_PATH_PREFIX = "/api/v1/video-assets/";
    private static final String SOURCE_PATH_SUFFIX = "/source";
    private static final String HLS_PATH_SEGMENT = "/hls/";
    private static final String HLS_PLAYLIST_FILENAME = "index.m3u8";

    private final VideoAssetProperties videoAssetProperties;

    private final ConcurrentMap<String, VideoAssetState> assetStore = new ConcurrentHashMap<>();

    public VideoAssetListView list() {
        List<VideoAssetView> items = assetStore.values().stream()
                .sorted(Comparator.comparing(VideoAssetState::getCreatedAt).reversed())
                .map(this::toView)
                .toList();
        return new VideoAssetListView(items);
    }

    public VideoAssetView get(String assetId) {
        return toView(requireAsset(assetId));
    }

    public VideoAssetView upload(MultipartFile file, String requestedName) {
        if (file == null || file.isEmpty()) {
            throw new IllegalArgumentException("视频文件不能为空");
        }

        String filename = normalizeFilename(file.getOriginalFilename());
        ensureMp4(filename);
        String assetId = nextAssetId();
        String displayName = resolveDisplayName(requestedName, filename);

        try {
            Path sourceDir = resolveAssetDir(assetId).resolve("source").normalize();
            Files.createDirectories(sourceDir);
            Path sourcePath = sourceDir.resolve(filename).normalize();
            ensureUnderBaseDir(sourcePath);
            file.transferTo(sourcePath.toFile());

            VideoAssetState state = new VideoAssetState(
                    assetId,
                    displayName,
                    filename,
                    sourcePath,
                    false
            );
            assetStore.put(assetId, state);
            log.info("Video asset uploaded. assetId={}, filename={}", assetId, filename);
            return toView(state);
        } catch (IOException ex) {
            throw new IllegalStateException("视频上传失败: " + ex.getMessage(), ex);
        }
    }

    public VideoAssetView importSample() {
        Path samplePath = resolveSamplePath();
        if (samplePath == null) {
            throw new NoSuchElementException("未找到 sample.mp4，请先准备 frontend/public/sample/sample.mp4");
        }

        String filename = normalizeFilename(samplePath.getFileName().toString());
        ensureMp4(filename);
        String assetId = nextAssetId();

        try {
            Path sourceDir = resolveAssetDir(assetId).resolve("source").normalize();
            Files.createDirectories(sourceDir);
            Path sourcePath = sourceDir.resolve(filename).normalize();
            ensureUnderBaseDir(sourcePath);
            Files.copy(samplePath, sourcePath, StandardCopyOption.REPLACE_EXISTING);

            VideoAssetState state = new VideoAssetState(
                    assetId,
                    stripExtension(filename) + " Demo",
                    filename,
                    sourcePath,
                    true
            );
            assetStore.put(assetId, state);
            log.info("Sample video asset imported. assetId={}, source={}", assetId, samplePath);
            return toView(state);
        } catch (IOException ex) {
            throw new IllegalStateException("导入 sample.mp4 失败: " + ex.getMessage(), ex);
        }
    }

    public VideoAssetView transcode(String assetId) {
        VideoAssetState state = requireAsset(assetId);
        state.markTranscoding();

        Path assetDir = resolveAssetDir(assetId);
        Path hlsDir = assetDir.resolve("hls").normalize();
        Path playlistPath = hlsDir.resolve(HLS_PLAYLIST_FILENAME).normalize();
        Path segmentPatternPath = hlsDir.resolve("segment-%03d.ts").normalize();

        try {
            ensureUnderBaseDir(assetDir);
            if (Files.exists(hlsDir)) {
                FileSystemUtils.deleteRecursively(hlsDir);
            }
            Files.createDirectories(hlsDir);

            List<String> command = buildTranscodeCommand(state.getSourcePath(), playlistPath, segmentPatternPath);
            log.info("Video asset HLS transcode started. assetId={}, command={}", assetId, command);
            Process process = new ProcessBuilder(command)
                    .redirectErrorStream(true)
                    .start();

            String output = readProcessOutput(process);
            int exitCode = process.waitFor();
            if (exitCode != 0) {
                state.markFailed(buildTranscodeFailureMessage(output));
                throw new IllegalStateException(state.getErrorMessage());
            }

            if (!Files.exists(playlistPath) || !Files.isRegularFile(playlistPath)) {
                state.markFailed("FFmpeg 已执行，但未生成 m3u8 播放清单");
                throw new IllegalStateException(state.getErrorMessage());
            }

            List<String> segmentFileNames = Files.list(hlsDir)
                    .filter(Files::isRegularFile)
                    .map(path -> path.getFileName().toString())
                    .filter(filename -> filename.toLowerCase(Locale.ROOT).endsWith(".ts"))
                    .sorted()
                    .toList();

            if (segmentFileNames.isEmpty()) {
                state.markFailed("FFmpeg 已执行，但未生成 ts 切片文件");
                throw new IllegalStateException(state.getErrorMessage());
            }

            state.markReady(playlistPath, segmentFileNames);
            log.info(
                    "Video asset HLS transcode finished. assetId={}, segmentCount={}",
                    assetId,
                    segmentFileNames.size()
            );
            return toView(state);
        } catch (IOException ex) {
            String message = "FFmpeg 不存在或不可执行，请先安装 FFmpeg 并确保命令可用";
            state.markFailed(message);
            throw new IllegalStateException(message, ex);
        } catch (InterruptedException ex) {
            Thread.currentThread().interrupt();
            String message = "视频转码被中断，请稍后重试";
            state.markFailed(message);
            throw new IllegalStateException(message, ex);
        }
    }

    public MediaResource getSourceResource(String assetId) {
        VideoAssetState state = requireAsset(assetId);
        Path sourcePath = state.getSourcePath();
        ensureReadableFile(sourcePath, "源视频不存在");
        return new MediaResource(sourcePath, MediaType.parseMediaType("video/mp4"));
    }

    public MediaResource getHlsResource(String assetId, String relativePath) {
        VideoAssetState state = requireAsset(assetId);
        if (!StringUtils.hasText(relativePath)) {
            throw new NoSuchElementException("HLS 文件不存在");
        }

        Path hlsDir = resolveAssetDir(assetId).resolve("hls").normalize();
        Path requestedFile = hlsDir.resolve(relativePath).normalize();
        if (!requestedFile.startsWith(hlsDir)) {
            throw new IllegalArgumentException("非法 HLS 文件路径");
        }

        ensureReadableFile(requestedFile, "HLS 文件不存在");
        return new MediaResource(requestedFile, resolveMediaType(requestedFile));
    }

    private VideoAssetState requireAsset(String assetId) {
        if (!StringUtils.hasText(assetId)) {
            throw new IllegalArgumentException("assetId 不能为空");
        }
        VideoAssetState state = assetStore.get(assetId);
        if (state == null) {
            throw new NoSuchElementException("视频资产不存在");
        }
        return state;
    }

    private Path resolveBaseDir() {
        Path baseDir = Path.of(videoAssetProperties.getLocalBaseDir()).toAbsolutePath().normalize();
        try {
            Files.createDirectories(baseDir);
        } catch (IOException ex) {
            throw new IllegalStateException("无法初始化视频资产目录: " + ex.getMessage(), ex);
        }
        return baseDir;
    }

    private Path resolveAssetDir(String assetId) {
        return resolveBaseDir().resolve(assetId).normalize();
    }

    private void ensureUnderBaseDir(Path path) {
        if (!path.startsWith(resolveBaseDir())) {
            throw new IllegalArgumentException("非法视频资产路径");
        }
    }

    private void ensureReadableFile(Path file, String missingMessage) {
        if (!Files.exists(file) || !Files.isRegularFile(file)) {
            throw new NoSuchElementException(missingMessage);
        }
    }

    private List<String> buildTranscodeCommand(Path sourcePath, Path playlistPath, Path segmentPatternPath) {
        List<String> command = new ArrayList<>();
        command.add(videoAssetProperties.getFfmpegCommand());
        command.addAll(videoAssetProperties.getFfmpegCommandArgs());
        command.add("-y");
        command.add("-i");
        command.add(sourcePath.toString());
        command.add("-c:v");
        command.add("libx264");
        command.add("-c:a");
        command.add("aac");
        command.add("-b:a");
        command.add("128k");
        command.add("-f");
        command.add("hls");
        command.add("-hls_time");
        command.add(String.valueOf(Math.max(1, videoAssetProperties.getHlsSegmentSeconds())));
        command.add("-hls_playlist_type");
        command.add("vod");
        command.add("-hls_segment_filename");
        command.add(segmentPatternPath.toString());
        command.add(playlistPath.toString());
        return command;
    }

    private String readProcessOutput(Process process) throws IOException {
        try (BufferedReader reader = new BufferedReader(
                new InputStreamReader(process.getInputStream(), StandardCharsets.UTF_8))) {
            StringBuilder builder = new StringBuilder();
            String line;
            while ((line = reader.readLine()) != null) {
                if (builder.length() > 0) {
                    builder.append(System.lineSeparator());
                }
                builder.append(line);
            }
            return builder.toString();
        }
    }

    private String buildTranscodeFailureMessage(String output) {
        if (!StringUtils.hasText(output)) {
            return "FFmpeg 转码失败，请检查输入视频或 FFmpeg 配置";
        }

        String[] lines = output.split("\\R");
        int startIndex = Math.max(0, lines.length - 3);
        String hint = String.join(" ", List.of(lines).subList(startIndex, lines.length)).trim();
        if (!StringUtils.hasText(hint)) {
            return "FFmpeg 转码失败，请检查输入视频或 FFmpeg 配置";
        }
        return "FFmpeg 转码失败: " + hint;
    }

    private Path resolveSamplePath() {
        for (String candidate : videoAssetProperties.getSampleImportCandidates()) {
            if (!StringUtils.hasText(candidate)) {
                continue;
            }

            Path path = Path.of(candidate).toAbsolutePath().normalize();
            if (Files.exists(path) && Files.isRegularFile(path)) {
                return path;
            }
        }
        return null;
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

    private VideoAssetView toView(VideoAssetState state) {
        String playlistUrl = state.getPlaylistPath() == null
                ? null
                : SOURCE_PATH_PREFIX + state.getId() + HLS_PATH_SEGMENT + HLS_PLAYLIST_FILENAME;

        List<String> segmentUrls = state.getSegmentFileNames().stream()
                .map(filename -> SOURCE_PATH_PREFIX + state.getId() + HLS_PATH_SEGMENT + filename)
                .toList();

        return new VideoAssetView(
                state.getId(),
                state.getName(),
                state.getOriginalFilename(),
                state.getStatus().name(),
                state.isSample(),
                SOURCE_PATH_PREFIX + state.getId() + SOURCE_PATH_SUFFIX,
                playlistUrl,
                segmentUrls,
                state.getErrorMessage(),
                state.getCreatedAt().toString(),
                state.getUpdatedAt().toString()
        );
    }

    private String nextAssetId() {
        return "video_" + UUID.randomUUID().toString().replace("-", "");
    }

    private void ensureMp4(String filename) {
        if (!filename.toLowerCase(Locale.ROOT).endsWith(".mp4")) {
            throw new IllegalArgumentException("当前仅支持上传或导入 MP4 视频");
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
            return "video.mp4";
        }

        String filename = originalFilename.replace('\u0000', ' ').trim().replace('\\', '/');
        int lastSlash = filename.lastIndexOf('/');
        if (lastSlash >= 0) {
            filename = filename.substring(lastSlash + 1);
        }

        return StringUtils.hasText(filename) ? filename : "video.mp4";
    }

    private String stripExtension(String filename) {
        int dotIndex = filename.lastIndexOf('.');
        return dotIndex > 0 ? filename.substring(0, dotIndex) : filename;
    }

    public record MediaResource(Path file, MediaType mediaType) {
    }

    @Getter
    private static final class VideoAssetState {
        private final String id;
        private final String name;
        private final String originalFilename;
        private final Path sourcePath;
        private final boolean sample;
        private final Instant createdAt = Instant.now();
        private volatile Instant updatedAt = createdAt;
        private volatile VideoAssetStatus status = VideoAssetStatus.UPLOADED;
        private volatile Path playlistPath;
        private volatile List<String> segmentFileNames = List.of();
        private volatile String errorMessage;

        private VideoAssetState(
                String id,
                String name,
                String originalFilename,
                Path sourcePath,
                boolean sample
        ) {
            this.id = id;
            this.name = name;
            this.originalFilename = originalFilename;
            this.sourcePath = sourcePath;
            this.sample = sample;
        }

        private void markTranscoding() {
            this.status = VideoAssetStatus.TRANSCODING;
            this.errorMessage = null;
            this.playlistPath = null;
            this.segmentFileNames = List.of();
            touch();
        }

        private void markReady(Path playlistPath, List<String> segmentFileNames) {
            this.status = VideoAssetStatus.READY;
            this.playlistPath = playlistPath;
            this.segmentFileNames = List.copyOf(segmentFileNames);
            this.errorMessage = null;
            touch();
        }

        private void markFailed(String errorMessage) {
            this.status = VideoAssetStatus.FAILED;
            this.errorMessage = errorMessage;
            this.playlistPath = null;
            this.segmentFileNames = List.of();
            touch();
        }

        private void touch() {
            this.updatedAt = Instant.now();
        }
    }
}
