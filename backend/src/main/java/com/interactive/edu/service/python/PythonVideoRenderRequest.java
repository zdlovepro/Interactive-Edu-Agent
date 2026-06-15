package com.interactive.edu.service.python;

import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;

import java.util.List;

@Data
@Builder
@JsonInclude(JsonInclude.Include.NON_NULL)
public class PythonVideoRenderRequest {

    @JsonProperty("coursewareId")
    private String coursewareId;

    @JsonProperty("outputDir")
    private String outputDir;

    @JsonProperty("backendBaseUrl")
    private String backendBaseUrl;

    @JsonProperty("hlsSegmentSeconds")
    private Integer hlsSegmentSeconds;

    @JsonProperty("segments")
    private List<Segment> segments;

    @Data
    @AllArgsConstructor
    @JsonInclude(JsonInclude.Include.NON_NULL)
    public static class Segment {

        @JsonProperty("segmentId")
        private String segmentId;

        @JsonProperty("pageIndex")
        private int pageIndex;

        @JsonProperty("title")
        private String title;

        @JsonProperty("scriptText")
        private String scriptText;

        @JsonProperty("pageImagePath")
        private String pageImagePath;

        @JsonProperty("knowledgePoints")
        private List<String> knowledgePoints;

        @JsonProperty("visualSummary")
        private String visualSummary;

        @JsonProperty("audioUrl")
        private String audioUrl;
    }
}
