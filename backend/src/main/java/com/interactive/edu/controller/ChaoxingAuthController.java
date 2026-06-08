package com.interactive.edu.controller;

import com.interactive.edu.dto.BaseResponse;
import com.interactive.edu.dto.chaoxing.ChaoxingAuthSessionCreateRequest;
import com.interactive.edu.service.python.PythonChaoxingAuthClient;
import com.interactive.edu.vo.chaoxing.ChaoxingAuthSessionView;
import jakarta.validation.constraints.NotBlank;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/v1/chaoxing/auth/sessions")
@RequiredArgsConstructor
public class ChaoxingAuthController {

    private final PythonChaoxingAuthClient pythonChaoxingAuthClient;

    @PostMapping
    public BaseResponse<ChaoxingAuthSessionView> createSession(
            @RequestBody(required = false) ChaoxingAuthSessionCreateRequest request
    ) {
        return BaseResponse.ok(pythonChaoxingAuthClient.createSession(request));
    }

    @GetMapping("/{sessionId}")
    public BaseResponse<ChaoxingAuthSessionView> getSession(
            @PathVariable("sessionId") @NotBlank String sessionId
    ) {
        return BaseResponse.ok(pythonChaoxingAuthClient.getSession(sessionId));
    }

    @GetMapping(value = "/{sessionId}/qrcode", produces = MediaType.IMAGE_PNG_VALUE)
    public ResponseEntity<byte[]> getQrCode(
            @PathVariable("sessionId") @NotBlank String sessionId
    ) {
        return ResponseEntity.ok()
                .contentType(MediaType.IMAGE_PNG)
                .header(HttpHeaders.CACHE_CONTROL, "no-store, no-cache, must-revalidate, max-age=0")
                .header(HttpHeaders.PRAGMA, "no-cache")
                .body(pythonChaoxingAuthClient.getQrCode(sessionId));
    }

    @DeleteMapping("/{sessionId}")
    public BaseResponse<ChaoxingAuthSessionView> closeSession(
            @PathVariable("sessionId") @NotBlank String sessionId
    ) {
        return BaseResponse.ok(pythonChaoxingAuthClient.closeSession(sessionId));
    }
}
