package com.interactive.edu.controller;

import com.interactive.edu.dto.BaseResponse;
import com.interactive.edu.service.digitalhuman.DigitalHumanTaskService;
import com.interactive.edu.vo.digitalhuman.DigitalHumanTaskResultView;
import com.interactive.edu.vo.digitalhuman.DigitalHumanTaskView;
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
@RequestMapping("/api/v1/digital-human/tasks")
@RequiredArgsConstructor
public class DigitalHumanTaskController {

    private final DigitalHumanTaskService digitalHumanTaskService;

    @PostMapping
    public BaseResponse<DigitalHumanTaskView> createTask(@Valid @RequestBody CreateDigitalHumanTaskRequest request) {
        return BaseResponse.ok(digitalHumanTaskService.createTask(
                new DigitalHumanTaskService.CreateRequest(
                        request.coursewareId(),
                        request.pageNo(),
                        request.scriptId(),
                        request.audioUrl(),
                        request.mode()
                )
        ));
    }

    @GetMapping("/{taskId}")
    public BaseResponse<DigitalHumanTaskView> getTask(@PathVariable @NotBlank String taskId) {
        return BaseResponse.ok(digitalHumanTaskService.getTask(taskId));
    }

    @GetMapping("/{taskId}/result")
    public BaseResponse<DigitalHumanTaskResultView> getResult(@PathVariable @NotBlank String taskId) {
        return BaseResponse.ok(digitalHumanTaskService.getResult(taskId));
    }

    @PostMapping("/{taskId}/bind-video")
    public BaseResponse<DigitalHumanTaskView> bindVideo(
            @PathVariable @NotBlank String taskId,
            @Valid @RequestBody BindVideoRequest request
    ) {
        return BaseResponse.ok(digitalHumanTaskService.bindVideo(
                taskId,
                new DigitalHumanTaskService.BindVideoRequest(request.videoAssetId())
        ));
    }

    @PostMapping("/{taskId}/bind-hls")
    public BaseResponse<DigitalHumanTaskView> bindHls(
            @PathVariable @NotBlank String taskId,
            @Valid @RequestBody BindHlsRequest request
    ) {
        return BaseResponse.ok(digitalHumanTaskService.bindHls(
                taskId,
                new DigitalHumanTaskService.BindHlsRequest(request.videoAssetId(), request.hlsUrl())
        ));
    }

    public record CreateDigitalHumanTaskRequest(
            String coursewareId,
            Integer pageNo,
            String scriptId,
            String audioUrl,
            String mode
    ) {
    }

    public record BindVideoRequest(String videoAssetId) {
    }

    public record BindHlsRequest(String videoAssetId, String hlsUrl) {
    }
}
