package com.interactive.edu.entity;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EntityListeners;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import lombok.Getter;
import lombok.Setter;
import org.springframework.data.annotation.CreatedDate;
import org.springframework.data.annotation.LastModifiedDate;
import org.springframework.data.jpa.domain.support.AuditingEntityListener;

import java.time.LocalDateTime;

@Entity
@Table(name = "chaoxing_import_task")
@Getter
@Setter
@EntityListeners(AuditingEntityListener.class)
public class ChaoxingImportTaskEntity {

    @Id
    @Column(name = "id", length = 64, nullable = false)
    private String id;

    @Column(name = "course_url", length = 1024)
    private String courseUrl;

    @Column(name = "course_id", length = 64)
    private String courseId;

    @Column(name = "clazz_id", length = 64)
    private String clazzId;

    @Column(name = "cpi", length = 64)
    private String cpi;

    @Column(name = "enc", length = 255)
    private String enc;

    @Column(name = "owner_user_id", length = 64)
    private String ownerUserId;

    @Column(name = "status", length = 32, nullable = false)
    private String status;

    @Column(name = "stage", length = 64)
    private String stage;

    @Column(name = "progress")
    private Integer progress;

    @Column(name = "message", length = 1024)
    private String message;

    @Column(name = "error_message", columnDefinition = "TEXT")
    private String errorMessage;

    @Column(name = "output_dir", length = 1024)
    private String outputDir;

    @Column(name = "manifest_path", length = 1024)
    private String manifestPath;

    @Column(name = "parse_ready_manifest_path", length = 1024)
    private String parseReadyManifestPath;

    @Column(name = "generated_pdf", length = 1024)
    private String generatedPdf;

    @Column(name = "courseware_id", length = 64)
    private String coursewareId;

    @CreatedDate
    @Column(name = "create_time", updatable = false)
    private LocalDateTime createTime;

    @LastModifiedDate
    @Column(name = "update_time")
    private LocalDateTime updateTime;
}
