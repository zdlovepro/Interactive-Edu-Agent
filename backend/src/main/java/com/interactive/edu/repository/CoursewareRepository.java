package com.interactive.edu.repository;

import com.interactive.edu.entity.Courseware;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.Optional;

@Repository
public interface CoursewareRepository extends JpaRepository<Courseware, String> {
    Optional<Courseware> findFirstByCourseCodeIgnoreCase(String courseCode);

    Optional<Courseware> findFirstByCourseCodeIgnoreCaseAndIdNot(String courseCode, String id);
}
