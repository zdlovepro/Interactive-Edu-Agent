package com.interactive.edu.controller;

import com.interactive.edu.config.VideoAssetProperties;
import com.interactive.edu.service.video.VideoAssetService;
import com.interactive.edu.vo.video.VideoAssetView;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.springframework.http.HttpHeaders;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

class VideoAssetControllerTest {

    @TempDir
    Path tempDir;

    private VideoAssetService videoAssetService;
    private MockMvc mockMvc;

    @BeforeEach
    void setUp() throws Exception {
        VideoAssetProperties properties = new VideoAssetProperties();
        properties.setLocalBaseDir(tempDir.resolve("video-assets").toString());
        properties.setFfmpegCommand("cmd");
        properties.setFfmpegCommandArgs(List.of("/c", createMockFfmpegScript().toString()));

        videoAssetService = new VideoAssetService(properties);
        mockMvc = MockMvcBuilders.standaloneSetup(new VideoAssetController(videoAssetService)).build();
    }

    @Test
    @DisplayName("source and hls files are exposed with media-friendly content types")
    void mediaEndpoints_returnExpectedContentTypes() throws Exception {
        VideoAssetView uploaded = videoAssetService.upload(
                new org.springframework.mock.web.MockMultipartFile(
                        "file",
                        "controller-demo.mp4",
                        "video/mp4",
                        new byte[]{0x55, 0x66, 0x77}
                ),
                null
        );
        VideoAssetView transcoded = videoAssetService.transcode(uploaded.id());

        mockMvc.perform(get(uploaded.sourceUrl()))
                .andExpect(status().isOk())
                .andExpect(header().string(HttpHeaders.CACHE_CONTROL, "public, max-age=3600"))
                .andExpect(content().contentType("video/mp4"))
                .andExpect(content().bytes(new byte[]{0x55, 0x66, 0x77}));

        mockMvc.perform(get(transcoded.playlistUrl()))
                .andExpect(status().isOk())
                .andExpect(content().contentType("application/vnd.apple.mpegurl"))
                .andExpect(content().string(org.hamcrest.Matchers.containsString("segment-000.ts")));

        mockMvc.perform(get(transcoded.segmentUrls().get(0)))
                .andExpect(status().isOk())
                .andExpect(content().contentType("video/mp2t"))
                .andExpect(content().bytes(new byte[]{0x00, 0x01, 0x02, 0x03}));
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
