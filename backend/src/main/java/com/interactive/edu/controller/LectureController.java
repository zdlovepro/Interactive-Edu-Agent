package com.interactive.edu.controller;

import com.interactive.edu.dto.BaseResponse;
import com.interactive.edu.exception.BusinessException;
import com.interactive.edu.exception.ErrorCode;
import com.interactive.edu.service.courseware.CoursewareService;
import com.interactive.edu.service.lecture.LectureService;
import com.interactive.edu.service.record.LectureRecordService;
import com.interactive.edu.service.user.AuthService;
import com.interactive.edu.vo.lecture.LectureSessionView;
import com.interactive.edu.vo.lecture.SessionStatusView;
import com.interactive.edu.vo.record.InterruptRecordView;
import com.interactive.edu.vo.record.QaRecordView;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@RestController
@RequestMapping("/api/v1/lecture")
@RequiredArgsConstructor
@Validated
@Slf4j
public class LectureController {

    private final LectureService lectureService;
    private final LectureRecordService lectureRecordService;
    private final CoursewareService coursewareService;
    private final AuthService authService;

    @PostMapping("/start")
    public BaseResponse<LectureSessionView> start(
            @Valid @RequestBody StartLectureRequest request,
            @RequestHeader(value = "Authorization", required = false) String authorizationHeader,
            @RequestHeader(value = "X-Course-Code", required = false) String courseCode
    ) {
        AuthService.AuthenticatedUser user = authService.requireUser(authorizationHeader);
        coursewareService.assertReadable(request.coursewareId(), user, courseCode);
        LectureSessionView sessionView = lectureService.startLecture(request.coursewareId(), user.id());
        registerSessionSafely(sessionView.sessionId());
        return BaseResponse.ok(sessionView);
    }

    @PostMapping("/{sessionId}/pause")
    public BaseResponse<SessionStatusView> pause(
            @PathVariable("sessionId") @NotBlank String sessionId,
            @RequestHeader(value = "Authorization", required = false) String authorizationHeader
    ) {
        requireSessionOwner(authorizationHeader, sessionId);
        return BaseResponse.ok(lectureService.pause(sessionId));
    }

    @PostMapping("/pause")
    public BaseResponse<SessionStatusView> pauseByBody(
            @Valid @RequestBody ResumeLectureRequest request,
            @RequestHeader(value = "Authorization", required = false) String authorizationHeader
    ) {
        requireSessionOwner(authorizationHeader, request.sessionId());
        return BaseResponse.ok(lectureService.pause(request.sessionId()));
    }

    @PostMapping("/resume")
    public BaseResponse<LectureSessionView> resume(
            @Valid @RequestBody ResumeLectureRequest request,
            @RequestHeader(value = "Authorization", required = false) String authorizationHeader
    ) {
        requireSessionOwner(authorizationHeader, request.sessionId());
        LectureSessionView sessionView = lectureService.resume(request.sessionId());
        markLatestInterruptResumedSafely(request.sessionId());
        return BaseResponse.ok(sessionView);
    }

    private void registerSessionSafely(String sessionId) {
        try {
            lectureRecordService.registerSession(sessionId);
        } catch (Exception ex) {
            log.warn("Failed to register lecture record session. sessionId={}, reason={}", sessionId, ex.getMessage());
        }
    }

    private void markLatestInterruptResumedSafely(String sessionId) {
        try {
            lectureRecordService.tryMarkLatestInterruptResumed(sessionId);
        } catch (Exception ex) {
            log.warn("Failed to mark interrupt resumed. sessionId={}, reason={}", sessionId, ex.getMessage());
        }
    }

    @GetMapping("/{sessionId}/records")
    public BaseResponse<LectureRecordsResponse> getRecords(
            @PathVariable("sessionId") @NotBlank String sessionId,
            @RequestHeader(value = "Authorization", required = false) String authorizationHeader
    ) {
        requireSessionOwner(authorizationHeader, sessionId);
        LectureRecordService.SessionRecordsSnapshot snapshot = lectureRecordService.getSessionRecords(sessionId);
        return BaseResponse.ok(new LectureRecordsResponse(snapshot.interrupts(), snapshot.qaRecords()));
    }

    private AuthService.AuthenticatedUser requireSessionOwner(String authorizationHeader, String sessionId) {
        AuthService.AuthenticatedUser user = authService.requireUser(authorizationHeader);
        LectureService.SessionSnapshot session = lectureService.getSessionSnapshot(sessionId);
        if (!session.userId().equals(user.id())) {
            throw new BusinessException(ErrorCode.FORBIDDEN, "你无权操作该课堂会话");
        }
        return user;
    }

    public record StartLectureRequest(
            @NotBlank(message = "coursewareId 不能为空") String coursewareId,
            String userId
    ) {
    }

    public record ResumeLectureRequest(
            @NotBlank(message = "sessionId 不能为空") String sessionId
    ) {
    }

    public record LectureRecordsResponse(
            List<InterruptRecordView> interrupts,
            List<QaRecordView> qaRecords
    ) {
    }
}
