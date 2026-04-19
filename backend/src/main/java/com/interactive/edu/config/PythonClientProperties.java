package com.interactive.edu.config;

import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;

import java.time.Duration;

@Data
@ConfigurationProperties(prefix = "python.client")
public class PythonClientProperties {
    /**
     * e.g. http://localhost:8001
     */
    private String baseUrl = "http://localhost:8001";

    /**
     * e.g. /python/v1/parse
     */
    private String parsePath = "/python/v1/parse";

    /**
     * connect/read timeout
     */
    private Duration connectTimeout = Duration.ofSeconds(5);
    private Duration readTimeout = Duration.ofSeconds(30);
}
