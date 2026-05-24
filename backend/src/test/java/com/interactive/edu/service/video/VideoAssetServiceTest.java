package com.interactive.edu.service.video;

import com.interactive.edu.config.VideoAssetProperties;
import com.interactive.edu.vo.video.VideoAssetView;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.springframework.mock.web.MockMultipartFile;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class VideoAssetServiceTest {

    @TempDir
    Path tempDir;

    private VideoAssetProperties properties;
    private VideoAssetService service;

    @BeforeEach
    void setUp() {
        properties = new VideoAssetProperties();
        properties.setLocalBaseDir(tempDir.resolve("video-assets").toString());
        service = new VideoAssetService(properties);
    }

    @Test
    @DisplayName("sample import creates an uploaded demo asset from local sample.mp4")
    void importSample_createsUploadedAsset() throws Exception {
        Path samplePath = tempDir.resolve("samples/sample.mp4");
        Files.createDirectories(samplePath.getParent());
        Files.write(samplePath, new byte[]{0x00, 0x01, 0x02, 0x03});
        properties.setSampleImportCandidates(List.of(samplePath.toString()));

        VideoAssetView asset = service.importSample();

        assertThat(asset.status()).isEqualTo("UPLOADED");
        assertThat(asset.sample()).isTrue();
        assertThat(asset.originalFilename()).isEqualTo("sample.mp4");
        assertThat(service.list().items()).hasSize(1);
    }

    @Test
    @DisplayName("transcode reports a clear message when ffmpeg command is unavailable")
    void transcode_whenFfmpegMissing_marksAssetFailed() {
        properties.setFfmpegCommand("definitely-missing-ffmpeg");
        VideoAssetView uploaded = uploadVideo("missing-ffmpeg.mp4");

        assertThatThrownBy(() -> service.transcode(uploaded.id()))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("FFmpeg 不存在或不可执行");

        assertThat(service.get(uploaded.id()).status()).isEqualTo("FAILED");
        assertThat(service.get(uploaded.id()).errorMessage()).contains("FFmpeg");
    }

    @Test
    @DisplayName("transcode stores playlist and ts paths when ffmpeg command succeeds")
    void transcode_whenCommandSucceeds_marksAssetReady() throws Exception {
        Path mockFfmpegScript = createMockFfmpegScript();
        properties.setFfmpegCommand("cmd");
        properties.setFfmpegCommandArgs(List.of("/c", mockFfmpegScript.toString()));

        VideoAssetView uploaded = uploadVideo("demo.mp4");
        VideoAssetView transcoded = service.transcode(uploaded.id());

        assertThat(transcoded.status()).isEqualTo("READY");
        assertThat(transcoded.playlistUrl()).endsWith("/hls/index.m3u8");
        assertThat(transcoded.segmentUrls()).hasSize(1);
        assertThat(transcoded.segmentUrls().get(0)).endsWith("/hls/segment-000.ts");

        VideoAssetService.MediaResource playlistResource = service.getHlsResource(uploaded.id(), "index.m3u8");
        String playlistBody = Files.readString(playlistResource.file(), StandardCharsets.UTF_8);
        assertThat(playlistBody).contains("segment-000.ts");

        VideoAssetService.MediaResource segmentResource = service.getHlsResource(uploaded.id(), "segment-000.ts");
        assertThat(Files.readAllBytes(segmentResource.file()))
                .containsExactly((byte) 0x00, (byte) 0x01, (byte) 0x02, (byte) 0x03);
    }

    private VideoAssetView uploadVideo(String filename) {
        MockMultipartFile file = new MockMultipartFile(
                "file",
                filename,
                "video/mp4",
                new byte[]{0x10, 0x20, 0x30}
        );
        return service.upload(file, null);
    }

    private Path createMockFfmpegScript() throws Exception {
        Path script = tempDir.resolve("mock-ffmpeg.cmd");
        String scriptContent = """
                @echo off
                setlocal EnableExtensions EnableDelayedExpansion
                set "playlist="
                set "segmentPattern="
                set "captureSegment="

                for %%A in (%*) do (
                  if "!captureSegment!"=="1" (
                    set "segmentPattern=%%~A"
                    set "captureSegment="
                  )
                  if "%%~A"=="-hls_segment_filename" set "captureSegment=1"
                  set "playlist=%%~A"
                )

                if not defined segmentPattern exit /b 2

                set "segmentFile=!segmentPattern:%%03d=000!"
                for %%I in ("!playlist!") do (
                  if not exist "%%~dpI" mkdir "%%~dpI"
                )

                > "!playlist!" (
                  echo #EXTM3U
                  echo #EXT-X-VERSION:3
                  echo #EXT-X-TARGETDURATION:4
                  echo #EXTINF:4.0,
                  echo segment-000.ts
                  echo #EXT-X-ENDLIST
                )

                powershell -NoProfile -Command "[System.IO.File]::WriteAllBytes('!segmentFile!', [byte[]](0,1,2,3))" >nul
                """;
        Files.writeString(script, scriptContent, StandardCharsets.UTF_8);
        return script;
    }
}
