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

import java.util.UUID;

@Service
@RequiredArgsConstructor
public class CoursewareService {

    private final StorageServiceFactory storageServiceFactory;
    private final PythonParseClient pythonParseClient;

    public CoursewareUploadResult upload(MultipartFile file) {
        String coursewareId = "cware_" + UUID.randomUUID().toString().replace("-", "");

        StorageService storageService = storageServiceFactory.get();
        StoredObject stored = storageService.save(coursewareId, file);

        // 异步调用 Python 解析
        String filename = file.getOriginalFilename() == null ? "courseware.bin" : file.getOriginalFilename();
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
}