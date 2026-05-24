package com.interactive.edu.vo.video;

import java.util.List;

public record VideoAssetView(
        String id,
        String name,
        String originalFilename,
        String status,
        boolean sample,
        String sourceUrl,
        String playlistUrl,
        List<String> segmentUrls,
        String errorMessage,
        String createdAt,
        String updatedAt
) {
}
