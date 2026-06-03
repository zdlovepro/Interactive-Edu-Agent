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
@Table(name = "digital_human_task")
@Getter
@Setter
@EntityListeners(AuditingEntityListener.class)
public class DigitalHumanTaskEntity {

    @Id
    @Column(name = "id", length = 64, nullable = false)
    private String id;

    @Column(name = "courseware_id", length = 64, nullable = false)
    private String coursewareId;

    @Column(name = "page_no")
    private Integer pageNo;

    @Column(name = "script_id", length = 64)
    private String scriptId;

    @Column(name = "audio_url", length = 1024)
    private String audioUrl;

    @Column(name = "mode", length = 32)
    private String mode;

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

    @Column(name = "timeline_json", columnDefinition = "LONGTEXT")
    private String timelineJson;

    @Column(name = "phonemes_json", columnDefinition = "LONGTEXT")
    private String phonemesJson;

    @Column(name = "action_frames_json", columnDefinition = "LONGTEXT")
    private String actionFramesJson;

    @Column(name = "audio_json", columnDefinition = "TEXT")
    private String audioJson;

    @Column(name = "protocol_json", columnDefinition = "LONGTEXT")
    private String protocolJson;

    @Column(name = "protocol_xml", columnDefinition = "LONGTEXT")
    private String protocolXml;

    @Column(name = "warnings_json", columnDefinition = "TEXT")
    private String warningsJson;

    @Column(name = "video_asset_id", length = 64)
    private String videoAssetId;

    @Column(name = "video_url", length = 1024)
    private String videoUrl;

    @Column(name = "hls_asset_id", length = 64)
    private String hlsAssetId;

    @Column(name = "hls_url", length = 1024)
    private String hlsUrl;

    @CreatedDate
    @Column(name = "create_time", updatable = false)
    private LocalDateTime createTime;

    @LastModifiedDate
    @Column(name = "update_time")
    private LocalDateTime updateTime;
}
