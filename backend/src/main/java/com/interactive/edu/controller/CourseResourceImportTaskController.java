package com.interactive.edu.controller;

import com.interactive.edu.dto.BaseResponse;
import com.interactive.edu.dto.courseresourceimport.CreateCourseResourceImportTaskRequest;
import com.interactive.edu.service.courseresourceimport.CourseResourceImportTaskService;
import com.interactive.edu.service.user.AuthService;
import com.interactive.edu.vo.courseresourceimport.CourseResourceImportTaskCreateView;
import com.interactive.edu.vo.courseresourceimport.CourseResourceImportTaskFilesView;
import com.interactive.edu.vo.courseresourceimport.CourseResourceImportTaskView;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/v1/course-resource-import/tasks")
@RequiredArgsConstructor
public class CourseResourceImportTaskController {

    private final CourseResourceImportTaskService courseResourceImportTaskService;
    private final AuthService authService;

    @PostMapping
    public BaseResponse<CourseResourceImportTaskCreateView> createTask(
            @RequestBody @Valid CreateCourseResourceImportTaskRequest request,
            @RequestHeader(value = "Authorization", required = false) String authorizationHeader
    ) {
        return BaseResponse.ok(courseResourceImportTaskService.createTask(
                request,
                authService.requireUser(authorizationHeader).id()
        ));
    }

    @GetMapping("/{taskId}")
    public BaseResponse<CourseResourceImportTaskView> getTask(
            @PathVariable("taskId") @NotBlank String taskId,
            @RequestHeader(value = "Authorization", required = false) String authorizationHeader
    ) {
        return BaseResponse.ok(courseResourceImportTaskService.getTask(
                taskId,
                authService.requireUser(authorizationHeader).id()
        ));
    }

    @GetMapping("/{taskId}/files")
    public BaseResponse<CourseResourceImportTaskFilesView> getFiles(
            @PathVariable("taskId") @NotBlank String taskId,
            @RequestHeader(value = "Authorization", required = false) String authorizationHeader
    ) {
        return BaseResponse.ok(courseResourceImportTaskService.getFiles(
                taskId,
                authService.requireUser(authorizationHeader).id()
        ));
    }

    @PostMapping("/{taskId}/retry")
    public BaseResponse<CourseResourceImportTaskView> retry(
            @PathVariable("taskId") @NotBlank String taskId,
            @RequestHeader(value = "Authorization", required = false) String authorizationHeader
    ) {
        return BaseResponse.ok(courseResourceImportTaskService.retry(
                taskId,
                authService.requireUser(authorizationHeader).id()
        ));
    }

    @PostMapping("/{taskId}/cancel")
    public BaseResponse<CourseResourceImportTaskView> cancel(
            @PathVariable("taskId") @NotBlank String taskId,
            @RequestHeader(value = "Authorization", required = false) String authorizationHeader
    ) {
        return BaseResponse.ok(courseResourceImportTaskService.cancel(
                taskId,
                authService.requireUser(authorizationHeader).id()
        ));
    }
}
