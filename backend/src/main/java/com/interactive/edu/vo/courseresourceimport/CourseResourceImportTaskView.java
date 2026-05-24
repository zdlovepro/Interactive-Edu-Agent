package com.interactive.edu.vo.courseresourceimport;

public record CourseResourceImportTaskView(
        String taskId,
        String status,
        int progress,
        int discoveredCount,
        int selectedCount,
        int downloadedCount,
        int ignoredCount,
        String generatedPdf,
        String message,
        String coursewareId
) {
}
