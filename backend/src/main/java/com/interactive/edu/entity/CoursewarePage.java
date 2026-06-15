package com.interactive.edu.entity;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.PrePersist;
import jakarta.persistence.Table;
import lombok.Getter;
import lombok.Setter;
import org.springframework.data.annotation.CreatedDate;
import org.springframework.data.jpa.domain.support.AuditingEntityListener;
import jakarta.persistence.EntityListeners;

import java.time.LocalDateTime;

@Entity
@Table(name = "courseware_page")
@Getter
@Setter
@EntityListeners(AuditingEntityListener.class)
public class CoursewarePage {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "courseware_id", length = 64, nullable = false)
    private String coursewareId;

    @Column(name = "page_index", nullable = false)
    private Integer pageIndex;

    @Column(name = "title", length = 255)
    private String title;

    @Column(name = "original_text", columnDefinition = "TEXT")
    private String originalText;

    @Column(name = "knowledge_points_json", columnDefinition = "TEXT")
    private String knowledgePointsJson;

    @Column(name = "image_url", length = 512)
    private String imageUrl;

    @Column(name = "visual_summary", columnDefinition = "TEXT")
    private String visualSummary;

    @Column(name = "visual_objects_json", columnDefinition = "TEXT")
    private String visualObjectsJson;

    @CreatedDate
    @Column(name = "create_time", updatable = false)
    private LocalDateTime createTime;

    @PrePersist
    void prePersist() {
        if (createTime == null) {
            createTime = LocalDateTime.now();
        }
    }
}
