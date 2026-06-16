package com.interactive.edu.service.lecture;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.interactive.edu.entity.LectureSession;
import com.interactive.edu.enums.LectureSessionStatus;
import com.interactive.edu.repository.LectureSessionRepository;
import com.interactive.edu.service.courseware.CoursewareService;
import com.interactive.edu.support.RedisJsonStore;
import com.interactive.edu.vo.courseware.CurrentNodeView;
import com.interactive.edu.vo.lecture.LectureSessionView;
import com.interactive.edu.vo.lecture.SessionStatusView;
import lombok.Getter;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;

import java.time.Duration;
import java.time.Instant;
import java.time.LocalDateTime;
import java.time.ZoneId;
import java.util.NoSuchElementException;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ConcurrentMap;

@Service
@RequiredArgsConstructor
@Slf4j
public class LectureService {

    private static final String REDIS_KEY_PREFIX = "lecture:session:";
    private static final Duration REDIS_TTL = Duration.ofHours(24);

    private final CoursewareService coursewareService;
    private final ObjectProvider<LectureSessionRepository> lectureSessionRepositoryProvider;
    private final ObjectMapper objectMapper;
    private final RedisJsonStore redisJsonStore;

    private final ConcurrentMap<String, SessionState> sessionStore = new ConcurrentHashMap<>();

    public LectureSessionView startLecture(String coursewareId, String userId) {
        if (!StringUtils.hasText(coursewareId)) {
            throw new IllegalArgumentException("coursewareId must not be blank");
        }

        coursewareService.requireScript(coursewareId);
        String sessionId = "sess_" + UUID.randomUUID().toString().replace("-", "");
        String resolvedUserId = StringUtils.hasText(userId) ? userId.trim() : "demo_user";
        CurrentNodeView currentNode = coursewareService.getCurrentNode(coursewareId, 1);

        SessionState state = new SessionState(sessionId, coursewareId, resolvedUserId, currentNode.nodeId());
        state.markPlaying();
        sessionStore.put(sessionId, state);
        persistSession(state);
        log.info("Lecture started. sessionId={}, coursewareId={}, userId={}", sessionId, coursewareId, resolvedUserId);

        return new LectureSessionView(
                sessionId,
                state.getStatus(),
                currentNode,
                state.getCurrentPageIndex(),
                state.getBreakpointTime()
        );
    }

    public SessionStatusView pause(String sessionId) {
        LectureRealtimeState state = interrupt(sessionId, null, null);
        return new SessionStatusView(state.sessionId(), state.status());
    }

    public LectureSessionView resume(String sessionId) {
        ResumeState resumeState = resumeFromBreakpoint(sessionId);
        return new LectureSessionView(
                resumeState.sessionId(),
                LectureSessionStatus.PLAYING.name(),
                resumeState.currentNode(),
                resumeState.currentPageIndex(),
                resumeState.breakpointTime()
        );
    }

    public SessionSnapshot getSessionSnapshot(String sessionId) {
        validateSessionId(sessionId);

        SessionState session = requireSession(sessionId);
        return new SessionSnapshot(
                session.getSessionId(),
                session.getCoursewareId(),
                session.getUserId(),
                session.getCurrentPageIndex(),
                session.getStatus()
        );
    }

    public LectureRealtimeState interrupt(String sessionId, Integer pageIndex, Double currentTime) {
        validateSessionId(sessionId);

        LectureRealtimeState state = updateBreakpoint(sessionId, pageIndex, currentTime);
        SessionState session = requireSession(sessionId);
        session.markInterrupted();
        persistSession(session);
        log.info(
                "Lecture interrupted. sessionId={}, coursewareId={}, pageIndex={}, currentTime={}",
                sessionId,
                session.getCoursewareId(),
                state.currentPageIndex(),
                state.breakpointTime()
        );
        return toRealtimeState(session);
    }

    public LectureRealtimeState updateBreakpoint(String sessionId, Integer pageIndex, Double currentTime) {
        validateSessionId(sessionId);

        SessionState session = requireSession(sessionId);
        int resolvedPageIndex = resolvePageIndex(pageIndex, session.getCurrentPageIndex());
        double resolvedCurrentTime = resolveCurrentTime(currentTime, session.getBreakpointTime());
        CurrentNodeView currentNode = coursewareService.getCurrentNode(session.getCoursewareId(), resolvedPageIndex);
        session.updateBreakpoint(resolvedPageIndex, resolvedCurrentTime, currentNode.nodeId());
        persistSession(session);
        log.info(
                "Lecture breakpoint updated. sessionId={}, coursewareId={}, pageIndex={}, currentTime={}",
                sessionId,
                session.getCoursewareId(),
                resolvedPageIndex,
                resolvedCurrentTime
        );
        return toRealtimeState(session);
    }

