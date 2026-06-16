package com.interactive.edu.service.qa;

import com.interactive.edu.exception.ErrorCode;
import com.interactive.edu.exception.ServiceException;
import com.interactive.edu.service.courseware.CoursewareService;
import com.interactive.edu.service.lecture.LectureService;
import com.interactive.edu.service.python.PythonQaClient;
import com.interactive.edu.service.python.PythonQaIngestClient;
import com.interactive.edu.service.python.PythonQaRequest;
import com.interactive.edu.service.python.PythonQaResponse;
import com.interactive.edu.service.record.LectureRecordService;
import com.interactive.edu.vo.courseware.ScriptSegmentView;
import com.interactive.edu.vo.qa.QaAnswerView;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.web.servlet.mvc.method.annotation.StreamingResponseBody;

import java.io.ByteArrayOutputStream;
import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.NoSuchElementException;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.doAnswer;
import static org.mockito.Mockito.doThrow;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class QaServiceTest {

    @Mock
    private LectureService lectureService;

    @Mock
    private CoursewareService coursewareService;

    @Mock
    private PythonQaClient pythonQaClient;

    @Mock
    private PythonQaIngestClient pythonQaIngestClient;

    @Mock
    private LectureRecordService lectureRecordService;

    @InjectMocks
    private QaService qaService;

    @Test
    @DisplayName("uses Python RAG answer with current page context")
    void askText_pythonSuccess_returnsPythonAnswer() {
        LectureService.SessionSnapshot session = new LectureService.SessionSnapshot(
                "sess_qa_1",
                "cware_qa_1",
                "user_1",
                3,
                "PLAYING"
        );
        CoursewareService.QaIngestPage qaPage = new CoursewareService.QaIngestPage(
                4,
                "线性回归",
                "这一页介绍线性回归的定义和损失函数。",
                List.of("定义", "损失函数"),
                "D:/data/page4.png",
                "页面中包含公式和二维散点图。",
                List.of("公式", "散点图")
        );

        when(lectureService.getSessionSnapshot("sess_qa_1")).thenReturn(session);
        when(coursewareService.getQaIngestPages("cware_qa_1")).thenReturn(List.of(qaPage));
        when(coursewareService.getQaPageForPage("cware_qa_1", 4)).thenReturn(qaPage);
        when(pythonQaClient.askText(any(PythonQaRequest.class))).thenReturn(
                new PythonQaResponse(
                        "线性回归就是用一条线去拟合数据并最小化误差。",
                        List.of(new PythonQaResponse.EvidencePayload("page_4", "定义和损失函数", 4, "chunk_4")),
                        123
                )
        );

        QaAnswerView result = qaService.askText("sess_qa_1", "什么是线性回归", 4);

        assertThat(result.answer()).contains("线性回归");
        assertThat(result.latencyMs()).isEqualTo(123);
        assertThat(result.evidence()).hasSize(1);
        assertThat(result.evidence().get(0).pageIndex()).isEqualTo(4);

        ArgumentCaptor<PythonQaRequest> captor = ArgumentCaptor.forClass(PythonQaRequest.class);
        verify(pythonQaClient).askText(captor.capture());
        assertThat(captor.getValue().getPageIndex()).isEqualTo(4);
        assertThat(captor.getValue().getCurrentPageTitle()).isEqualTo("线性回归");
        assertThat(captor.getValue().getCurrentPageImagePath()).isEqualTo("D:/data/page4.png");
        assertThat(captor.getValue().getCurrentPageKnowledgePoints()).containsExactly("定义", "损失函数");
        verify(lectureService).updateBreakpoint("sess_qa_1", 4, null);
    }

    @Test
    @DisplayName("falls back to local template when Python QA fails")
    void askText_pythonError_fallsBackToLocalAnswer() {
        LectureService.SessionSnapshot session = new LectureService.SessionSnapshot(
                "sess_qa_2",
                "cware_qa_2",
                "user_2",
                2,
                "PLAYING"
        );
        ScriptSegmentView current = new ScriptSegmentView(
                "seg_2",
                "node_2",
                2,
                "梯度下降",
                "这一页介绍梯度下降如何沿负梯度方向更新参数。",
                List.of("学习率", "迭代更新"),
                null,
                "D:/data/page2.png",
                "/api/v1/courseware/cware_qa_2/page-images/2",
                "页面中包含迭代示意图。",
                List.of("示意图"),
                false
        );

        when(lectureService.getSessionSnapshot("sess_qa_2")).thenReturn(session);
        when(coursewareService.getQaIngestPages("cware_qa_2")).thenReturn(List.of());
        when(pythonQaClient.askText(any(PythonQaRequest.class)))
                .thenThrow(new ServiceException(ErrorCode.PYTHON_SERVICE_ERROR, "timeout"));
        when(coursewareService.getScriptSegments("cware_qa_2")).thenReturn(List.of(current));
        when(coursewareService.getSegmentForPage("cware_qa_2", 2)).thenReturn(current);

        QaAnswerView result = qaService.askText("sess_qa_2", "梯度下降怎么更新参数", 2);

        assertThat(result.answer()).contains("沿负梯度方向更新参数");
        assertThat(result.evidence()).hasSize(1);
        verify(lectureService, never()).updateBreakpoint("sess_qa_2", 2, null);
    }

    @Test
    @DisplayName("rebuilds vector index and retries when Python answer has no evidence")
    void askText_noEvidence_rebuildsIndexAndRetries() {
        LectureService.SessionSnapshot session = new LectureService.SessionSnapshot(
                "sess_qa_3",
                "cware_qa_3",
                "user_3",
                1,
                "PLAYING"
        );
        CoursewareService.QaIngestPage qaPage = new CoursewareService.QaIngestPage(
                1,
                "决策树",
                "这一页介绍决策树的划分准则。",
                List.of("信息增益"),
                "D:/data/page1.png",
                null,
                List.of()
        );

        when(lectureService.getSessionSnapshot("sess_qa_3")).thenReturn(session);
        when(coursewareService.getQaIngestPages("cware_qa_3")).thenReturn(List.of(qaPage));
        when(coursewareService.getQaPageForPage("cware_qa_3", 1)).thenReturn(qaPage);
        when(pythonQaClient.askText(any(PythonQaRequest.class)))
                .thenReturn(new PythonQaResponse("课件中没有直接覆盖该内容。", List.of(), 10))
                .thenReturn(new PythonQaResponse(
                        "这一页重点是用信息增益来选择划分属性。",
                        List.of(new PythonQaResponse.EvidencePayload("page_1", "信息增益", 1, "chunk_1")),
                        18
                ));

        QaAnswerView result = qaService.askText("sess_qa_3", "这一页重点是什么", 1);

        assertThat(result.answer()).contains("信息增益");
        verify(coursewareService, times(2)).getQaIngestPages("cware_qa_3");
        verify(pythonQaClient, times(2)).askText(any(PythonQaRequest.class));
    }

    @Test
    @DisplayName("streams Python SSE with requested page context")
    void streamText_pythonSuccess_proxiesSse() throws Exception {
        LectureService.SessionSnapshot session = new LectureService.SessionSnapshot(
                "sess_stream_1",
                "cware_stream_1",
                "user_stream_1",
                2,
                "PLAYING"
        );
        CoursewareService.QaIngestPage qaPage = new CoursewareService.QaIngestPage(
                5,
                "支持向量机",
                "这一页介绍间隔最大化。",
                List.of("间隔"),
                "D:/data/page5.png",
                null,
                List.of()
        );

        when(lectureService.getSessionSnapshot("sess_stream_1")).thenReturn(session);
        when(coursewareService.getQaIngestPages("cware_stream_1")).thenReturn(List.of(qaPage));
        when(coursewareService.getQaPageForPage("cware_stream_1", 5)).thenReturn(qaPage);
        doAnswer(invocation -> {
            PythonQaRequest request = invocation.getArgument(0);
            invocation.<java.io.OutputStream>getArgument(1).write((
                    "data: {\"type\":\"meta\",\"evidence\":[{\"source\":\"page_" + request.getPageIndex()
                            + "\",\"text\":\"ctx\",\"pageIndex\":" + request.getPageIndex() + "}]}\n\n"
                            + "data: {\"type\":\"delta\",\"content\":\"stream:" + request.getCoursewareId() + "\"}\n\n"
                            + "data: {\"type\":\"done\"}\n\n"
            ).getBytes(StandardCharsets.UTF_8));
            return null;
        }).when(pythonQaClient).streamText(any(PythonQaRequest.class), any(java.io.OutputStream.class));

        StreamingResponseBody body = qaService.streamText("sess_stream_1", "解释这一页", 5, 4);
        ByteArrayOutputStream output = new ByteArrayOutputStream();
        body.writeTo(output);

        String payload = output.toString(StandardCharsets.UTF_8);
        assertThat(payload).contains("\"type\":\"meta\"");
        assertThat(payload).contains("stream:cware_stream_1");
        assertThat(payload).contains("\"pageIndex\":5");
    }

    @Test
    @DisplayName("returns fallback SSE when Python QA stream is unavailable")
    void streamText_pythonUnavailable_returnsFallbackSse() throws Exception {
        LectureService.SessionSnapshot session = new LectureService.SessionSnapshot(
                "sess_stream_2",
                "cware_stream_2",
                "user_stream_2",
                2,
                "PLAYING"
        );

        when(lectureService.getSessionSnapshot("sess_stream_2")).thenReturn(session);
        when(coursewareService.getQaIngestPages("cware_stream_2")).thenReturn(List.of());
        doThrow(new ServiceException(ErrorCode.PYTHON_SERVICE_ERROR, "python down"))
                .when(pythonQaClient).streamText(any(PythonQaRequest.class), any(java.io.OutputStream.class));

        StreamingResponseBody body = qaService.streamText("sess_stream_2", "流式服务还在吗", 2, null);
        ByteArrayOutputStream output = new ByteArrayOutputStream();
        body.writeTo(output);

        String payload = output.toString(StandardCharsets.UTF_8);
        assertThat(payload).contains("当前问答服务暂时不可用，请稍后重试");
        assertThat(payload).contains("data: {\"type\":\"done\"}");
    }

    @Test
    @DisplayName("throws when session does not exist")
    void askText_sessionNotFound_throwsNoSuchElementException() {
        when(lectureService.getSessionSnapshot("missing")).thenThrow(new NoSuchElementException("session missing"));

        assertThatThrownBy(() -> qaService.askText("missing", "问题", 1))
                .isInstanceOf(NoSuchElementException.class);
        verifyNoInteractions(pythonQaClient, coursewareService, lectureRecordService, pythonQaIngestClient);
    }
}
