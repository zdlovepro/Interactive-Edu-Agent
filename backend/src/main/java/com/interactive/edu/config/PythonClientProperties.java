package com.interactive.edu.config;

import jakarta.annotation.PostConstruct;
import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.core.env.Environment;

import java.time.Duration;
import java.util.Arrays;
import java.util.Set;

@Data
@ConfigurationProperties(prefix = "python.client")
public class PythonClientProperties {
    private static final Set<String> LOCAL_DOCKER_HOST_ALIASES = Set.of(
            "http://python-service:8001",
            "http://python-service",
            "http://backend-python:8001"
    );

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

    /** QA ingest API path, e.g. /python/v1/ingest/pages */
    private String qaIngestPagesPath = "/python/v1/ingest/pages";

    /** Course resource importer API path, e.g. /python/v1/course-resource-import/import */
    private String courseResourceImportPath = "/python/v1/course-resource-import/import";

    /** Chaoxing QR auth API path, e.g. /python/v1/chaoxing/auth/sessions */
    private String chaoxingAuthPath = "/python/v1/chaoxing/auth/sessions";

    /** Courseware video render API path, e.g. /python/v1/video-render/render */
    private String videoRenderPath = "/python/v1/video-render/render";

    /** HTTP connect timeout. */
    private Duration connectTimeout = Duration.ofSeconds(5);

    /** HTTP read timeout. */
    private Duration readTimeout = Duration.ofSeconds(30);

    /** HTTP read timeout for long-running video render requests. */
    private Duration videoRenderReadTimeout = Duration.ofMinutes(60);

    @Autowired
    private Environment environment;

    @PostConstruct
    void normalizeBaseUrlForLocalProfile() {
        String[] activeProfiles = environment.getActiveProfiles();
        boolean localProfileActive = activeProfiles.length == 0
                || Arrays.stream(activeProfiles).anyMatch("local"::equalsIgnoreCase);
        if (!localProfileActive) {
            return;
        }

        String normalized = baseUrl == null ? "" : baseUrl.trim();
        if (LOCAL_DOCKER_HOST_ALIASES.contains(normalized)) {
            baseUrl = "http://localhost:8001";
        }
    }
}
