package com.interactive.edu.config;

import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;

@Data
@ConfigurationProperties(prefix = "python.client")
public class PythonClientProperties {
    /**
     * e.g. http://localhost:8000
     */
    private String baseUrl = "http://localhost:8000";

    /**
     * e.g. /python/v1/parse
     */
    private String parsePath = "/python/v1/parse";

    /**
     * connect/read timeout (ms)
     */
    private int connectTimeoutMs = 5000;
    private int readTimeoutMs = 30000;
}