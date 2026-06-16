package com.interactive.edu.service.courseware;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.interactive.edu.dto.CoursewareUploadResult;
import com.interactive.edu.enums.CoursewareStatus;
import com.interactive.edu.enums.TaskStatus;
import com.interactive.edu.exception.ErrorCode;
import com.interactive.edu.exception.ServiceException;
import com.interactive.edu.service.python.PythonParseClient;
import com.interactive.edu.service.python.PythonParseRequest;
import com.interactive.edu.service.python.PythonScriptClient;
import com.interactive.edu.service.python.PythonScriptRequest;
import com.interactive.edu.storage.StorageService;
import com.interactive.edu.storage.StorageServiceFactory;
import com.interactive.edu.storage.StoredObject;
import com.interactive.edu.service.tts.TtsService;
import com.interactive.edu.vo.courseware.CoursewareDetailView;
import com.interactive.edu.vo.courseware.ScriptView;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.core.task.TaskExecutor;
import org.springframework.mock.web.MockMultipartFile;

import java.nio.charset.StandardCharsets;
import java.util.ArrayDeque;
import java.util.Arrays;
import java.util.concurrent.CompletableFuture;
import java.util.Deque;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class CoursewareServiceTest {

    @Mock
    private StorageServiceFactory storageServiceFactory;

    @Mock
    private StorageService storageService;

    @Mock
    private PythonParseClient pythonParseClient;

    @Mock
    private PythonScriptClient pythonScriptClient;

    @Mock
    private TtsService ttsService;

    private RecordingTaskExecutor taskExecutor;
    private CoursewareService service;

    @BeforeEach
    void setUp() {
        taskExecutor = new RecordingTaskExecutor();
        service = new CoursewareService(
                storageServiceFactory,
                pythonParseClient,
                pythonScriptClient,
                taskExecutor,
                ttsService,
                new ObjectMapper(),
                emptyProvider(),
                emptyProvider(),
                emptyProvider()
        );

        when(storageServiceFactory.get()).thenReturn(storageService);
        when(storageService.save(anyString(), any())).thenAnswer(invocation ->
                new StoredObject(invocation.getArgument(0) + "/demo.pdf", "local"));
        when(pythonParseClient.parse(any(PythonParseRequest.class))).thenReturn(new PythonParseClient.ParsePayload(
                2,
                List.of("Page 1 Title", "Page 2 Title"),
                List.of(
                        new PythonParseClient.ParseSegment(1, "Page 1 Title", "Page 1 body", List.of("Concept 1"), null, null, List.of()),
                        new PythonParseClient.ParseSegment(2, "Page 2 Title", "Page 2 body", List.of("Concept 2"), null, null, List.of())
                )
        ));
    }

    @Test
    @DisplayName("returns GENERATING_SCRIPT immediately and avoids duplicate submissions")
    void triggerScriptGeneration_whenAlreadyGenerating_doesNotSubmitDuplicateTask() {
        String coursewareId = uploadAndFinishParse();

        String firstStatus = service.triggerScriptGeneration(coursewareId);
        CoursewareDetailView generatingDetail = service.getDetail(coursewareId);

        assertThat(firstStatus).isEqualTo(CoursewareStatus.GENERATING_SCRIPT.name());
        assertThat(generatingDetail.status()).isEqualTo(CoursewareStatus.GENERATING_SCRIPT.name());
        assertThat(generatingDetail.currentTaskStatus()).isEqualTo(TaskStatus.RUNNING.name());
        assertThat(taskExecutor.size()).isEqualTo(1);
        verifyNoInteractions(pythonScriptClient);

        String secondStatus = service.triggerScriptGeneration(coursewareId);

        assertThat(secondStatus).isEqualTo(CoursewareStatus.GENERATING_SCRIPT.name());
        assertThat(taskExecutor.size()).isEqualTo(1);
        assertThat(service.getScript(coursewareId)).isNull();
    }

    @Test
    @DisplayName("prefers Python generated opening pages and closing when available")
    void triggerScriptGeneration_pythonAvailable_usesPythonResultAndReady() {
        mockAsyncTtsResults("http://audio.test/segment-1.mp3", "http://audio.test/segment-2.mp3");
        when(pythonScriptClient.generate(any(PythonScriptRequest.class))).thenReturn(
                new PythonScriptClient.ScriptPayload(
                        "ignored-courseware-id",
                        "Opening from Python",
                        List.of(
                                new PythonScriptClient.PageScriptPayload(1, "Page 1 script", "Transition to page 2"),
                                new PythonScriptClient.PageScriptPayload(2, "Page 2 script", "Transition to closing")
                        ),
                        "Closing from Python"
                )
        );

        String coursewareId = uploadAndFinishParse();

        assertThat(service.triggerScriptGeneration(coursewareId)).isEqualTo(CoursewareStatus.GENERATING_SCRIPT.name());
        taskExecutor.runNext();

        ScriptView script = service.getScript(coursewareId);
        CoursewareDetailView detail = service.getDetail(coursewareId);

        assertThat(detail.status()).isEqualTo(CoursewareStatus.READY.name());
        assertThat(detail.currentTaskStatus()).isEqualTo(TaskStatus.SUCCESS.name());
        assertThat(script).isNotNull();
        assertThat(script.status()).isEqualTo(CoursewareStatus.READY.name());
        assertThat(script.opening()).isEqualTo("Opening from Python");
        assertThat(script.closing()).isEqualTo("Closing from Python");
        assertThat(script.segments()).hasSize(2);
        assertThat(script.segments()).allMatch(segment -> segment.audioUrl() != null);
        assertThat(script.segments().get(0).content()).contains("Opening from Python", "Page 1 script");
        assertThat(script.segments().get(0).content()).doesNotContain("Transition to page 2");
        assertThat(script.segments().get(1).content()).contains("Page 2 script");
        assertThat(script.segments().get(1).content()).doesNotContain("Transition to closing", "Closing from Python");

        ArgumentCaptor<PythonScriptRequest> captor = ArgumentCaptor.forClass(PythonScriptRequest.class);
        verify(pythonScriptClient).generate(captor.capture());
        assertThat(captor.getValue().getCoursewareId()).isEqualTo(coursewareId);
        assertThat(captor.getValue().getCoursewareName()).isEqualTo("Sample Courseware");
        assertThat(captor.getValue().getPages()).hasSize(2);

        assertThat(service.triggerScriptGeneration(coursewareId)).isEqualTo(CoursewareStatus.READY.name());
        verify(pythonScriptClient, times(1)).generate(any(PythonScriptRequest.class));
    }

    @Test
    @DisplayName("falls back to local script draft when Python is unavailable")
    void triggerScriptGeneration_pythonUnavailable_fallsBackToLocalDraft() {
        mockAsyncTtsResults("http://audio.test/segment-1.mp3", "http://audio.test/segment-2.mp3");
        when(pythonScriptClient.generate(any(PythonScriptRequest.class)))
                .thenThrow(new ServiceException(ErrorCode.PYTHON_SERVICE_ERROR, "python down"));

        String coursewareId = uploadAndFinishParse();

        assertThat(service.triggerScriptGeneration(coursewareId)).isEqualTo(CoursewareStatus.GENERATING_SCRIPT.name());
        taskExecutor.runNext();

        ScriptView script = service.getScript(coursewareId);
        CoursewareDetailView detail = service.getDetail(coursewareId);

        assertThat(detail.status()).isEqualTo(CoursewareStatus.READY.name());
        assertThat(detail.currentTaskStatus()).isEqualTo(TaskStatus.SUCCESS.name());
        assertThat(script).isNotNull();
        assertThat(script.segments()).allMatch(segment -> segment.audioUrl() != null);
        assertThat(script.opening()).isNotBlank();
        assertThat(script.segments().get(0).content()).contains("Page 1 Title", "Page 1 body");
        assertThat(script.closing()).isNotBlank();
    }

    @Test
    @DisplayName("marks task as PARTIAL_SUCCESS when only some pages have audio")
    void triggerScriptGeneration_partialTtsFailure_marksReadyWithPartialSuccess() {
        mockAsyncTtsResults("http://audio.test/segment-1.mp3", null);
        when(pythonScriptClient.generate(any(PythonScriptRequest.class)))
                .thenThrow(new ServiceException(ErrorCode.PYTHON_SERVICE_ERROR, "python down"));

        String coursewareId = uploadAndFinishParse();

        assertThat(service.triggerScriptGeneration(coursewareId)).isEqualTo(CoursewareStatus.GENERATING_SCRIPT.name());
        taskExecutor.runNext();

        ScriptView script = service.getScript(coursewareId);
        CoursewareDetailView detail = service.getDetail(coursewareId);

        assertThat(detail.status()).isEqualTo(CoursewareStatus.READY.name());
        assertThat(detail.currentTaskStatus()).isEqualTo(TaskStatus.PARTIAL_SUCCESS.name());
        assertThat(script).isNotNull();
        assertThat(script.segments()).hasSize(2);
        assertThat(script.segments().get(0).audioUrl()).isEqualTo("http://audio.test/segment-1.mp3");
        assertThat(script.segments().get(1).audioUrl()).isNull();
    }

    @Test
    @DisplayName("keeps courseware READY when all TTS calls fail unexpectedly")
    void triggerScriptGeneration_allTtsFailure_stillReadyWithPartialSuccess() {
        mockFailedAsyncTtsResults(
                new IllegalStateException("tts down"),
                new IllegalStateException("tts down")
        );
        when(pythonScriptClient.generate(any(PythonScriptRequest.class)))
                .thenThrow(new ServiceException(ErrorCode.PYTHON_SERVICE_ERROR, "python down"));

        String coursewareId = uploadAndFinishParse();

        assertThat(service.triggerScriptGeneration(coursewareId)).isEqualTo(CoursewareStatus.GENERATING_SCRIPT.name());
        taskExecutor.runNext();

        ScriptView script = service.getScript(coursewareId);
        CoursewareDetailView detail = service.getDetail(coursewareId);

        assertThat(detail.status()).isEqualTo(CoursewareStatus.READY.name());
        assertThat(detail.currentTaskStatus()).isEqualTo(TaskStatus.PARTIAL_SUCCESS.name());
        assertThat(script).isNotNull();
        assertThat(script.segments()).allMatch(segment -> segment.audioUrl() == null);
    }

    @Test
    @DisplayName("keeps courseware READY when TTS degrades to null for every page")
    void triggerScriptGeneration_ttsReturnsNullForAllSegments_keepsReadyAndNullAudio() {
        mockAsyncTtsResults(null, null);
        when(pythonScriptClient.generate(any(PythonScriptRequest.class)))
                .thenThrow(new ServiceException(ErrorCode.PYTHON_SERVICE_ERROR, "python down"));

        String coursewareId = uploadAndFinishParse();

        assertThat(service.triggerScriptGeneration(coursewareId)).isEqualTo(CoursewareStatus.GENERATING_SCRIPT.name());
        taskExecutor.runNext();

        ScriptView script = service.getScript(coursewareId);
        CoursewareDetailView detail = service.getDetail(coursewareId);

        assertThat(detail.status()).isEqualTo(CoursewareStatus.READY.name());
        assertThat(detail.currentTaskStatus()).isEqualTo(TaskStatus.PARTIAL_SUCCESS.name());
        assertThat(script).isNotNull();
        assertThat(script.segments()).allMatch(segment -> segment.audioUrl() == null);
    }

    private String uploadAndFinishParse() {
        MockMultipartFile file = new MockMultipartFile(
                "file",
                "demo.pdf",
                "application/pdf",
                "demo".getBytes(StandardCharsets.UTF_8)
        );

        CoursewareUploadResult uploadResult = service.upload(file, "Sample Courseware");
        assertThat(taskExecutor.size()).isEqualTo(1);
        taskExecutor.runNext();

        CoursewareDetailView detail = service.getDetail(uploadResult.getCoursewareId());
        assertThat(detail.status()).isEqualTo(CoursewareStatus.PARSED.name());
        assertThat(detail.currentTaskStatus()).isEqualTo(TaskStatus.SUCCESS.name());
        return uploadResult.getCoursewareId();
    }

    private static <T> ObjectProvider<T> emptyProvider() {
        return new ObjectProvider<>() {
            @Override
            public T getObject(Object... args) {
                return null;
            }

            @Override
            public T getIfAvailable() {
                return null;
            }

            @Override
            public T getIfUnique() {
                return null;
            }

            @Override
            public T getObject() {
                return null;
            }
        };
    }

    private void mockAsyncTtsResults(String... audioUrls) {
        CompletableFuture<String>[] futures = Arrays.stream(audioUrls)
                .map(CompletableFuture::completedFuture)
                .toArray(CompletableFuture[]::new);
        when(ttsService.synthesizeToAudioUrlAsync(anyString()))
                .thenReturn(futures[0], Arrays.copyOfRange(futures, 1, futures.length));
    }

    private void mockFailedAsyncTtsResults(RuntimeException... errors) {
        CompletableFuture<String>[] futures = Arrays.stream(errors)
                .map(error -> {
                    CompletableFuture<String> future = new CompletableFuture<>();
                    future.completeExceptionally(error);
                    return future;
                })
                .toArray(CompletableFuture[]::new);
        when(ttsService.synthesizeToAudioUrlAsync(anyString()))
                .thenReturn(futures[0], Arrays.copyOfRange(futures, 1, futures.length));
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
