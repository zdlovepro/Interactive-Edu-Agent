package com.interactive.edu.service.courseware;

import com.interactive.edu.dto.CoursewareUploadResult;
import com.interactive.edu.service.python.PythonParseClient;
import com.interactive.edu.service.python.PythonParseRequest;
import com.interactive.edu.service.storage.StoredObject;
import com.interactive.edu.service.storage.StorageService;
import com.interactive.edu.service.storage.StorageServiceFactory;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;
import java.io.InputStream;
import java.util.Collections;
import java.util.UUID;

@Service
@RequiredArgsConstructor
public class CoursewareService {

    private final StorageServiceFactory storageServiceFactory;
    private final PythonParseClient pythonParseClient;

    public CoursewareUploadResult upload(MultipartFile file) {
        String coursewareId = "cware_" + UUID.randomUUID().toString().replace("-", "");
        String filename = normalizeFilename(file.getOriginalFilename());
        MultipartFile fileForStorage = withOriginalFilename(file, filename);

        StorageService storageService = storageServiceFactory.get();
        StoredObject stored = storageService.save(coursewareId, fileForStorage);

        // 异步调用 Python 解析
        pythonParseClient.callParseAsync(
                new PythonParseRequest(
                        coursewareId,
                        stored.getStorageType(),
                        stored.getKey(),
                        filename,
                        file.getContentType()
                )
        );

        return new CoursewareUploadResult(coursewareId, "UPLOADED");
    }

    private String normalizeFilename(String originalFilename) {
        if (originalFilename == null) {
            return "courseware.bin";
        }

        String filename = originalFilename.replace('\u0000', ' ').trim();
        if (filename.isEmpty()) {
            return "courseware.bin";
        }

        filename = filename.replace('\\', '/');
        int lastSlash = filename.lastIndexOf('/');
        if (lastSlash >= 0) {
            filename = filename.substring(lastSlash + 1);
        }

        filename = filename.trim();
        return filename.isEmpty() ? "courseware.bin" : filename;
    }

    private MultipartFile withOriginalFilename(MultipartFile file, String originalFilename) {
        return new MultipartFile() {
            @Override
            public String getName() {
                return file.getName();
            }

            @Override
            public String getOriginalFilename() {
                return originalFilename;
            }

            @Override
            public String getContentType() {
                return file.getContentType();
            }

            @Override
            public boolean isEmpty() {
                return file.isEmpty();
            }

            @Override
            public long getSize() {
                return file.getSize();
            }

            @Override
            public byte[] getBytes() throws IOException {
                return file.getBytes();
            }

            @Override
            public InputStream getInputStream() throws IOException {
                return file.getInputStream();
            }

            @Override
            public void transferTo(java.io.File dest) throws IOException, IllegalStateException {
                file.transferTo(dest);
            }

            @Override
            public java.util.ResourceBundle getResourceBundle() {
                throw new UnsupportedOperationException();
            }

            @Override
            public org.springframework.core.io.Resource getResource() {
                return file.getResource();
            }

            @Override
            public void transferTo(java.nio.file.Path dest) throws IOException, IllegalStateException {
                file.transferTo(dest);
            }

            @Override
            public java.util.Iterator<String> getHeaderNames() {
                return Collections.emptyIterator();
            }

            @Override
            public String getHeader(String name) {
                return null;
            }
        };
    }
}