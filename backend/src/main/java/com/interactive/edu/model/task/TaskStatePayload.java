package com.interactive.edu.model.task;

import com.interactive.edu.enums.UnifiedTaskStatus;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.Instant;
import java.util.LinkedHashMap;
import java.util.Map;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class TaskStatePayload {
    private String taskId;
    private UnifiedTaskStatus status;
    private String stage;
    private Integer progress;
    private String message;
    private String errorMessage;
    @Builder.Default
    private Map<String, Object> metadata = new LinkedHashMap<>();
    private Instant updatedAt;
}
