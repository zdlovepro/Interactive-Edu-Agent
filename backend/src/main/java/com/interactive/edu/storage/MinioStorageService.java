package com.interactive.edu.service.storage;

import com.interactive.edu.config.MinioProperties;
import io.minio.MinioClient;
import io.minio.PutObjectArgs;
import io.minio.MakeBucketArgs;
import io.minio.BucketExistsArgs;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.web.multipart.MultipartFile;

import java.io.InputStream;

@Service
@RequiredArgsConstructor
public class MinioStorageService implements StorageService {

    private final MinioClient minioClient;
    private final MinioProperties minioProperties;

    @Override
    public StoredObject save(String coursewareId, MultipartFile file) {
        try {
            ensureBucket();

            String filename = file.getOriginalFilename() == null ? "courseware.bin" : file.getOriginalFilename();
            String objectKey = coursewareId + "/" + filename;

            try (InputStream in = file.getInputStream()) {
                minioClient.putObject(
                        PutObjectArgs.builder()
                                .bucket(minioProperties.getBucket())
                                .object(objectKey)
                                .stream(in, file.getSize(), -1)
                                .contentType(file.getContentType())
                                .build()
                );
            }

            return new StoredObject(objectKey, "minio");
        } catch (Exception e) {
            throw new RuntimeException("MinIO 存储失败: " + e.getMessage(), e);
        }
    }

    private void ensureBucket() throws Exception {
        boolean exists = minioClient.bucketExists(
                BucketExistsArgs.builder().bucket(minioProperties.getBucket()).build()
        );
        if (!exists) {
            minioClient.makeBucket(MakeBucketArgs.builder().bucket(minioProperties.getBucket()).build());
        }
    }
}