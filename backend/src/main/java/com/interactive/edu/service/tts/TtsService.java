package com.interactive.edu.service.tts;

import java.util.concurrent.CompletableFuture;

/**
 * 文本转语音 (TTS) 统一服务接口
 * 负责提供同步与异步的语音流生成能力
 */
public interface TtsService {

    /**
     * 同步生成语音流
     * @param text 待转换的文本
     * @return 音频流数据（如 MP3 格式的二进制数据）
     */
    byte[] generateAudioSync(String text);

    /**
     * 异步生成语音流
     * @param text 待转换的文本
     * @return 异步返回的音频二进制数据
     */
    CompletableFuture<byte[]> generateAudioAsync(String text);
}
