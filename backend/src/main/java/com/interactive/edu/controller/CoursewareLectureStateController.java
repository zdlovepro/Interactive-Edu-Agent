package com.interactive.edu.controller;

import com.interactive.edu.dto.BaseResponse;
import com.interactive.edu.service.lecture.CoursewareLectureStateService;
import com.interactive.edu.vo.lecture.CoursewareLectureStateView;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/v1/lectures")
@RequiredArgsConstructor
public class CoursewareLectureStateController {

    private final CoursewareLectureStateService coursewareLectureStateService;

    @GetMapping("/{coursewareId}/state")
    public BaseResponse<CoursewareLectureStateView> getState(@PathVariable @NotBlank String coursewareId) {
        return BaseResponse.ok(coursewareLectureStateService.getState(coursewareId));
    }

    @PostMapping("/{coursewareId}/progress")
    public BaseResponse<CoursewareLectureStateView> updateProgress(
            @PathVariable @NotBlank String coursewareId,
            @Valid @RequestBody LectureProgressRequest request
    ) {
        return BaseResponse.ok(coursewareLectureStateService.updateProgress(
                coursewareId,
                new CoursewareLectureStateService.ProgressRequest(request.currentPage(), request.status(), request.playbackTime())
        ));
    }

    @PostMapping("/{coursewareId}/records")
    public BaseResponse<String> appendRecord(
            @PathVariable @NotBlank String coursewareId,
            @Valid @RequestBody LectureRecordRequest request
    ) {
        return coursewareLectureStateService.appendRecord(
                coursewareId,
                new CoursewareLectureStateService.RecordRequest(request.recordType(), request.payload())
        );
    }

    public record LectureProgressRequest(
            Integer currentPage,
            String status,
            Double playbackTime
    ) {
    }

    public record LectureRecordRequest(
            String recordType,
            Object payload
    ) {
    }
}
