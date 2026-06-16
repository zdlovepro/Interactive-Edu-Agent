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
@Table(name = "lecture_interrupt_record")
@Getter
@Setter
public class LectureInterruptRecord {

    @Id
    @Column(name = "id", length = 128, nullable = false)
    private String id;

    @Column(name = "session_id", length = 128, nullable = false)
    private String sessionId;

    @Column(name = "courseware_id", length = 64, nullable = false)
    private String coursewareId;

    @Column(name = "page_index")
    private Integer pageIndex;

    @Column(name = "playback_time_seconds")
    private Double currentTime;

    @Column(name = "asr_text", columnDefinition = "TEXT")
    private String asrText;

    @Column(name = "status", length = 32, nullable = false)
    private String status;

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
