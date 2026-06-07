package com.interactive.edu.vo.digitalhuman;

public record DigitalHumanTaskView(
        String taskId,
        String status,
        String stage,
        Integer progress,
        String coursewareId,
        Integer pageNo,
        String scriptId,
        String audioUrl,
        String videoUrl,
        String hlsUrl,
        String message,
        String errorMessage
) {
}
