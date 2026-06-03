package com.interactive.edu.entity;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EntityListeners;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import lombok.Getter;
import lombok.Setter;
import org.springframework.data.annotation.CreatedDate;
import org.springframework.data.jpa.domain.support.AuditingEntityListener;

import java.time.LocalDateTime;

@Entity
@Table(name = "chaoxing_resource")
@Getter
@Setter
@EntityListeners(AuditingEntityListener.class)
public class ChaoxingResourceEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "task_id", length = 64, nullable = false)
    private String taskId;

    @Column(name = "resource_id", length = 128)
    private String resourceId;

    @Column(name = "title", length = 512)
    private String title;

    @Column(name = "file_name", length = 255)
    private String fileName;

    @Column(name = "resource_kind", length = 64)
    private String resourceKind;

    @Column(name = "status", length = 32)
    private String status;

    @Column(name = "local_path", length = 1024)
    private String localPath;

    @Column(name = "mime_type", length = 128)
    private String mimeType;

    @Column(name = "source_url", length = 1024)
    private String sourceUrl;

    @Column(name = "confidence")
    private Double confidence;

    @Column(name = "reason", columnDefinition = "TEXT")
    private String reason;

    @CreatedDate
    @Column(name = "create_time", updatable = false)
    private LocalDateTime createTime;
}
