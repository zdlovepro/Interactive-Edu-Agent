package com.interactive.edu.repository;

import com.interactive.edu.entity.VisualQaRecordEntity;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;

public interface VisualQaRecordRepository extends JpaRepository<VisualQaRecordEntity, Long> {
    List<VisualQaRecordEntity> findByCoursewareIdOrderByCreateTimeDesc(String coursewareId);
}
