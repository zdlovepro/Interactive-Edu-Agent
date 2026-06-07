package com.interactive.edu.repository;

import com.interactive.edu.entity.ChaoxingResourceEntity;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;

public interface ChaoxingResourceRepository extends JpaRepository<ChaoxingResourceEntity, Long> {
    List<ChaoxingResourceEntity> findByTaskIdOrderByIdAsc(String taskId);
    void deleteByTaskId(String taskId);
}
