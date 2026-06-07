package com.interactive.edu.vo.digitalhuman;

public record DigitalHumanTaskResultView(
        String taskId,
        String status,
        Object audio,
        Object tokens,
        Object phonemes,
        Object actionFrames,
        Object protocolJson,
        String protocolXml,
        Object warnings,
        String videoUrl,
        String hlsUrl
) {
}
