package com.interactive.edu.vo.lecture;

public record CoursewareLectureStateView(
        String coursewareId,
        String title,
        String sourceType,
        Integer currentPage,
        Integer totalPages,
        String pageText,
        String pageImageUrl,
        String scriptId,
        String scriptText,
        String audioUrl,
        String digitalHumanTaskId,
        String digitalHumanStatus,
        String videoUrl,
        String hlsUrl
) {
}
