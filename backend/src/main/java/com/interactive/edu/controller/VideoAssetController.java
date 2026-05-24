package com.interactive.edu.controller;

import com.interactive.edu.dto.BaseResponse;
import com.interactive.edu.service.video.VideoAssetService;
import com.interactive.edu.vo.video.VideoAssetListView;
import com.interactive.edu.vo.video.VideoAssetView;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.constraints.NotBlank;
import lombok.RequiredArgsConstructor;
import org.springframework.core.io.FileSystemResource;
import org.springframework.core.io.Resource;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestPart;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;

import java.net.URLDecoder;
import java.nio.charset.StandardCharsets;

@RestController
@RequestMapping("/api/v1/video-assets")
@RequiredArgsConstructor
@Validated
public class VideoAssetController {

    private static final String HLS_REQUEST_PREFIX = "/api/v1/video-assets/%s/hls/";

    private final VideoAssetService videoAssetService;

    @GetMapping
    public BaseResponse<VideoAssetListView> list() {
        return BaseResponse.ok(videoAssetService.list());
    }

    @GetMapping("/{assetId}")
    public BaseResponse<VideoAssetView> detail(@PathVariable("assetId") @NotBlank String assetId) {
        return BaseResponse.ok(videoAssetService.get(assetId));
    }

    @PostMapping(value = "/upload", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    public BaseResponse<VideoAssetView> upload(
            @RequestPart("file") MultipartFile file,
            @RequestPart(value = "name", required = false) String name
    ) {
        return BaseResponse.ok(videoAssetService.upload(file, name));
    }

    @PostMapping("/import-sample")
    public BaseResponse<VideoAssetView> importSample() {
        return BaseResponse.ok(videoAssetService.importSample());
    }

    @PostMapping("/{assetId}/transcode")
    public BaseResponse<VideoAssetView> transcode(@PathVariable("assetId") @NotBlank String assetId) {
        return BaseResponse.ok(videoAssetService.transcode(assetId));
    }

    @GetMapping("/{assetId}/source")
    public ResponseEntity<Resource> getSource(@PathVariable("assetId") @NotBlank String assetId) {
        return buildMediaResponse(videoAssetService.getSourceResource(assetId));
    }

    @GetMapping("/{assetId}/hls/**")
    public ResponseEntity<Resource> getHls(
            @PathVariable("assetId") @NotBlank String assetId,
            HttpServletRequest request
    ) {
        String requestPrefix = HLS_REQUEST_PREFIX.formatted(assetId);
        String requestUri = request.getRequestURI();
        int prefixIndex = requestUri.indexOf(requestPrefix);
        if (prefixIndex < 0) {
            throw new IllegalArgumentException("非法 HLS 请求路径");
        }

        String encodedRelativePath = requestUri.substring(prefixIndex + requestPrefix.length());
        String relativePath = URLDecoder.decode(encodedRelativePath, StandardCharsets.UTF_8);
        return buildMediaResponse(videoAssetService.getHlsResource(assetId, relativePath));
    }

    private ResponseEntity<Resource> buildMediaResponse(VideoAssetService.MediaResource mediaResource) {
        Resource resource = new FileSystemResource(mediaResource.file());
        return ResponseEntity.ok()
                .contentType(mediaResource.mediaType())
                .header(HttpHeaders.CACHE_CONTROL, "public, max-age=3600")
                .body(resource);
    }
}
