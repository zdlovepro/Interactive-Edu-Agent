package com.interactive.edu.dto.courseware;

import jakarta.validation.constraints.Size;
import lombok.Getter;
import lombok.Setter;

@Getter
@Setter
public class UpdateCoursewareCourseCodeRequest {

    @Size(max = 64, message = "courseCode 长度不能超过 64")
    private String courseCode;
}
