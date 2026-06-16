package com.interactive.edu.repository;

import com.interactive.edu.entity.CourseResourceImportTask;
import org.springframework.data.jpa.repository.JpaRepository;

public interface CourseResourceImportTaskRepository extends JpaRepository<CourseResourceImportTask, String> {
}
