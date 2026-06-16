package com.interactive.edu.service.urlimport;

import com.interactive.edu.enums.UrlImportTaskStatus;
import com.interactive.edu.exception.BusinessException;
import com.interactive.edu.exception.ErrorCode;
import com.interactive.edu.vo.courseware.UrlImportTaskView;
import lombok.extern.slf4j.Slf4j;
import org.springframework.core.task.TaskExecutor;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;

import java.net.URI;
import java.net.URISyntaxException;
import java.time.Instant;
import java.util.NoSuchElementException;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ConcurrentMap;

@Service
@Slf4j
public class UrlImportService {

    private final TaskExecutor taskExecutor;
    private final ConcurrentMap<String, UrlImportTask> tasks = new ConcurrentHashMap<>();

    public UrlImportService(TaskExecutor taskExecutor) {
        this.taskExecutor = taskExecutor;
    }

    public UrlImportTaskView createTask(String url, String requestedName, String userId) {
        URI sourceUri = parseSourceUrl(url);
        String normalizedUserId = normalizeUserId(userId);
        String taskId = "crawl_task_" + UUID.randomUUID().toString().replace("-", "");
        String coursewareId = "cware_" + UUID.randomUUID().toString().replace("-", "");
        String displayName = resolveDisplayName(requestedName, sourceUri);

        UrlImportTask task = UrlImportTask.queued(taskId, coursewareId, normalizedUserId, sourceUri.toString(), displayName);
        tasks.put(taskId, task);

        log.info(
                "URL import task accepted. taskId={}, coursewareId={}, userId={}, host={}",
                taskId,
                coursewareId,
                normalizedUserId,
                sourceUri.getHost()
        );
        taskExecutor.execute(() -> dispatchToCrawlerQueue(taskId));
        return task.toView();
    }

    public UrlImportTaskView getTask(String taskId, String userId) {
        if (!StringUtils.hasText(taskId)) {
            throw new IllegalArgumentException("taskId must not be blank");
        }

        UrlImportTask task = tasks.get(taskId);
        if (task == null) {
            throw new NoSuchElementException("URL import task not found");
        }
        if (!task.userId.equals(normalizeUserId(userId))) {
            throw new BusinessException(ErrorCode.FORBIDDEN, "You are not allowed to access this URL import task");
        }
        return task.toView();
    }

    private void dispatchToCrawlerQueue(String taskId) {
        UrlImportTask task = tasks.get(taskId);
        if (task == null) {
            return;
        }

        task.markWaitingCrawler();
        log.info("URL import task ready for crawler worker. taskId={}, coursewareId={}", task.taskId, task.coursewareId);
    }

    private URI parseSourceUrl(String url) {
        if (!StringUtils.hasText(url)) {
            throw new IllegalArgumentException("url must not be blank");
        }
        try {
            URI uri = new URI(url.trim());
            String scheme = uri.getScheme();
            if (scheme == null || (!"http".equalsIgnoreCase(scheme) && !"https".equalsIgnoreCase(scheme))) {
                throw new IllegalArgumentException("url must use http or https");
            }
            if (!StringUtils.hasText(uri.getHost())) {
                throw new IllegalArgumentException("url host must not be blank");
            }
            return uri;
        } catch (URISyntaxException ex) {
            throw new IllegalArgumentException("url format is invalid");
        }
    }

    private String resolveDisplayName(String requestedName, URI sourceUri) {
        if (StringUtils.hasText(requestedName)) {
            return requestedName.trim();
        }

        String path = sourceUri.getPath();
        if (StringUtils.hasText(path)) {
            int slashIndex = path.lastIndexOf('/');
            String lastSegment = slashIndex >= 0 ? path.substring(slashIndex + 1) : path;
            if (StringUtils.hasText(lastSegment)) {
                return lastSegment;
            }
        }
        return "URL resource - " + sourceUri.getHost();
    }

    private String normalizeUserId(String userId) {
        if (!StringUtils.hasText(userId)) {
            throw new IllegalArgumentException("userId must not be blank");
        }
        return userId.trim();
    }

    private static final class UrlImportTask {
        private final String taskId;
        private final String coursewareId;
        private final String userId;
        private final String sourceUrl;
        private final String name;
        private final Instant createdAt;
        private volatile Instant updatedAt;
        private volatile UrlImportTaskStatus status;
        private volatile String stage;
        private volatile int progress;
        private volatile String message;

        private UrlImportTask(
                String taskId,
                String coursewareId,
                String userId,
                String sourceUrl,
                String name,
                Instant createdAt,
                UrlImportTaskStatus status,
                String stage,
                int progress,
                String message
        ) {
            this.taskId = taskId;
            this.coursewareId = coursewareId;
            this.userId = userId;
            this.sourceUrl = sourceUrl;
            this.name = name;
            this.createdAt = createdAt;
            this.updatedAt = createdAt;
            this.status = status;
            this.stage = stage;
            this.progress = progress;
            this.message = message;
        }

        private static UrlImportTask queued(
                String taskId,
                String coursewareId,
                String userId,
                String sourceUrl,
                String name
        ) {
            return new UrlImportTask(
                    taskId,
                    coursewareId,
                    userId,
                    sourceUrl,
                    name,
                    Instant.now(),
                    UrlImportTaskStatus.QUEUED,
                    "QUEUED",
                    5,
                    "URL import task has been queued"
            );
        }

        private void markWaitingCrawler() {
            this.status = UrlImportTaskStatus.WAITING_CRAWLER;
            this.stage = "QUEUED";
            this.progress = 15;
            this.message = "Crawler worker is not connected yet; task is ready for dispatch";
            this.updatedAt = Instant.now();
        }

        private UrlImportTaskView toView() {
            return new UrlImportTaskView(
                    taskId,
                    coursewareId,
                    sourceUrl,
                    name,
                    status.name(),
                    stage,
                    progress,
                    message,
                    createdAt.toString(),
                    updatedAt.toString()
            );
        }
    }
}
