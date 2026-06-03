package com.interactive.edu.service.lecture;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.interactive.edu.dto.BaseResponse;
import com.interactive.edu.entity.DigitalHumanTaskEntity;
import com.interactive.edu.entity.LectureRecordEntity;
import com.interactive.edu.model.task.TaskStatePayload;
import com.interactive.edu.repository.LectureRecordRepository;
import com.interactive.edu.service.courseware.CoursewareService;
import com.interactive.edu.service.digitalhuman.DigitalHumanTaskService;
import com.interactive.edu.service.task.TaskStateStore;
import com.interactive.edu.vo.courseware.CoursewareDetailView;
import com.interactive.edu.vo.courseware.ScriptSegmentView;
import com.interactive.edu.vo.lecture.CoursewareLectureStateView;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;

import java.time.Instant;
import java.util.List;
import java.util.Map;

@Service
@RequiredArgsConstructor
public class CoursewareLectureStateService {

    private final CoursewareService coursewareService;
    private final DigitalHumanTaskService digitalHumanTaskService;
    private final TaskStateStore taskStateStore;
    private final ObjectMapper objectMapper;
    private final ObjectProvider<LectureRecordRepository> lectureRecordRepositoryProvider;

    public CoursewareLectureStateView getState(String coursewareId) {
        CoursewareDetailView detailView = coursewareService.getDetail(coursewareId);
        Integer currentPage = resolveCurrentPage(coursewareId);
        List<CoursewareService.PageSnapshot> pages = coursewareService.listPageSnapshots(coursewareId);
        int totalPages = pages.isEmpty() ? 1 : pages.size();
        CoursewareService.PageSnapshot pageSnapshot = coursewareService.getPageSnapshot(coursewareId, currentPage);
        if (pageSnapshot == null && !pages.isEmpty()) {
            pageSnapshot = pages.get(0);
            currentPage = pageSnapshot.pageIndex();
        }
        ScriptSegmentView scriptSegment = resolveScriptSegment(coursewareId, currentPage);
        DigitalHumanTaskEntity digitalHumanTask = digitalHumanTaskService.findLatestByCoursewareAndPage(coursewareId, currentPage);

        return new CoursewareLectureStateView(
                coursewareId,
                detailView.name(),
                StringUtils.hasText(coursewareService.getSourceType(coursewareId))
                        ? coursewareService.getSourceType(coursewareId)
                        : "LOCAL",
                currentPage,
                totalPages,
                pageSnapshot == null ? null : pageSnapshot.text(),
                buildPageImageApiUrl(coursewareId, currentPage, pageSnapshot == null ? null : pageSnapshot.imageUrl()),
                coursewareService.findScriptIdByPage(coursewareId, currentPage),
                scriptSegment == null ? null : scriptSegment.content(),
                scriptSegment == null ? null : scriptSegment.audioUrl(),
                digitalHumanTask == null ? null : digitalHumanTask.getId(),
                digitalHumanTask == null ? null : digitalHumanTask.getStatus(),
                digitalHumanTask == null ? null : digitalHumanTask.getVideoUrl(),
                digitalHumanTask == null ? null : digitalHumanTask.getHlsUrl()
        );
    }

    public CoursewareLectureStateView updateProgress(String coursewareId, ProgressRequest request) {
        int currentPage = request.currentPage() == null || request.currentPage() <= 0 ? 1 : request.currentPage();
        taskStateStore.save(
                "lecture_state:" + coursewareId,
                TaskStatePayload.builder()
                        .taskId(coursewareId)
                        .status(com.interactive.edu.enums.UnifiedTaskStatus.RUNNING)
                        .stage("lecture-progress")
                        .progress(0)
                        .message("Lecture progress updated")
                        .updatedAt(Instant.now())
                        .metadata(Map.of(
                                "currentPage", currentPage,
                                "status", StringUtils.hasText(request.status()) ? request.status() : "ACTIVE"
                        ))
                        .build()
        );
        persistLectureRecord(coursewareId, "PROGRESS", request);
        return getState(coursewareId);
    }

    public BaseResponse<String> appendRecord(String coursewareId, RecordRequest request) {
        persistLectureRecord(coursewareId, StringUtils.hasText(request.recordType()) ? request.recordType() : "GENERIC", request.payload());
        return BaseResponse.ok("recorded");
    }

    private Integer resolveCurrentPage(String coursewareId) {
        return taskStateStore.get("lecture_state:" + coursewareId)
                .map(TaskStatePayload::getMetadata)
                .map(metadata -> metadata.get("currentPage"))
                .filter(Number.class::isInstance)
                .map(Number.class::cast)
                .map(Number::intValue)
                .orElse(1);
    }

    private ScriptSegmentView resolveScriptSegment(String coursewareId, Integer currentPage) {
        try {
            return coursewareService.getSegmentForPage(coursewareId, currentPage);
        } catch (Exception ignored) {
            return null;
        }
    }

    private void persistLectureRecord(String coursewareId, String recordType, Object payload) {
        LectureRecordRepository repository = lectureRecordRepositoryProvider.getIfAvailable();
        if (repository == null) {
            return;
        }
        LectureRecordEntity entity = new LectureRecordEntity();
        entity.setCoursewareId(coursewareId);
        entity.setPageNo(resolveCurrentPage(coursewareId));
        entity.setRecordType(recordType);
        entity.setPayloadJson(writeJson(payload));
        repository.save(entity);
    }

    private String writeJson(Object value) {
        try {
            return objectMapper.writeValueAsString(value);
        } catch (JsonProcessingException ex) {
            throw new IllegalStateException("Failed to serialize lecture payload", ex);
        }
    }

    private String buildPageImageApiUrl(String coursewareId, int pageIndex, String imagePath) {
        if (!StringUtils.hasText(imagePath)) {
            return null;
        }
        return "/api/v1/courseware/" + coursewareId + "/pages/" + pageIndex + "/image";
    }

    public record ProgressRequest(
            Integer currentPage,
            String status,
            Double playbackTime
    ) {
    }

    public record RecordRequest(
            String recordType,
            Object payload
    ) {
    }
}
