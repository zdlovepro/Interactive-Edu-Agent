package com.interactive.edu.repository;

import com.interactive.edu.entity.HlsAssetEntity;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Optional;

public interface HlsAssetRepository extends JpaRepository<HlsAssetEntity, Long> {
    Optional<HlsAssetEntity> findFirstByVideoAssetIdOrderByCreateTimeDesc(String videoAssetId);
}
