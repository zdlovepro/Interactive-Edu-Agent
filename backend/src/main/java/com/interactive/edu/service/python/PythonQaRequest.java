package com.interactive.edu.service.python;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.AllArgsConstructor;
import lombok.Data;

import java.util.List;

@Data
@AllArgsConstructor
public class PythonQaRequest {

    @JsonProperty("sessionId")
    private String sessionId;

    @JsonProperty("coursewareId")
    private String coursewareId;

    @JsonProperty("pageIndex")
    private Integer pageIndex;

    @JsonProperty("question")
    private String question;

    @JsonProperty("topK")
    private Integer topK;

    @JsonProperty("currentPageTitle")
    private String currentPageTitle;

    @JsonProperty("currentPageContent")
    private String currentPageContent;

    @JsonProperty("currentPageImagePath")
    private String currentPageImagePath;

    @JsonProperty("currentPageVisualSummary")
    private String currentPageVisualSummary;

    @JsonProperty("currentPageKnowledgePoints")
    private List<String> currentPageKnowledgePoints;

    @JsonProperty("currentPageVisualObjects")
    private List<String> currentPageVisualObjects;

    @JsonProperty("coursewarePages")
    private List<CoursewarePagePayload> coursewarePages;

    @Data
    @AllArgsConstructor
    public static class CoursewarePagePayload {

        @JsonProperty("pageIndex")
        private Integer pageIndex;

        @JsonProperty("title")
        private String title;

        @JsonProperty("content")
        private String content;

        @JsonProperty("knowledgePoints")
        private List<String> knowledgePoints;

        @JsonProperty("visualSummary")
        private String visualSummary;

        @JsonProperty("visualObjects")
        private List<String> visualObjects;
    }
}
