package com.interactive.edu.repository;

import com.interactive.edu.entity.LectureScript;
import jakarta.transaction.Transactional;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.util.List;

@Repository
public interface LectureScriptRepository extends JpaRepository<LectureScript, String> {
    List<LectureScript> findByCoursewareIdOrderByPageIndexAsc(String coursewareId);

    @Modifying
    @Transactional
    @Query("delete from LectureScript script where script.coursewareId = :coursewareId")
    void deleteByCoursewareId(@Param("coursewareId") String coursewareId);
}
