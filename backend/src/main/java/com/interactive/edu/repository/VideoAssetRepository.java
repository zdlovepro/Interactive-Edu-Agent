package com.interactive.edu.repository;

import com.interactive.edu.entity.VideoAssetEntity;
import org.springframework.data.jpa.repository.JpaRepository;

public interface VideoAssetRepository extends JpaRepository<VideoAssetEntity, String> {
}
