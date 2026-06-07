package com.interactive.edu.controller;

import com.interactive.edu.dto.BaseResponse;
import com.interactive.edu.service.qa.VisualQaService;
import com.interactive.edu.vo.qa.VisualQaAnswerView;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/v1/qa")
@RequiredArgsConstructor
public class VisualQaController {

    private final VisualQaService visualQaService;

    @PostMapping("/visual")
    public BaseResponse<VisualQaAnswerView> askVisual(@Valid @RequestBody VisualQaRequest request) {
        return BaseResponse.ok(visualQaService.askVisual(request.coursewareId(), request.pageNo(), request.question()));
    }

    public record VisualQaRequest(
            String coursewareId,
            Integer pageNo,
            String question
    ) {
    }
}
