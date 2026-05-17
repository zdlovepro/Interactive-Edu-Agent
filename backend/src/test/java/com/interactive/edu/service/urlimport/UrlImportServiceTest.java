package com.interactive.edu.service.urlimport;

import com.interactive.edu.enums.UrlImportTaskStatus;
import com.interactive.edu.vo.courseware.UrlImportTaskView;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.core.task.TaskExecutor;

import java.util.ArrayDeque;
import java.util.Deque;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class UrlImportServiceTest {

    private final RecordingTaskExecutor taskExecutor = new RecordingTaskExecutor();
    private final UrlImportService service = new UrlImportService(taskExecutor);

    @Test
    @DisplayName("creates URL import task and waits for crawler worker")
    void createTask_validUrl_createsQueuedTaskThenWaitingCrawler() {
        UrlImportTaskView queued = service.createTask("https://example.com/resources/demo.pdf", "Web Courseware");

        assertThat(queued.taskId()).startsWith("crawl_task_");
        assertThat(queued.coursewareId()).startsWith("cware_");
        assertThat(queued.sourceUrl()).isEqualTo("https://example.com/resources/demo.pdf");
        assertThat(queued.name()).isEqualTo("Web Courseware");
        assertThat(queued.status()).isEqualTo(UrlImportTaskStatus.QUEUED.name());
        assertThat(queued.progress()).isEqualTo(5);
        assertThat(taskExecutor.size()).isEqualTo(1);

        taskExecutor.runNext();

        UrlImportTaskView waiting = service.getTask(queued.taskId());
        assertThat(waiting.status()).isEqualTo(UrlImportTaskStatus.WAITING_CRAWLER.name());
        assertThat(waiting.progress()).isEqualTo(15);
        assertThat(waiting.message()).contains("Crawler worker");
    }

    @Test
    @DisplayName("rejects non-http URL")
    void createTask_invalidScheme_rejectsRequest() {
        assertThatThrownBy(() -> service.createTask("ftp://example.com/demo.pdf", null))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("http or https");
    }

    private static final class RecordingTaskExecutor implements TaskExecutor {
        private final Deque<Runnable> tasks = new ArrayDeque<>();

        @Override
        public void execute(Runnable task) {
            tasks.addLast(task);
        }

        private int size() {
            return tasks.size();
        }

        private void runNext() {
            Runnable task = tasks.pollFirst();
            if (task != null) {
                task.run();
            }
        }
    }
}
