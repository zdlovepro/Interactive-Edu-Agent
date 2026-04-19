package com.interactive.edu.service.tts.impl;

import com.interactive.edu.config.TtsProperties;
import com.interactive.edu.service.tts.TtsService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Service;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.util.concurrent.CompletableFuture;

/**
 * Azure 认知服务 TTS 实现
 * 基于云厂商标准 REST API
 */
@Slf4j
@Service
@RequiredArgsConstructor
@ConditionalOnProperty(prefix = "interactive.edu.tts", name = "provider", havingValue = "azure")
public class AzureTtsServiceImpl implements TtsService {

    private final TtsProperties ttsProperties;
    
    // 复用 HttpClient 提高连接效率
    private final HttpClient httpClient = HttpClient.newBuilder()
            .connectTimeout(Duration.ofSeconds(10))
            .build();

    @Override
    public byte[] generateAudioSync(String text) {
        log.info("调用 Azure TTS 同步请求，文本长度: {}", text.length());
        try {
            HttpRequest request = buildRequest(text);
            HttpResponse<byte[]> response = httpClient.send(request, HttpResponse.BodyHandlers.ofByteArray());
            if (response.statusCode() == 200) {
                return response.body();
            } else {
                log.error("Azure TTS 请求响应失败, 状态码: {}, 返回体脱敏: {}", response.statusCode(), 
                        new String(response.body()).length() > 50 ? "部分截断" : new String(response.body()));
                throw new RuntimeException("Azure TTS 调用异常, HTTPS Code: " + response.statusCode());
            }
        } catch (Exception e) {
            log.error("Azure TTS 服务同步调用出现内部错误", e);
            throw new RuntimeException("生成音频失败", e);
        }
    }

    @Override
    public CompletableFuture<byte[]> generateAudioAsync(String text) {
        log.info("调用 Azure TTS 异步请求，文本长度: {}", text.length());
        try {
            HttpRequest request = buildRequest(text);
            return httpClient.sendAsync(request, HttpResponse.BodyHandlers.ofByteArray())
                    .thenApply(response -> {
                        if (response.statusCode() == 200) {
                            return response.body();
                        } else {
                            log.error("Azure TTS 异步响应失败, 状态码: {}", response.statusCode());
                            throw new RuntimeException("Azure TTS 异步异常, HTTPS Code: " + response.statusCode());
                        }
                    });
        } catch (Exception e) {
            log.error("构建 Azure TTS 异步请求失败", e);
            CompletableFuture<byte[]> failedFuture = new CompletableFuture<>();
            failedFuture.completeExceptionally(e);
            return failedFuture;
        }
    }

    /**
     * 构建发送给 Azure TTS 的 HTTP 请求
     */
    private HttpRequest buildRequest(String text) {
        TtsProperties.Azure azureConfig = ttsProperties.getAzure();
        
        // 此处避免硬编码 URL、Key、Region 等
        String urLString = String.format("https://%s.tts.speech.microsoft.com/cognitiveservices/v1", azureConfig.getRegion());
        
        // 简单转移文本防止破坏 XML 结构
        String escapedText = text.replace("&", "&amp;")
                                 .replace("<", "&lt;")
                                 .replace(">", "&gt;");
        
        // 按照 Azure 官方的 SSML 格式协议编写
        String body = String.format(
                "<speak version='1.0' xml:lang='zh-CN'><voice xml:lang='zh-CN' name='%s'>%s</voice></speak>",
                azureConfig.getVoiceName(),
                escapedText
        );

        return HttpRequest.newBuilder()
                .uri(URI.create(urLString))
                .header("Ocp-Apim-Subscription-Key", azureConfig.getApiKey())
                .header("Content-Type", "application/ssml+xml")
                .header("X-Microsoft-OutputFormat", "audio-16khz-128kbitrate-mono-mp3")
                .POST(HttpRequest.BodyPublishers.ofString(body))
                .build();
    }
}
