package com.interactive.edu.controller;

import com.interactive.edu.dto.BaseResponse;
import com.interactive.edu.dto.courseware.UrlImportRequest;
import com.interactive.edu.service.urlimport.UrlImportService;
import com.interactive.edu.vo.courseware.UrlImportTaskView;
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
@RequestMapping("/api/v1/courseware/import-url")
@RequiredArgsConstructor
public class UrlImportController {

    private final UrlImportService urlImportService;

    @PostMapping
    public BaseResponse<UrlImportTaskView> createTask(@Valid @RequestBody UrlImportRequest request) {
        return BaseResponse.ok(urlImportService.createTask(request.getUrl(), request.getName()));
    }

    @GetMapping("/tasks/{taskId}")
    public BaseResponse<UrlImportTaskView> getTask(@PathVariable("taskId") @NotBlank String taskId) {
        return BaseResponse.ok(urlImportService.getTask(taskId));
    }
}
