package com.interactive.edu.repository;

import com.interactive.edu.entity.CoursewareVideoRenderTask;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

@Repository
public interface CoursewareVideoRenderTaskRepository extends JpaRepository<CoursewareVideoRenderTask, String> {
}
