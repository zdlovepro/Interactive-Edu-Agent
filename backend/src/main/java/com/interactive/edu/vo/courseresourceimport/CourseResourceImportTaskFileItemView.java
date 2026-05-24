package com.interactive.edu.vo.courseresourceimport;

public record CourseResourceImportTaskFileItemView(
        String fileName,
        String resourceKind,
        String status,
        String localPath,
        Double confidence,
        String reason
) {
}
