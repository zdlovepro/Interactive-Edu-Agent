package com.interactive.edu.storage;

import org.springframework.web.multipart.MultipartFile;

public interface StorageService {
    StoredObject save(String coursewareId, MultipartFile file);
}
