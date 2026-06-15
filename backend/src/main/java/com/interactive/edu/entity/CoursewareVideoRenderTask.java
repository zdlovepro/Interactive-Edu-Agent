package com.interactive.edu.entity;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.PrePersist;
import jakarta.persistence.PreUpdate;
import jakarta.persistence.Table;
import lombok.Getter;
import lombok.Setter;

import java.time.LocalDateTime;

@Entity
@Table(name = "courseware_video_render_task")
@Getter
@Setter
public class CoursewareVideoRenderTask {

    @Id
    @Column(name = "courseware_id", length = 64, nullable = false)
    private String coursewareId;

    @Column(name = "status", length = 32, nullable = false)
    private String status = "PENDING";

    @Column(name = "progress", nullable = false)
    private Integer progress = 0;

    @Column(name = "message", length = 255)
    private String message;

    @Column(name = "mp4_path", length = 1024)
    private String mp4Path;

    @Column(name = "hls_playlist_path", length = 1024)
    private String hlsPlaylistPath;

    @Column(name = "duration_ms")
    private Long durationMs;

    @Column(name = "segment_count")
    private Integer segmentCount;

    @Column(name = "error_message", length = 1024)
    private String errorMessage;

    @Column(name = "create_time", updatable = false)
    private LocalDateTime createTime;

    @Column(name = "update_time")
    private LocalDateTime updateTime;

    @PrePersist
    void prePersist() {
        LocalDateTime now = LocalDateTime.now();
        if (createTime == null) {
            createTime = now;
        }
        if (updateTime == null) {
            updateTime = now;
        }
    }

    @PreUpdate
    void preUpdate() {
        updateTime = LocalDateTime.now();
    }
}
