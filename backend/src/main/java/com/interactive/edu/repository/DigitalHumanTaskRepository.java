package com.interactive.edu.repository;

import com.interactive.edu.entity.DigitalHumanTaskEntity;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;

public interface DigitalHumanTaskRepository extends JpaRepository<DigitalHumanTaskEntity, String> {
    List<DigitalHumanTaskEntity> findByCoursewareIdOrderByCreateTimeDesc(String coursewareId);
    Optional<DigitalHumanTaskEntity> findFirstByCoursewareIdAndPageNoOrderByCreateTimeDesc(String coursewareId, Integer pageNo);
}
