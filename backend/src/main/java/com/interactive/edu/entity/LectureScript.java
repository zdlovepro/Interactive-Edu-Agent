package com.interactive.edu.entity;

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
@Table(name = "lecture_script")
@Getter
@Setter
@EntityListeners(AuditingEntityListener.class)
public class LectureScript {

    @Id
    @Column(name = "id", length = 64, nullable = false)
    private String id;

    @Column(name = "courseware_id", length = 64, nullable = false)
    private String coursewareId;

    @Column(name = "page_index", nullable = false)
    private Integer pageIndex;

    @Column(name = "node_id", length = 64, nullable = false, unique = true)
    private String nodeId;

    @Column(name = "title", length = 255)
    private String title;

    @Column(name = "content", columnDefinition = "TEXT")
    private String content;

    @Column(name = "knowledge_points_json", columnDefinition = "TEXT")
    private String knowledgePointsJson;

    @Column(name = "audio_url", length = 512)
    private String audioUrl;

    @Column(name = "page_image_url", length = 512)
    private String pageImageUrl;

    @Column(name = "visual_summary", columnDefinition = "TEXT")
    private String visualSummary;

    @Column(name = "visual_objects_json", columnDefinition = "TEXT")
    private String visualObjectsJson;

    @Column(name = "digital_human_enabled", nullable = false)
    private Boolean digitalHumanEnabled = Boolean.FALSE;

    // AUTO, EDITED
    @Column(name = "edit_status", length = 32)
    private String editStatus = "AUTO";

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
