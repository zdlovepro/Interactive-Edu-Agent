package com.interactive.edu.service.python;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.AllArgsConstructor;
import lombok.Data;

import java.util.List;

@Data
@AllArgsConstructor
public class PythonQaIngestRequest {

    @JsonProperty("coursewareId")
    private String coursewareId;

    @JsonProperty("pages")
    private List<PagePayload> pages;

    @JsonProperty("chunkSize")
    private Integer chunkSize;

    @JsonProperty("chunkOverlap")
    private Integer chunkOverlap;

    @JsonProperty("includeVisualSummaryDocs")
    private Boolean includeVisualSummaryDocs;

    @Data
    @AllArgsConstructor
    public static class PagePayload {
        @JsonProperty("pageIndex")
        private int pageIndex;

        @JsonProperty("title")
        private String title;

        @JsonProperty("content")
        private String content;

        @JsonProperty("knowledgePoints")
        private List<String> knowledgePoints;

        @JsonProperty("pageImagePath")
        private String pageImagePath;

        @JsonProperty("visualSummary")
        private String visualSummary;

        @JsonProperty("visualObjects")
        private List<String> visualObjects;
    }
}
