package com.interactive.edu.dto.courseware;

import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotEmpty;
import lombok.Data;

import java.util.List;

@Data
public class UpdateCoursewareScriptRequest {

    private boolean regenerateAudio = true;

    @Valid
    @NotEmpty
    private List<Segment> segments;

    @Data
    public static class Segment {

        @NotBlank
        private String id;

        @NotBlank
        private String title;

        @NotBlank
        private String content;

        private Boolean digitalHumanEnabled;
    }
}
