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
@Table(name = "lecture_record")
@Getter
@Setter
@EntityListeners(AuditingEntityListener.class)
public class LectureRecordEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "courseware_id", length = 64, nullable = false)
    private String coursewareId;

    @Column(name = "page_no")
    private Integer pageNo;

    @Column(name = "record_type", length = 64, nullable = false)
    private String recordType;

    @Column(name = "payload_json", columnDefinition = "LONGTEXT")
    private String payloadJson;

    @CreatedDate
    @Column(name = "create_time", updatable = false)
    private LocalDateTime createTime;
}
