package com.interactive.edu.controller;

import com.interactive.edu.dto.BaseResponse;
import com.interactive.edu.dto.asr.AsrRequest;
import com.interactive.edu.dto.asr.AsrResult;
import com.interactive.edu.exception.BusinessException;
import com.interactive.edu.exception.ErrorCode;
import com.interactive.edu.service.asr.AsrService;
import com.interactive.edu.service.lecture.LectureService;
import com.interactive.edu.service.user.AuthService;
import lombok.RequiredArgsConstructor;
import org.springframework.util.StringUtils;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;

@RestController
@RequestMapping("/api/v1/asr")
@RequiredArgsConstructor
@Validated
public class AsrController {

    private final AsrService asrService;
    private final AuthService authService;
    private final LectureService lectureService;

    @PostMapping("/recognize")
    public BaseResponse<AsrResult> recognize(
            @RequestParam("file") MultipartFile file,
            @RequestParam(value = "sessionId", required = false) String sessionId,
            @RequestParam(value = "pageIndex", required = false) Integer pageIndex,
            @RequestHeader(value = "Authorization", required = false) String authorizationHeader
    ) throws IOException {
        if (file == null || file.isEmpty()) {
            throw new BusinessException(ErrorCode.PARAM_ERROR, "音频文件不能为空");
        }

        if (StringUtils.hasText(sessionId)) {
            AuthService.AuthenticatedUser user = authService.requireUser(authorizationHeader);
            if (!lectureService.getSessionSnapshot(sessionId).userId().equals(user.id())) {
                throw new BusinessException(ErrorCode.FORBIDDEN, "你无权使用该课堂语音识别");
            }
        }

        String contentType = file.getContentType();
        if (!StringUtils.hasText(contentType) && StringUtils.hasText(file.getOriginalFilename())) {
            contentType = inferContentType(file.getOriginalFilename());
        }

        AsrRequest request = AsrRequest.builder()
                .audioData(file.getBytes())
                .filename(file.getOriginalFilename())
                .contentType(contentType)
                .sessionId(sessionId)
                .pageIndex(pageIndex)
                .build();
        return BaseResponse.ok(asrService.recognize(request));
    }

    private String inferContentType(String filename) {
        String lowerFilename = filename.toLowerCase();
        if (lowerFilename.endsWith(".webm")) {
            return "audio/webm";
        }
        if (lowerFilename.endsWith(".wav")) {
            return "audio/wav";
        }
        if (lowerFilename.endsWith(".mp3")) {
            return "audio/mpeg";
        }
        if (lowerFilename.endsWith(".m4a") || lowerFilename.endsWith(".mp4")) {
            return "audio/mp4";
        }
        return null;
    }
}
