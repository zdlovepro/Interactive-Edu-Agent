package com.interactive.edu.service.asr;

import com.interactive.edu.client.AsrClient;
import com.interactive.edu.client.impl.LocalMockAsrClient;
import com.interactive.edu.client.impl.QwenAsrClient;
import com.interactive.edu.config.AsrProperties;
import com.interactive.edu.dto.asr.AsrRequest;
import com.interactive.edu.dto.asr.AsrResult;
import com.interactive.edu.exception.BusinessException;
import com.interactive.edu.exception.ErrorCode;
import com.interactive.edu.service.record.LectureRecordService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;

@Service
@RequiredArgsConstructor
@Slf4j
public class AsrService {

    private final AsrProperties properties;
    private final LocalMockAsrClient localMockAsrClient;
    private final QwenAsrClient qwenAsrClient;
    private final LectureRecordService lectureRecordService;

    public AsrResult recognize(AsrRequest request) {
        validateRequest(request);

        AsrClient client = resolveClient();
        AsrResult result = client.recognize(request);
        if (!StringUtils.hasText(result.getText())) {
            throw new BusinessException(ErrorCode.BUSINESS_VALIDATION_FAILED, "语音识别结果为空");
        }

        updateRecordSafely(request.getSessionId(), result.getText(), request.getPageIndex());
        return result;
    }

    private void validateRequest(AsrRequest request) {
        if (request == null || request.getAudioData() == null || request.getAudioData().length == 0) {
            throw new BusinessException(ErrorCode.PARAM_ERROR, "音频文件不能为空");
        }

        long maxBytes = properties.getQwen().getMaxFileSizeMb() * 1024L * 1024L;
        if (request.getAudioData().length > maxBytes) {
            throw new BusinessException(
                    ErrorCode.PARAM_ERROR,
                    "音频文件不能超过 " + properties.getQwen().getMaxFileSizeMb() + "MB"
            );
        }

        if (!StringUtils.hasText(resolveMimeType(request.getContentType(), request.getFilename()))) {
            throw new BusinessException(ErrorCode.PARAM_ERROR, "音频格式不受支持");
        }
    }

    private AsrClient resolveClient() {
        if (!properties.isEnabled()) {
            log.info("ASR disabled. Falling back to local mock provider.");
            return localMockAsrClient;
        }
        if (!"qwen".equalsIgnoreCase(properties.getProvider())) {
            log.info("ASR provider is local or unsupported. provider={}", properties.getProvider());
            return localMockAsrClient;
        }
        if (!StringUtils.hasText(properties.getQwen().getApiKey())) {
            log.warn("Qwen ASR api key missing. Falling back to local mock provider.");
            return localMockAsrClient;
        }
        return qwenAsrClient;
    }

    private void updateRecordSafely(String sessionId, String text, Integer pageIndex) {
        if (!StringUtils.hasText(sessionId) || !StringUtils.hasText(text)) {
            return;
        }
        try {
            lectureRecordService.updateLatestInterruptAsrText(sessionId.trim(), text.trim());
            log.info(
                    "ASR text stored for lecture session. sessionId={}, pageIndex={}, textLength={}",
                    sessionId,
                    pageIndex,
                    text.length()
            );
        } catch (Exception ex) {
            log.warn(
                    "Failed to persist ASR text. sessionId={}, pageIndex={}, reason={}",
                    sessionId,
                    pageIndex,
                    ex.getMessage()
            );
        }
    }

    private String resolveMimeType(String contentType, String filename) {
        if (StringUtils.hasText(contentType)) {
            String normalized = normalizeContentType(contentType);
            if (normalized != null) {
                return normalized;
            }
        }

        return resolveMimeTypeFromFilename(filename);
    }

    private String normalizeContentType(String contentType) {
        if (!StringUtils.hasText(contentType)) {
            return null;
        }

        String baseType = contentType.trim().toLowerCase();
        int separatorIndex = baseType.indexOf(';');
        if (separatorIndex >= 0) {
            baseType = baseType.substring(0, separatorIndex).trim();
        }

        if ("audio/webm".equals(baseType) || "video/webm".equals(baseType)) {
            return "audio/webm";
        }
        if ("audio/wav".equals(baseType) || "audio/x-wav".equals(baseType)) {
            return "audio/wav";
        }
        if ("audio/mpeg".equals(baseType) || "audio/mp3".equals(baseType)) {
            return "audio/mpeg";
        }
        if ("audio/mp4".equals(baseType) || "audio/m4a".equals(baseType)) {
            return "audio/mp4";
        }
        return null;
    }

    private String resolveMimeTypeFromFilename(String filename) {
        if (!StringUtils.hasText(filename)) {
            return null;
        }
        String lowerFilename = filename.trim().toLowerCase();
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
