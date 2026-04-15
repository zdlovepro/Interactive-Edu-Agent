package com.interactive.edu.service.courseware;

import com.interactive.edu.dto.BaseResponse;
import com.interactive.edu.dto.CoursewareUploadResult;
import com.interactive.edu.service.courseware.CoursewareService;
import jakarta.validation.constraints.NotNull;
import lombok.RequiredArgsConstructor;
import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

@RestController
@RequestMapping("/api/v1/courseware")
@RequiredArgsConstructor
public class CoursewareController {

    private final CoursewareService coursewareService;

    @PostMapping(value = "/upload", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    public BaseResponse<CoursewareUploadResult> upload(@RequestPart("file") @NotNull MultipartFile file,
                                                       @RequestPart(value = "name", required = false) String name) {
        // name 暂时不落库，先保留参数位，后续再接 DB 表
        CoursewareUploadResult result = coursewareService.upload(file);
        return BaseResponse.ok(result);
    }
}