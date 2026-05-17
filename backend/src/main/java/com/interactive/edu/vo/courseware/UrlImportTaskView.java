package com.interactive.edu.vo.courseware;

public record UrlImportTaskView(
        String taskId,
        String coursewareId,
        String sourceUrl,
        String name,
        String status,
        String stage,
        int progress,
        String message,
        String createdAt,
        String updatedAt
) {
}
