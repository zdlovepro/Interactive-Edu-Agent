package com.interactive.edu.vo.courseware;

import java.util.List;

public record CoursewareVideoRenderTaskView(
        String coursewareId,
        String status,
        int progress,
        String message,
        String mp4Path,
        String hlsPlaylistPath,
        String hlsUrl,
        Long durationMs,
        Integer segmentCount,
        String errorMessage,
        List<CoursewareVideoTimelineItemView> timeline
) {
}
