package com.interactive.edu.repository;

import com.interactive.edu.entity.LectureSession;
import org.springframework.data.jpa.repository.JpaRepository;

public interface LectureSessionRepository extends JpaRepository<LectureSession, String> {
}
