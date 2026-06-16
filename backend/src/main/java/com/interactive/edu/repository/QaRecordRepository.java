package com.interactive.edu.repository;

import com.interactive.edu.entity.QaRecord;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;

public interface QaRecordRepository extends JpaRepository<QaRecord, Long> {
    List<QaRecord> findBySessionIdOrderByCreateTimeAsc(String sessionId);
}
