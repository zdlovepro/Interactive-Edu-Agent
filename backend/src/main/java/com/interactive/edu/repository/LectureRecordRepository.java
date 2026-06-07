package com.interactive.edu.repository;

import com.interactive.edu.entity.LectureRecordEntity;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;

public interface LectureRecordRepository extends JpaRepository<LectureRecordEntity, Long> {
    List<LectureRecordEntity> findByCoursewareIdOrderByCreateTimeDesc(String coursewareId);
}
