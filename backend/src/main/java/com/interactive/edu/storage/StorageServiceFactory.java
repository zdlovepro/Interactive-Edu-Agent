package com.interactive.edu.service.storage;

import com.interactive.edu.config.StorageProperties;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Component;

@Component
@RequiredArgsConstructor
public class StorageServiceFactory {

    private final StorageProperties storageProperties;
    private final MinioStorageService minioStorageService;
    private final LocalStorageService localStorageService;

    public StorageService get() {
        String type = storageProperties.getType();
        if (type == null) type = "minio";
        return switch (type.toLowerCase()) {
            case "local" -> localStorageService;
            case "minio" -> minioStorageService;
            default -> throw new IllegalArgumentException("不支持的 storage.type: " + type);
        };
    }
}