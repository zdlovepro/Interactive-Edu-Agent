package com.interactive.edu.config;

import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;

import java.util.ArrayList;
import java.util.List;

@Data
@ConfigurationProperties(prefix = "video.asset")
public class VideoAssetProperties {

    /** Base directory used when storing uploaded videos and HLS outputs locally. */
    private String localBaseDir = "./data/video-assets";

    /** Command used to invoke FFmpeg. */
    private String ffmpegCommand = "ffmpeg";

    /** Optional command arguments prepended before FFmpeg flags. */
    private List<String> ffmpegCommandArgs = new ArrayList<>();

    /** Default HLS segment duration in seconds. */
    private int hlsSegmentSeconds = 6;

    /** Candidate local sample paths used by the sample import endpoint. */
    private List<String> sampleImportCandidates = new ArrayList<>(List.of(
            "../frontend/public/sample/sample.mp4",
            "frontend/public/sample/sample.mp4"
    ));
}
