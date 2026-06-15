package com.interactive.edu.service.tts;

import com.interactive.edu.client.TtsClient;
import com.interactive.edu.config.TtsProperties;
import com.interactive.edu.dto.tts.TtsRequest;
import com.interactive.edu.dto.tts.TtsResult;
import com.interactive.edu.storage.TtsAudioStorageService;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;

import java.util.concurrent.CompletableFuture;
import java.util.concurrent.Executor;

/**
 * Main-chain TTS facade.
 * <p>
 * This service is intentionally best-effort:
 * when TTS is disabled, misconfigured, or temporarily unavailable,
 * it returns {@code null} instead of failing the script-generation flow.
 */
@Service
@Slf4j
public class TtsService {

    private static final int MAX_TTS_TEXT_LENGTH = 1000;

    private final TtsProperties ttsProperties;
    private final ObjectProvider<TtsClient> ttsClientProvider;
    private final ObjectProvider<TtsAudioStorageService> audioStorageServiceProvider;
    private final Executor ttsTaskExecutor;

    public TtsService(
            TtsProperties ttsProperties,
            ObjectProvider<TtsClient> ttsClientProvider,
            ObjectProvider<TtsAudioStorageService> audioStorageServiceProvider,
            @Qualifier("ttsTaskExecutor") Executor ttsTaskExecutor
    ) {
        this.ttsProperties = ttsProperties;
        this.ttsClientProvider = ttsClientProvider;
        this.audioStorageServiceProvider = audioStorageServiceProvider;
        this.ttsTaskExecutor = ttsTaskExecutor;
    }

    public String synthesizeToAudioUrl(String text) {
        String normalizedText = normalizeText(text);
        if (!StringUtils.hasText(normalizedText)) {
            return null;
        }

        if (!ttsProperties.isEnabled()) {
            return null;
        }

        if (!hasAliyunCredentials()) {
            log.warn("TTS is enabled but DashScope API key is missing. Skip audio generation.");
            return null;
        }

        TtsClient ttsClient = ttsClientProvider.getIfAvailable();
        TtsAudioStorageService storageService = audioStorageServiceProvider.getIfAvailable();
        if (ttsClient == null || storageService == null) {
            log.warn("TTS is enabled but runtime beans are unavailable. clientPresent={}, storagePresent={}",
                    ttsClient != null, storageService != null);
            return null;
        }

        int maxAttempts = Math.max(1, ttsProperties.getRetryCount() + 1);
        for (int attempt = 1; attempt <= maxAttempts; attempt++) {
            try {
                return synthesizeOnce(normalizedText, ttsClient, storageService);
            } catch (Exception ex) {
                if (attempt >= maxAttempts) {
                    log.warn(
                            "TTS generation failed after {} attempts, degrade to text-only flow. reason={}",
                            maxAttempts,
                            ex.getMessage()
                    );
                    log.debug("TTS generation failure details", ex);
                    return null;
                }

                long backoffMillis = Math.max(0L, ttsProperties.getRetryBackoffMillis()) * attempt;
                log.warn(
                        "TTS generation attempt {}/{} failed, will retry in {} ms. reason={}",
                        attempt,
                        maxAttempts,
                        backoffMillis,
                        ex.getMessage()
                );
                sleepBeforeRetry(backoffMillis);
            }
        }

        return null;
    }

    public CompletableFuture<String> synthesizeToAudioUrlAsync(String text) {
        return CompletableFuture.supplyAsync(() -> synthesizeToAudioUrl(text), ttsTaskExecutor);
    }

    public boolean canGenerateAudio() {
        if (!ttsProperties.isEnabled() || !hasAliyunCredentials()) {
            return false;
        }
        return ttsClientProvider.getIfAvailable() != null
                && audioStorageServiceProvider.getIfAvailable() != null;
    }

    private boolean hasAliyunCredentials() {
        TtsProperties.Aliyun aliyun = ttsProperties.getAliyun();
        return aliyun != null
                && StringUtils.hasText(aliyun.getApiKey());
    }

    private String synthesizeOnce(
            String normalizedText,
            TtsClient ttsClient,
            TtsAudioStorageService storageService
    ) {
        TtsResult result = ttsClient.synthesize(TtsRequest.builder()
                .text(normalizedText)
                .build());

        if (result == null || result.getAudioData() == null || result.getAudioData().length == 0) {
            throw new IllegalStateException("TTS returned empty audio data");
        }

        String format = StringUtils.hasText(result.getFormat()) ? result.getFormat() : "wav";
        String objectKey = storageService.generateObjectKey(format);
        String audioUrl = storageService.uploadAndSign(objectKey, result.getAudioData(), format, null);
        log.info("TTS generation succeeded. format={}, audioBytes={}", format, result.getAudioData().length);
        return audioUrl;
    }

    private String normalizeText(String text) {
        if (!StringUtils.hasText(text)) {
            return null;
        }
        String normalized = text.trim();
        if (normalized.length() <= MAX_TTS_TEXT_LENGTH) {
            return normalized;
        }
        log.info("TTS source text is too long ({} chars). Truncate to {} chars for synthesis.",
                normalized.length(), MAX_TTS_TEXT_LENGTH);
        return normalized.substring(0, MAX_TTS_TEXT_LENGTH);
    }

    private void sleepBeforeRetry(long backoffMillis) {
        if (backoffMillis <= 0) {
            return;
        }
        try {
            Thread.sleep(backoffMillis);
        } catch (InterruptedException ex) {
            Thread.currentThread().interrupt();
            throw new IllegalStateException("Interrupted while waiting for TTS retry", ex);
        }
    }
}
