package com.interactive.edu.vo.chaoxing;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@NoArgsConstructor
@AllArgsConstructor
public class ChaoxingAuthSessionView {
    private String sessionId;
    private String status;
    private String qrCodeUrl;
    private String message;
    private String expiresAt;
    private String authorizedAt;
}
