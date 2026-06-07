package com.interactive.edu.vo.qa;

import java.util.List;

public record VisualQaAnswerView(
        String answer,
        boolean usedVision,
        String fallbackReason,
        List<VisualQaEvidenceView> evidence
) {
}
