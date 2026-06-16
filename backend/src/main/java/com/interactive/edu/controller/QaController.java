package com.interactive.edu.controller;

import com.interactive.edu.dto.BaseResponse;
import com.interactive.edu.exception.BusinessException;
import com.interactive.edu.exception.ErrorCode;
import com.interactive.edu.service.lecture.LectureService;
import com.interactive.edu.service.qa.QaService;
import com.interactive.edu.service.user.AuthService;
import com.interactive.edu.vo.qa.QaAnswerView;
import jakarta.validation.Valid;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import lombok.RequiredArgsConstructor;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.servlet.mvc.method.annotation.StreamingResponseBody;

@RestController
@RequestMapping("/api/v1/qa")
@RequiredArgsConstructor
@Validated
public class QaController {

    private final QaService qaService;
    private final AuthService authService;
    private final LectureService lectureService;

    @PostMapping("/ask-text")
    public BaseResponse<QaAnswerView> askText(
            @Valid @RequestBody AskTextRequest request,
            @RequestHeader(value = "Authorization", required = false) String authorizationHeader
    ) {
        requireSessionOwner(authService.requireUser(authorizationHeader), request.sessionId());
        return BaseResponse.ok(qaService.askText(request.sessionId(), request.question(), request.pageIndex()));
    }

    @GetMapping(path = "/stream", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    public ResponseEntity<StreamingResponseBody> streamText(
            @RequestParam @NotBlank(message = "sessionId 不能为空") String sessionId,
            @RequestParam @NotBlank(message = "question 不能为空") String question,
            @RequestParam(required = false) @Min(value = 1, message = "pageIndex 必须大于 0") Integer pageIndex,
            @RequestParam(required = false) @Min(value = 1, message = "topK 必须大于 0") Integer topK,
            @RequestParam(required = false) String token
    ) {
        requireSessionOwner(authService.requireUserByToken(token), sessionId);
        return ResponseEntity.ok()
                .contentType(MediaType.TEXT_EVENT_STREAM)
                .body(qaService.streamText(sessionId, question, pageIndex, topK));
    }

    private void requireSessionOwner(AuthService.AuthenticatedUser user, String sessionId) {
        if (!lectureService.getSessionSnapshot(sessionId).userId().equals(user.id())) {
            throw new BusinessException(ErrorCode.FORBIDDEN, "你无权访问该课堂问答");
        }
    }

    public record AskTextRequest(
            @NotBlank(message = "sessionId 不能为空") String sessionId,
            @NotBlank(message = "question 不能为空") String question,
            @Min(value = 1, message = "pageIndex 必须大于 0") Integer pageIndex
    ) {
    }
}
