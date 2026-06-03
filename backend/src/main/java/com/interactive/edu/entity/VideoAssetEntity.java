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
@Table(name = "video_asset")
@Getter
@Setter
@EntityListeners(AuditingEntityListener.class)
public class VideoAssetEntity {

    @Id
    @Column(name = "id", length = 64, nullable = false)
    private String id;

    @Column(name = "name", length = 255)
    private String name;

    @Column(name = "original_filename", length = 255)
    private String originalFilename;

    @Column(name = "status", length = 32)
    private String status;

    @Column(name = "source_url", length = 1024)
    private String sourceUrl;

    @Column(name = "sample")
    private Boolean sample;

    @CreatedDate
    @Column(name = "create_time", updatable = false)
    private LocalDateTime createTime;

    @LastModifiedDate
    @Column(name = "update_time")
    private LocalDateTime updateTime;
}
