package com.interactive.edu;

import com.interactive.edu.config.AsrProperties;
import com.interactive.edu.config.CorsProperties;
import com.interactive.edu.config.PythonClientProperties;
import com.interactive.edu.config.StorageProperties;
import com.interactive.edu.config.TtsProperties;
import com.interactive.edu.config.VideoAssetProperties;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.context.properties.EnableConfigurationProperties;

@SpringBootApplication
@EnableConfigurationProperties({
        AsrProperties.class,
        CorsProperties.class,
        StorageProperties.class,
        PythonClientProperties.class,
        TtsProperties.class,
        VideoAssetProperties.class
})
public class BackendApplication {
    public static void main(String[] args) {
        SpringApplication.run(BackendApplication.class, args);
    }
}
