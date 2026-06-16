package com.interactive.edu.vo.courseware;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;

@JsonIgnoreProperties(ignoreUnknown = true)
public record CoursewareVideoTimelineItemView(
        @JsonProperty("segmentId") String segmentId,
        @JsonProperty("pageIndex") int pageIndex,
        @JsonProperty("title") String title,
        @JsonProperty("startMs") long startMs,
        @JsonProperty("endMs") long endMs,
        @JsonProperty("durationMs") long durationMs
) {
}
