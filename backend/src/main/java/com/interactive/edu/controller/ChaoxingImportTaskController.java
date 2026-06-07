package com.interactive.edu.controller;

import com.interactive.edu.dto.BaseResponse;
import com.interactive.edu.service.imports.ChaoxingImportTaskService;
import com.interactive.edu.vo.imports.ChaoxingCoursewareBindView;
import com.interactive.edu.vo.imports.ChaoxingImportTaskView;
import com.interactive.edu.vo.imports.ChaoxingResourceView;
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

import java.util.List;

@RestController
@RequestMapping("/api/v1/import/chaoxing/tasks")
@RequiredArgsConstructor
public class ChaoxingImportTaskController {

    private final ChaoxingImportTaskService chaoxingImportTaskService;

    @PostMapping
    public BaseResponse<ChaoxingImportTaskView> createTask(
            @Valid @RequestBody CreateChaoxingTaskRequest request,
            @RequestHeader(value = "X-User-Id", required = false) String userId
    ) {
        return BaseResponse.ok(chaoxingImportTaskService.createTask(
                new ChaoxingImportTaskService.CreateRequest(
                        request.courseUrl(),
                        request.courseId(),
                        request.clazzId(),
                        request.cpi(),
                        request.enc(),
                        request.cookie(),
                        request.authorization(),
                        request.referer(),
                        request.userAgent()
                ),
                userId
        ));
    }

    @GetMapping("/{taskId}")
    public BaseResponse<ChaoxingImportTaskView> getTask(@PathVariable @NotBlank String taskId) {
        return BaseResponse.ok(chaoxingImportTaskService.getTask(taskId));
    }

    @GetMapping("/{taskId}/resources")
    public BaseResponse<List<ChaoxingResourceView>> getResources(@PathVariable @NotBlank String taskId) {
        return BaseResponse.ok(chaoxingImportTaskService.getResources(taskId));
    }

    @PostMapping("/{taskId}/coursewares")
    public BaseResponse<ChaoxingCoursewareBindView> createCourseware(@PathVariable @NotBlank String taskId) {
        return BaseResponse.ok(chaoxingImportTaskService.createCourseware(taskId));
    }

    public record CreateChaoxingTaskRequest(
            String courseUrl,
            String courseId,
            String clazzId,
            String cpi,
            String enc,
            String cookie,
            String authorization,
            String referer,
            String userAgent
    ) {
    }
}
