package com.interactive.edu.service.qa;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.interactive.edu.entity.VisualQaRecordEntity;
import com.interactive.edu.repository.VisualQaRecordRepository;
import com.interactive.edu.service.courseware.CoursewareService;
import com.interactive.edu.vo.qa.VisualQaAnswerView;
import com.interactive.edu.vo.qa.VisualQaEvidenceView;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;

import java.util.ArrayList;
import java.util.List;

@Service
@RequiredArgsConstructor
public class VisualQaService {

    private final CoursewareService coursewareService;
    private final ObjectMapper objectMapper;
    private final ObjectProvider<VisualQaRecordRepository> visualQaRecordRepositoryProvider;

    public VisualQaAnswerView askVisual(String coursewareId, Integer pageNo, String question) {
        if (!StringUtils.hasText(coursewareId) || pageNo == null || pageNo <= 0 || !StringUtils.hasText(question)) {
            throw new IllegalArgumentException("coursewareId, pageNo and question are required");
        }

        CoursewareService.PageSnapshot pageSnapshot = coursewareService.getPageSnapshot(coursewareId, pageNo);
        boolean hasVisualSignal = pageSnapshot != null && (StringUtils.hasText(pageSnapshot.imageUrl()) || !pageSnapshot.knowledgePoints().isEmpty());
        String answer;
        String fallbackReason = null;
        List<VisualQaEvidenceView> evidence = new ArrayList<>();

        if (pageSnapshot != null && StringUtils.hasText(pageSnapshot.text())) {
            answer = "结合当前页内容，这一页主要想表达的是：" + summarize(pageSnapshot.text());
            evidence.add(new VisualQaEvidenceView(pageNo, "pageText", summarize(pageSnapshot.text())));
            if (StringUtils.hasText(pageSnapshot.imageUrl())) {
                evidence.add(new VisualQaEvidenceView(pageNo, "pageImage", "当前页图片已就绪，可用于视觉解释。"));
            }
        } else {
            answer = "当前页暂时没有可用的图文信息，建议稍后在课件解析完成后重试。";
            fallbackReason = "PAGE_CONTENT_UNAVAILABLE";
        }

        VisualQaAnswerView view = new VisualQaAnswerView(answer, hasVisualSignal, fallbackReason, List.copyOf(evidence));
        persistRecord(coursewareId, pageNo, question, view);
        return view;
    }

    private void persistRecord(String coursewareId, Integer pageNo, String question, VisualQaAnswerView answerView) {
        VisualQaRecordRepository repository = visualQaRecordRepositoryProvider.getIfAvailable();
        if (repository == null) {
            return;
        }
        VisualQaRecordEntity entity = new VisualQaRecordEntity();
        entity.setCoursewareId(coursewareId);
        entity.setPageNo(pageNo);
        entity.setQuestion(question);
        entity.setAnswer(answerView.answer());
        entity.setUsedVision(answerView.usedVision());
        entity.setFallbackReason(answerView.fallbackReason());
        entity.setEvidenceJson(writeJson(answerView.evidence()));
        repository.save(entity);
    }

    private String writeJson(Object value) {
        try {
            return objectMapper.writeValueAsString(value);
        } catch (JsonProcessingException ex) {
            throw new IllegalStateException("Failed to serialize visual QA payload", ex);
        }
    }

    private String summarize(String text) {
        String normalized = text.trim();
        return normalized.length() <= 120 ? normalized : normalized.substring(0, 120) + "...";
    }
}
