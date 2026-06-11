package com.interactive.edu.controller;

import com.interactive.edu.dto.BaseResponse;
import com.interactive.edu.service.courseware.CoursewareVideoRenderService;
import com.interactive.edu.vo.courseware.CoursewareVideoRenderTaskView;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.constraints.NotBlank;
import lombok.RequiredArgsConstructor;
import org.springframework.core.io.Resource;
import org.springframework.http.CacheControl;
import org.springframework.http.ResponseEntity;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.net.URLDecoder;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.TimeUnit;

@RestController
@RequestMapping("/api/v1/courseware/{coursewareId}/video")
@RequiredArgsConstructor
@Validated
public class CoursewareVideoController {

    private static final String HLS_REQUEST_PREFIX = "/api/v1/courseware/%s/video/hls/";

    private final CoursewareVideoRenderService coursewareVideoRenderService;

    @PostMapping("/render")
    public BaseResponse<CoursewareVideoRenderTaskView> render(
            @PathVariable("coursewareId") @NotBlank String coursewareId
    ) {
        return BaseResponse.ok(coursewareVideoRenderService.triggerRender(coursewareId));
    }

    @GetMapping("/render")
    public BaseResponse<CoursewareVideoRenderTaskView> renderTask(
            @PathVariable("coursewareId") @NotBlank String coursewareId
    ) {
        return BaseResponse.ok(coursewareVideoRenderService.getTask(coursewareId));
    }

    @GetMapping("/source")
    public ResponseEntity<Resource> source(
            @PathVariable("coursewareId") @NotBlank String coursewareId
    ) {
        return buildMediaResponse(coursewareVideoRenderService.getSourceResource(coursewareId));
    }

    @GetMapping("/hls/**")
    public ResponseEntity<Resource> hls(
            @PathVariable("coursewareId") @NotBlank String coursewareId,
            HttpServletRequest request
    ) {
        String requestPrefix = HLS_REQUEST_PREFIX.formatted(coursewareId);
        String requestUri = request.getRequestURI();
        int prefixIndex = requestUri.indexOf(requestPrefix);
        if (prefixIndex < 0) {
            throw new IllegalArgumentException("Illegal HLS request path");
        }

        String encodedRelativePath = requestUri.substring(prefixIndex + requestPrefix.length());
        String relativePath = URLDecoder.decode(encodedRelativePath, StandardCharsets.UTF_8);
        return buildMediaResponse(coursewareVideoRenderService.getHlsResource(coursewareId, relativePath));
    }

    private ResponseEntity<Resource> buildMediaResponse(CoursewareVideoRenderService.MediaResource mediaResource) {
        return ResponseEntity.ok()
                .contentType(mediaResource.mediaType())
                .cacheControl(CacheControl.maxAge(1, TimeUnit.HOURS).cachePublic())
                .body(mediaResource.resource());
    }
}
