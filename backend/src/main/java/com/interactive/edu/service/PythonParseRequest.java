package com.interactive.edu.service.python;

import lombok.AllArgsConstructor;
import lombok.Data;

@Data
@AllArgsConstructor
public class PythonParseRequest {
    private String coursewareId;
    private String storage;   // minio | local
    private String key;       // objectKey or relativePath
    private String fileName;
    private String contentType;
}
