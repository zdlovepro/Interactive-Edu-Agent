package com.interactive.edu.controller;

import com.interactive.edu.service.courseware.CoursewareService;
import jakarta.validation.constraints.NotBlank;
import lombok.RequiredArgsConstructor;
import org.springframework.core.io.FileSystemResource;
import org.springframework.core.io.Resource;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.util.StringUtils;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Locale;
import java.util.NoSuchElementException;

@RestController
@RequestMapping("/api/v1/courseware")
@RequiredArgsConstructor
public class CoursewarePageAssetController {

    private final CoursewareService coursewareService;

    @GetMapping("/{coursewareId}/pages/{pageIndex}/image")
    public ResponseEntity<Resource> getPageImage(
            @PathVariable("coursewareId") @NotBlank String coursewareId,
            @PathVariable("pageIndex") Integer pageIndex
    ) {
        CoursewareService.PageSnapshot pageSnapshot = coursewareService.getPageSnapshot(coursewareId, pageIndex);
        if (pageSnapshot == null || !StringUtils.hasText(pageSnapshot.imageUrl())) {
            throw new NoSuchElementException("Page image not found");
        }
        String rawPath = pageSnapshot.imageUrl();
        if (rawPath.startsWith("http://") || rawPath.startsWith("https://")) {
            return ResponseEntity.status(302)
                    .header(HttpHeaders.LOCATION, rawPath)
                    .build();
        }

        Path file = Path.of(rawPath).toAbsolutePath().normalize();
        if (!Files.exists(file) || !Files.isRegularFile(file)) {
            throw new NoSuchElementException("Page image not found");
        }
        return ResponseEntity.ok()
                .contentType(resolveMediaType(file))
                .header(HttpHeaders.CACHE_CONTROL, "public, max-age=3600")
                .body(new FileSystemResource(file));
    }

    private MediaType resolveMediaType(Path file) {
        String lowerName = file.getFileName().toString().toLowerCase(Locale.ROOT);
        if (lowerName.endsWith(".png")) {
            return MediaType.IMAGE_PNG;
        }
        if (lowerName.endsWith(".jpg") || lowerName.endsWith(".jpeg")) {
            return MediaType.IMAGE_JPEG;
        }
        return MediaType.APPLICATION_OCTET_STREAM;
    }
}
