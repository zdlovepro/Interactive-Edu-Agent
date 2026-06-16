package com.interactive.edu.repository;

import com.interactive.edu.entity.LectureInterruptRecord;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;

public interface LectureInterruptRecordRepository extends JpaRepository<LectureInterruptRecord, String> {
    List<LectureInterruptRecord> findBySessionIdOrderByCreateTimeAsc(String sessionId);

    Optional<LectureInterruptRecord> findTopBySessionIdOrderByUpdateTimeDescIdDesc(String sessionId);
}
