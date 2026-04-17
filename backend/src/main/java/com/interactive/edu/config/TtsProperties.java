package com.interactive.edu.config;

import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.context.annotation.Configuration;

@Data
@Configuration
@ConfigurationProperties(prefix = "interactive.edu.tts")
public class TtsProperties {
    /**
     * TTS 服务提供商，支持 mock, azure, baidu 等
     * 默认为 mock
     */
    private String provider = "mock";
    
    private Azure azure = new Azure();

    @Data
    public static class Azure {
        private String region;
        private String apiKey;
        private String voiceName = "zh-CN-XiaoxiaoNeural";
    }
}
