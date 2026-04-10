package com.interactive.edu.entity;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import lombok.Getter;
import lombok.Setter;
import org.springframework.data.annotation.CreatedDate;
import org.springframework.data.jpa.domain.support.AuditingEntityListener;
import jakarta.persistence.EntityListeners;

import java.time.LocalDateTime;

@Entity
@Table(name = "qa_record")
@Getter
@Setter
@EntityListeners(AuditingEntityListener.class)
public class QaRecord {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "session_id", length = 128, nullable = false)
    private String sessionId;

    @Column(name = "courseware_id", length = 64, nullable = false)
    private String coursewareId;

    @Column(name = "node_id", length = 64)
    private String nodeId;

    @Column(name = "user_id", length = 64, nullable = false)
    private String userId;

    @Column(name = "ask_text", columnDefinition = "TEXT", nullable = false)
    private String askText;

    @Column(name = "answer_text", columnDefinition = "TEXT")
    private String answerText;

    // Optional mapped field to JSON metadata, using JSON or varchar since length can be large
    @Column(name = "reference_fragments", columnDefinition = "JSON")
    private String referenceFragments;

    @CreatedDate
    @Column(name = "create_time", updatable = false)
    private LocalDateTime createTime;
}
