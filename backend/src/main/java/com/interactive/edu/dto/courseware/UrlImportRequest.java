package com.interactive.edu.dto.courseware;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import lombok.Data;

@Data
public class UrlImportRequest {

    @NotBlank(message = "url must not be blank")
    @Size(max = 2048, message = "url length must be <= 2048")
    private String url;

    @Size(max = 255, message = "name length must be <= 255")
    private String name;
}