    public ResumeState resumeFromBreakpoint(String sessionId) {
        validateSessionId(sessionId);

        SessionState session = requireSession(sessionId);
        session.markResuming();
        CurrentNodeView currentNode = coursewareService.getCurrentNode(
                session.getCoursewareId(),
                session.getCurrentPageIndex()
        );
        double breakpointTime = session.getBreakpointTime();
        int currentPageIndex = session.getCurrentPageIndex();
        session.markPlaying();
        session.setCurrentNodeId(currentNode.nodeId());
        persistSession(session);
        log.info(
                "Lecture resumed from breakpoint. sessionId={}, coursewareId={}, pageIndex={}, breakpointTime={}",
                sessionId,
                session.getCoursewareId(),
                currentPageIndex,
                breakpointTime
        );
        return new ResumeState(session.getSessionId(), currentPageIndex, breakpointTime, currentNode);
    }

    public LectureRealtimeState updateHeartbeat(String sessionId) {
        validateSessionId(sessionId);

        SessionState session = requireSession(sessionId);
        session.updateHeartbeat();
        persistSession(session);
        log.debug("Lecture heartbeat updated. sessionId={}, coursewareId={}", sessionId, session.getCoursewareId());
        return toRealtimeState(session);
    }

    public LectureRealtimeState getRealtimeState(String sessionId) {
        validateSessionId(sessionId);
        return toRealtimeState(requireSession(sessionId));
    }

    private void validateSessionId(String sessionId) {
        if (!StringUtils.hasText(sessionId)) {
            throw new IllegalArgumentException("sessionId must not be blank");
        }
    }

    private int resolvePageIndex(Integer requestedPageIndex, int currentPageIndex) {
        if (requestedPageIndex == null) {
            return currentPageIndex;
        }
        if (requestedPageIndex <= 0) {
            throw new IllegalArgumentException("pageIndex must be positive");
        }
        return requestedPageIndex;
    }

    private double resolveCurrentTime(Double requestedCurrentTime, double currentTime) {
        if (requestedCurrentTime == null) {
            return currentTime;
        }
        if (requestedCurrentTime < 0) {
            throw new IllegalArgumentException("currentTime must be greater than or equal to 0");
        }
        return requestedCurrentTime;
    }

    private LectureRealtimeState toRealtimeState(SessionState session) {
        return new LectureRealtimeState(
                session.getSessionId(),
                session.getCoursewareId(),
                session.getStatus(),
                session.getCurrentPageIndex(),
                session.getBreakpointTime(),
                session.getLastSeenAt(),
                coursewareService.getCurrentNode(session.getCoursewareId(), session.getCurrentPageIndex())
        );
    }

    private SessionState requireSession(String sessionId) {
        SessionState session = sessionStore.get(sessionId);
        if (session != null) {
            return session;
        }

        SessionState restored = restoreSession(sessionId);
        if (restored != null) {
            sessionStore.put(sessionId, restored);
            return restored;
        }
        throw new NoSuchElementException("lecture session not found");
    }

    private SessionState restoreSession(String sessionId) {
        if (!isPersistentMode()) {
            return null;
        }

        String cachedJson = redisJsonStore.get(redisKey(sessionId));
        if (StringUtils.hasText(cachedJson)) {
            try {
                SessionCachePayload payload = objectMapper.readValue(cachedJson, SessionCachePayload.class);
                return payload.toState();
            } catch (Exception ex) {
                log.warn("Failed to restore lecture session from Redis. sessionId={}, reason={}", sessionId, ex.getMessage());
            }
        }

        return lectureSessionRepository().findById(sessionId)
                .map(SessionState::fromEntity)
                .orElse(null);
    }

    private void persistSession(SessionState state) {
        if (!isPersistentMode()) {
            return;
        }

        LectureSession entity = lectureSessionRepository().findById(state.getSessionId())
                .orElseGet(LectureSession::new);
        entity.setId(state.getSessionId());
        entity.setCoursewareId(state.getCoursewareId());
        entity.setUserId(state.getUserId());
        entity.setCurrentPageIndex(state.getCurrentPageIndex());
        entity.setCurrentNodeId(state.getCurrentNodeId());
        entity.setStatus(state.getStatus());
        entity.setBreakpointTime(state.getBreakpointTime());
        entity.setLastSeenAt(toLocalDateTime(state.getLastSeenAt()));
        lectureSessionRepository().save(entity);

        try {
            redisJsonStore.put(
                    redisKey(state.getSessionId()),
                    objectMapper.writeValueAsString(SessionCachePayload.fromState(state)),
                    REDIS_TTL
            );
        } catch (Exception ex) {
            log.warn("Failed to cache lecture session into Redis. sessionId={}, reason={}", state.getSessionId(), ex.getMessage());
        }
    }

    private boolean isPersistentMode() {
        return lectureSessionRepositoryProvider.getIfAvailable() != null;
    }

    private LectureSessionRepository lectureSessionRepository() {
        LectureSessionRepository repository = lectureSessionRepositoryProvider.getIfAvailable();
        if (repository == null) {
            throw new IllegalStateException("LectureSessionRepository is unavailable in the current profile");
        }
        return repository;
    }

