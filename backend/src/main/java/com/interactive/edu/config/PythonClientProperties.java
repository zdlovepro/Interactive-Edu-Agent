package com.interactive.edu.config;

import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;

import java.time.Duration;

@Data
@ConfigurationProperties(prefix = "python.client")
public class PythonClientProperties {
    /** Python service base URL, e.g. http://localhost:8001 */
    private String baseUrl = "http://localhost:8001";

    /** Parse API path, e.g. /python/v1/parse */
    private String parsePath = "/python/v1/parse";

    /** Script generation API path, e.g. /python/v1/script/generate */
    private String scriptGeneratePath = "/python/v1/script/generate";

    /** QA API path, e.g. /python/v1/qa/ask-text */
    private String qaPath = "/python/v1/qa/ask-text";

    /** QA SSE API path, e.g. /python/v1/qa/stream */
    private String qaStreamPath = "/python/v1/qa/stream";

    /** Course resource import API path. */
    private String courseResourceImportPath = "/python/v1/course-resource-import/import";

    /** Digital-human audio-drive API path. */
    private String digitalHumanAudioDrivePath = "/python/v1/digital-human/audio-drive";

    /** Optional visual QA API path. */
    private String visualQaPath = "/python/v1/rag/visual-ask";

    /** HTTP connect timeout. */
    private Duration connectTimeout = Duration.ofSeconds(5);

    /** HTTP read timeout. */
    private Duration readTimeout = Duration.ofSeconds(30);
}
