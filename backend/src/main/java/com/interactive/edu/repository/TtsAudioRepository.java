package com.interactive.edu.repository;

import com.interactive.edu.entity.TtsAudioEntity;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;

public interface TtsAudioRepository extends JpaRepository<TtsAudioEntity, Long> {
    List<TtsAudioEntity> findByCoursewareIdOrderByCreateTimeAsc(String coursewareId);
}