    private String redisKey(String sessionId) {
        return REDIS_KEY_PREFIX + sessionId;
    }

    private static LocalDateTime toLocalDateTime(Instant instant) {
        return instant == null ? null : LocalDateTime.ofInstant(instant, ZoneId.systemDefault());
    }

    private static Instant toInstant(LocalDateTime time) {
        return time == null ? Instant.now() : time.atZone(ZoneId.systemDefault()).toInstant();
    }

    public record SessionSnapshot(
            String sessionId,
            String coursewareId,
            String userId,
            int currentPageIndex,
            String status
    ) {
    }

    public record LectureRealtimeState(
            String sessionId,
            String coursewareId,
            String status,
            int currentPageIndex,
            double breakpointTime,
            Instant lastSeenAt,
            CurrentNodeView currentNode
    ) {
    }

    public record ResumeState(
            String sessionId,
            int currentPageIndex,
            double breakpointTime,
            CurrentNodeView currentNode
    ) {
    }

    private record SessionCachePayload(
            String sessionId,
            String coursewareId,
            String userId,
            String currentNodeId,
            int currentPageIndex,
            double breakpointTime,
            String status,
            Instant createdAt,
            Instant updatedAt,
            Instant lastSeenAt
    ) {
        private static SessionCachePayload fromState(SessionState state) {
            return new SessionCachePayload(
                    state.getSessionId(),
                    state.getCoursewareId(),
                    state.getUserId(),
                    state.getCurrentNodeId(),
                    state.getCurrentPageIndex(),
                    state.getBreakpointTime(),
                    state.getStatus(),
                    state.getCreatedAt(),
                    state.getUpdatedAt(),
                    state.getLastSeenAt()
            );
        }

        private SessionState toState() {
            return new SessionState(
                    sessionId,
                    coursewareId,
                    userId,
                    currentNodeId,
                    currentPageIndex,
                    breakpointTime,
                    status,
                    createdAt,
                    updatedAt,
                    lastSeenAt
            );
        }
    }

    @Getter
    private static final class SessionState {
        private final String sessionId;
        private final String coursewareId;
        private final String userId;
        private final Instant createdAt;
        private volatile Instant updatedAt;
        private volatile Instant lastSeenAt;
        private volatile String currentNodeId;
        private volatile int currentPageIndex;
        private volatile double breakpointTime;
        private volatile String status;

        private SessionState(String sessionId, String coursewareId, String userId, String currentNodeId) {
            this(
                    sessionId,
                    coursewareId,
                    userId,
                    currentNodeId,
                    1,
                    0D,
                    LectureSessionStatus.IDLE.name(),
                    Instant.now(),
                    Instant.now(),
                    Instant.now()
            );
        }

        private SessionState(
                String sessionId,
                String coursewareId,
                String userId,
                String currentNodeId,
                int currentPageIndex,
                double breakpointTime,
                String status,
                Instant createdAt,
                Instant updatedAt,
                Instant lastSeenAt
        ) {
            this.sessionId = sessionId;
            this.coursewareId = coursewareId;
            this.userId = userId;
            this.currentNodeId = currentNodeId;
            this.currentPageIndex = currentPageIndex;
            this.breakpointTime = breakpointTime;
            this.status = status;
            this.createdAt = createdAt;
            this.updatedAt = updatedAt;
            this.lastSeenAt = lastSeenAt;
        }

        private static SessionState fromEntity(LectureSession entity) {
            return new SessionState(
                    entity.getId(),
                    entity.getCoursewareId(),
                    entity.getUserId(),
                    entity.getCurrentNodeId(),
                    entity.getCurrentPageIndex() == null ? 1 : entity.getCurrentPageIndex(),
                    entity.getBreakpointTime() == null ? 0D : entity.getBreakpointTime(),
                    StringUtils.hasText(entity.getStatus()) ? entity.getStatus() : LectureSessionStatus.IDLE.name(),
                    toInstant(entity.getCreateTime()),
                    toInstant(entity.getUpdateTime()),
                    toInstant(entity.getLastSeenAt())
            );
        }

        private synchronized void updateBreakpoint(int pageIndex, double currentTime, String currentNodeId) {
            this.currentPageIndex = pageIndex;
            this.breakpointTime = currentTime;
            this.currentNodeId = currentNodeId;
            touch();
        }

        private synchronized void markInterrupted() {
            this.status = LectureSessionStatus.INTERRUPTED.name();
            touch();
        }

        private synchronized void markResuming() {
            this.status = LectureSessionStatus.RESUMING.name();
            touch();
        }

        private synchronized void markPlaying() {
            this.status = LectureSessionStatus.PLAYING.name();
            touch();
        }

        private synchronized void updateHeartbeat() {
            touch();
        }

        private synchronized void setCurrentNodeId(String currentNodeId) {
            this.currentNodeId = currentNodeId;
            touch();
        }

        private synchronized void touch() {
            Instant now = Instant.now();
            this.updatedAt = now;
            this.lastSeenAt = now;
        }
    }
}
