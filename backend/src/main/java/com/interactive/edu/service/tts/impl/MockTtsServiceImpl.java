package com.interactive.edu.service.tts.impl;

import com.interactive.edu.service.tts.TtsService;
import lombok.extern.slf4j.Slf4j;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Service;

import java.util.concurrent.CompletableFuture;

/**
 * 本地 Mock 的 TTS 实现
 * 在未配置真是 TTS 服务时使用，避免阻断研发流程
 */
@Slf4j
@Service
@ConditionalOnProperty(prefix = "interactive.edu.tts", name = "provider", havingValue = "mock", matchIfMissing = true)
public class MockTtsServiceImpl implements TtsService {

    private String summarizeTextForLog(String text) {
        if (text == null) {
            return "null";
        }
        int maxPreviewLength = 100;
        int textLength = text.length();
        String preview = textLength <= maxPreviewLength ? text : text.substring(0, maxPreviewLength) + "...(truncated)";
        return "length=" + textLength + ", preview=" + preview;
    }

    @Override
    public byte[] generateAudioSync(String text) {
        log.info("[MOCK TTS] 模拟进行文本生成语音，文本摘要: {}", summarizeTextForLog(text));
        // 模拟返回空字节流（代表 MP3 数据）
        return new byte[0];
    }

    @Override
    public CompletableFuture<byte[]> generateAudioAsync(String text) {
        log.info("[MOCK TTS] 模拟进行文本生成异步语音，文本摘要: {}", summarizeTextForLog(text));
        return CompletableFuture.completedFuture(new byte[0]);
    }
}
