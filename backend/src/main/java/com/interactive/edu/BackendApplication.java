package com.interactive.edu;

import com.interactive.edu.config.PythonClientProperties;
import com.interactive.edu.config.StorageProperties;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.data.jpa.repository.config.EnableJpaAuditing;
import org.springframework.boot.context.properties.EnableConfigurationProperties;

@EnableJpaAuditing
@SpringBootApplication
@EnableConfigurationProperties({StorageProperties.class, PythonClientProperties.class})
public class BackendApplication {
    public static void main(String[] args) {
        SpringApplication.run(BackendApplication.class, args);
    }
}