package com.interactive.edu.config;

import com.interactive.edu.enums.TtsProvider;
import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;

/**
 * TTS 文本转语音配置属性
 * <p>
 * 当前实现对接阿里云 NLS 语音合成服务（流式 HTTP REST API）。
 * 配置前缀：{@code tts}
 */
@Data
@ConfigurationProperties(prefix = "tts")
public class TtsProperties {

    /** 云厂商标识，当前仅支持 {@link TtsProvider#ALIYUN} */
    private TtsProvider provider = TtsProvider.ALIYUN;

    private Aliyun aliyun = new Aliyun();

    @Data
    public static class Aliyun {

        /**
         * 阿里云 NLS 项目 AppKey
         * 在阿里云控制台「智能语音交互」→「项目管理」中获取
         */
        private String appKey;

        /**
         * RAM AccessKeyId
         */
        private String accessKeyId;

        /**
         * RAM AccessKeySecret
         */
        private String accessKeySecret;

        /**
         * NLS 网关地址（默认华东1区）
         */
        private String endpoint = "https://nls-gateway.cn-shanghai.aliyuncs.com";

        /**
         * 默认发音人
         * 常用选项：aixia（女）、aiyu（男）、aijia（标准女）等
         */
        private String voice = "aixia";

        /**
         * 音频采样率（Hz），阿里云 NLS 支持：8000 / 16000
         */
        private int sampleRate = 16000;

        /**
         * 音频输出格式：wav / mp3 / pcm
         */
        private String format = "wav";

        /**
         * 语速控制，取值范围 -500~500，0 为正常语速
         */
        private int speechRate = 0;

        /**
         * 语调控制，取值范围 -500~500，0 为正常语调
         */
        private int pitchRate = 0;

        /**
         * 音量，取值范围 0~100
         */
        private int volume = 50;

        /**
         * HTTP 连接超时（毫秒）
         */
        private int connectTimeoutMs = 5000;

        /**
         * HTTP 读取超时（毫秒）
         * TTS 合成耗时受文本长度影响，建议不低于 30 秒
         */
        private int readTimeoutMs = 30000;

        /**
         * Token 获取路径（相对 endpoint 的路径）
         */
        private String tokenPath = "/token";

        /**
         * 语音合成局程响应路径（相对 endpoint 的路径）
         */
        private String ttsPath = "/stream/v1/tts";
    }
}
