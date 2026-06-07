package com.interactive.edu.vo.imports;

public record ChaoxingResourceView(
        String resourceId,
        String title,
        String fileName,
        String resourceKind,
        String status,
        String localPath,
        String mimeType,
        String sourceUrl,
        Double confidence,
        String reason
) {
}
