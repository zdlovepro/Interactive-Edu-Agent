package com.interactive.edu.dto.courseresourceimport;

import jakarta.validation.constraints.NotBlank;
import lombok.Data;

@Data
public class CreateCourseResourceImportTaskRequest {

    @NotBlank
    private String sourceType;
    private String url;
    private String courseid;
    private String clazzid;
    private String cpi;
    private String enc;
    private String cookie;
    private String authorization;
    private String referer;
    private Boolean buildPdf;
    private Boolean autoParse;
}
