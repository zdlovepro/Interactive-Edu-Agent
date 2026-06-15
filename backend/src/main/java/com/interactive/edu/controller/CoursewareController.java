package com.interactive.edu.controller;

import com.interactive.edu.dto.BaseResponse;
import com.interactive.edu.dto.CoursewareUploadResult;
import com.interactive.edu.dto.courseware.UpdateCoursewareScriptRequest;
import com.interactive.edu.service.courseware.CoursewareService;
import com.interactive.edu.vo.courseware.CoursewareDetailView;
import com.interactive.edu.vo.courseware.CoursewareListView;
import com.interactive.edu.vo.courseware.ScriptView;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import lombok.RequiredArgsConstructor;
import org.springframework.core.io.Resource;
import org.springframework.http.ResponseEntity;
import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RequestPart;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;

import java.util.Map;

@RestController
@RequestMapping("/api/v1/courseware")
@RequiredArgsConstructor
public class CoursewareController {

    private final CoursewareService coursewareService;

    @PostMapping(value = "/upload", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    public BaseResponse<CoursewareUploadResult> upload(
            @RequestPart("file") @NotNull MultipartFile file,
            @RequestPart(value = "name", required = false) String name
    ) {
        return BaseResponse.ok(coursewareService.upload(file, name));
    }

    @GetMapping
    public BaseResponse<CoursewareListView> list(
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(defaultValue = "20") int pageSize,
            @RequestParam(required = false) String status
    ) {
        return BaseResponse.ok(coursewareService.list(page, pageSize, status));
    }

    @GetMapping("/{coursewareId}")
    public BaseResponse<CoursewareDetailView> detail(
            @PathVariable("coursewareId") @NotBlank String coursewareId
    ) {
        return BaseResponse.ok(coursewareService.getDetail(coursewareId));
    }

    @GetMapping("/{coursewareId}/script")
    public BaseResponse<ScriptView> getScript(
            @PathVariable("coursewareId") @NotBlank String coursewareId
    ) {
        return BaseResponse.ok(coursewareService.getScript(coursewareId));
    }

    @GetMapping("/{coursewareId}/pages/{pageIndex}/image")
    public ResponseEntity<Resource> getScriptPageImage(
            @PathVariable("coursewareId") @NotBlank String coursewareId,
            @PathVariable("pageIndex") int pageIndex
    ) {
        CoursewareService.PageMediaResource mediaResource = coursewareService.getScriptPageImageResource(coursewareId, pageIndex);
        return ResponseEntity.ok()
                .contentType(mediaResource.mediaType())
                .body(mediaResource.resource());
    }

    @PutMapping("/{coursewareId}/script")
    public BaseResponse<ScriptView> updateScript(
            @PathVariable("coursewareId") @NotBlank String coursewareId,
            @Valid @RequestBody UpdateCoursewareScriptRequest request
    ) {
        return BaseResponse.ok(coursewareService.updateScript(coursewareId, request));
    }

    @PostMapping("/{coursewareId}/script/generate")
    public BaseResponse<Map<String, String>> generateScript(
            @PathVariable("coursewareId") @NotBlank String coursewareId
    ) {
        String status = coursewareService.triggerScriptGeneration(coursewareId);
        return BaseResponse.ok(Map.of(
                "coursewareId", coursewareId,
                "status", status
        ));
    }
}
