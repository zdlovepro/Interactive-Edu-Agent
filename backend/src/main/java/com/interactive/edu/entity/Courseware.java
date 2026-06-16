package com.interactive.edu.entity;

import com.interactive.edu.enums.CoursewareStatus;
import com.interactive.edu.enums.TaskStatus;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.PrePersist;
import jakarta.persistence.PreUpdate;
import jakarta.persistence.Table;
import lombok.Getter;
import lombok.Setter;
import org.springframework.data.annotation.CreatedDate;
import org.springframework.data.annotation.LastModifiedDate;
import org.springframework.data.jpa.domain.support.AuditingEntityListener;
import jakarta.persistence.EntityListeners;

import java.time.LocalDateTime;

@Entity
@Table(name = "courseware")
@Getter
@Setter
@EntityListeners(AuditingEntityListener.class)
public class Courseware {

    @Id
    @Column(name = "id", length = 64, nullable = false)
    private String id;

    @Column(name = "name", length = 255, nullable = false)
    private String name;

    @Column(name = "file_url", length = 512, nullable = false)
    private String fileUrl;

    @Column(name = "storage_type", length = 32, nullable = false)
    private String storageType = "local";

    @Column(name = "original_filename", length = 255)
    private String originalFilename;

    @Column(name = "file_type", length = 128, nullable = false)
    private String fileType;

    @Column(name = "status", length = 64, nullable = false)
    private String status = CoursewareStatus.UPLOADED.name();

    @Column(name = "current_task_status", length = 32, nullable = false)
    private String currentTaskStatus = TaskStatus.PENDING.name();

    @Column(name = "script_opening", columnDefinition = "TEXT")
    private String scriptOpening;

    @Column(name = "script_closing", columnDefinition = "TEXT")
    private String scriptClosing;

    @Column(name = "uploader_id", length = 64)
    private String uploaderId;

    @Column(name = "course_code", length = 64)
    private String courseCode;

    @CreatedDate
    @Column(name = "create_time", updatable = false)
    private LocalDateTime createTime;

    @LastModifiedDate
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
