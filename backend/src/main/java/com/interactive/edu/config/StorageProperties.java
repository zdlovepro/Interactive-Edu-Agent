package com.interactive.edu.config;

import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;

@Data
@ConfigurationProperties(prefix = "storage")
public class StorageProperties {
    /**
     * minio | local
     */
    private String type = "local";

    /**
     * for local storage, e.g. ./data/courseware
     */
    private String localBaseDir = "./data/courseware";
}
