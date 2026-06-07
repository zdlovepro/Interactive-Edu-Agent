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
import org.springframework.data.annotation.LastModifiedDate;
import org.springframework.data.jpa.domain.support.AuditingEntityListener;

import java.time.LocalDateTime;

@Entity
@Table(name = "hls_asset")
@Getter
@Setter
@EntityListeners(AuditingEntityListener.class)
public class HlsAssetEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "video_asset_id", length = 64, nullable = false)
    private String videoAssetId;

    @Column(name = "playlist_url", length = 1024)
    private String playlistUrl;

    @Column(name = "segment_urls_json", columnDefinition = "LONGTEXT")
    private String segmentUrlsJson;

    @Column(name = "status", length = 32)
    private String status;

    @CreatedDate
    @Column(name = "create_time", updatable = false)
    private LocalDateTime createTime;

    @LastModifiedDate
    @Column(name = "update_time")
    private LocalDateTime updateTime;
}
