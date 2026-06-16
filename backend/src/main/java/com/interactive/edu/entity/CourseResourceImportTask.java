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
@Table(name = "course_resource_import_task")
@Getter
@Setter
public class CourseResourceImportTask {

    @Id
    @Column(name = "id", length = 128, nullable = false)
    private String id;

    @Column(name = "user_id", length = 64, nullable = false)
    private String userId;

    @Column(name = "source_type", length = 64, nullable = false)
    private String sourceType;

    @Column(name = "source_url", length = 1024)
    private String sourceUrl;

    @Column(name = "courseid", length = 128)
    private String courseid;

    @Column(name = "clazzid", length = 128)
    private String clazzid;

    @Column(name = "cpi", length = 128)
    private String cpi;

    @Column(name = "enc", length = 255)
    private String enc;

    @Column(name = "referer", length = 1024)
    private String referer;

    @Column(name = "build_pdf", nullable = false)
    private Boolean buildPdf = Boolean.FALSE;

    @Column(name = "auto_parse", nullable = false)
    private Boolean autoParse = Boolean.FALSE;

    @Column(name = "output_dir", length = 1024)
    private String outputDir;

    @Column(name = "status", length = 32, nullable = false)
    private String status;

    @Column(name = "progress", nullable = false)
    private Integer progress = 0;

    @Column(name = "discovered_count", nullable = false)
    private Integer discoveredCount = 0;

    @Column(name = "selected_count", nullable = false)
    private Integer selectedCount = 0;

    @Column(name = "downloaded_count", nullable = false)
    private Integer downloadedCount = 0;

    @Column(name = "ignored_count", nullable = false)
    private Integer ignoredCount = 0;

    @Column(name = "generated_pdf", length = 1024)
    private String generatedPdf;

    @Column(name = "message", length = 1024)
    private String message;

    @Column(name = "courseware_id", length = 64)
    private String coursewareId;

    @Column(name = "files_json", columnDefinition = "LONGTEXT")
    private String filesJson;

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
