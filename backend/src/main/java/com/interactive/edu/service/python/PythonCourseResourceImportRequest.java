package com.interactive.edu.service.python;

import lombok.Builder;
import lombok.Value;

import java.nio.file.Path;

@Value
@Builder
public class PythonCourseResourceImportRequest {
    String sourceType;
    String url;
    String courseid;
    String clazzid;
    String cpi;
    String enc;
    String cookie;
    String authorization;
    String referer;
    boolean buildPdf;
    boolean autoParse;
    Path outputDir;
}
