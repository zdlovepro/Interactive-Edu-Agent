package com.interactive.edu.vo.imports;

public record ChaoxingImportTaskView(
        String taskId,
        String status,
        String stage,
        Integer progress,
        String message,
        String errorMessage,
        String courseUrl,
        String generatedPdf,
        String coursewareId,
        Integer resourceCount
) {
}
