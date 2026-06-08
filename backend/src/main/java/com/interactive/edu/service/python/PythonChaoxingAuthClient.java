package com.interactive.edu.service.python;

import com.fasterxml.jackson.databind.JsonNode;
import com.interactive.edu.config.PythonClientProperties;
import com.interactive.edu.dto.chaoxing.ChaoxingAuthSessionCreateRequest;
import com.interactive.edu.exception.ErrorCode;
import com.interactive.edu.exception.ServiceException;
import com.interactive.edu.vo.chaoxing.ChaoxingAuthSessionView;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.MediaType;
import org.springframework.http.client.JdkClientHttpRequestFactory;
import org.springframework.stereotype.Component;
import org.springframework.util.StringUtils;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientException;

import java.net.http.HttpClient;
import java.util.LinkedHashMap;
import java.util.Map;

@Component
@Slf4j
public class PythonChaoxingAuthClient {

    private final PythonClientProperties props;
    private final RestClient restClient;

    public PythonChaoxingAuthClient(PythonClientProperties props) {
        this.props = props;

        HttpClient httpClient = HttpClient.newBuilder()
                .connectTimeout(props.getConnectTimeout())
                .build();

        JdkClientHttpRequestFactory requestFactory = new JdkClientHttpRequestFactory(httpClient);
        requestFactory.setReadTimeout(props.getReadTimeout());

        this.restClient = RestClient.builder()
                .requestFactory(requestFactory)
                .build();
    }

    public ChaoxingAuthSessionView createSession(ChaoxingAuthSessionCreateRequest request) {
        Map<String, Object> body = new LinkedHashMap<>();
        body.put("course_url", emptyToNull(request == null ? null : request.getCourseUrl()));
        body.put("user_agent", emptyToNull(request == null ? null : request.getUserAgent()));
        JsonNode payload = post("", body);
        return toView(payload);
    }

    public ChaoxingAuthSessionView getSession(String sessionId) {
        JsonNode payload = get("/" + sessionId);
        return toView(payload);
    }

    public byte[] getQrCode(String sessionId) {
        String url = baseUrl() + "/" + sessionId + "/qrcode";
        try {
            byte[] image = restClient.get()
                    .uri(url)
                    .accept(MediaType.IMAGE_PNG)
                    .retrieve()
                    .body(byte[].class);
            if (image == null || image.length == 0) {
                throw new ServiceException(ErrorCode.PYTHON_SERVICE_ERROR, "Chaoxing QR code is empty");
            }
            return image;
        } catch (ServiceException ex) {
            throw ex;
        } catch (RestClientException ex) {
            throw new ServiceException(ErrorCode.PYTHON_SERVICE_ERROR, "Failed to fetch Chaoxing QR code", ex);
        }
    }

    public ChaoxingAuthSessionView closeSession(String sessionId) {
        JsonNode payload = delete("/" + sessionId);
        return toView(payload);
    }

    private JsonNode post(String path, Map<String, Object> body) {
        try {
            JsonNode envelope = restClient.post()
                    .uri(baseUrl() + path)
                    .contentType(MediaType.APPLICATION_JSON)
                    .accept(MediaType.APPLICATION_JSON)
                    .body(body)
                    .retrieve()
                    .body(JsonNode.class);
            return requireSuccess(envelope);
        } catch (ServiceException ex) {
            throw ex;
        } catch (RestClientException ex) {
            throw new ServiceException(ErrorCode.PYTHON_SERVICE_ERROR, "Chaoxing auth service call failed", ex);
        }
    }

    private JsonNode get(String path) {
        try {
            JsonNode envelope = restClient.get()
                    .uri(baseUrl() + path)
                    .accept(MediaType.APPLICATION_JSON)
                    .retrieve()
                    .body(JsonNode.class);
            return requireSuccess(envelope);
        } catch (ServiceException ex) {
            throw ex;
        } catch (RestClientException ex) {
            throw new ServiceException(ErrorCode.PYTHON_SERVICE_ERROR, "Chaoxing auth service call failed", ex);
        }
    }

    private JsonNode delete(String path) {
        try {
            JsonNode envelope = restClient.delete()
                    .uri(baseUrl() + path)
                    .accept(MediaType.APPLICATION_JSON)
                    .retrieve()
                    .body(JsonNode.class);
            return requireSuccess(envelope);
        } catch (ServiceException ex) {
            throw ex;
        } catch (RestClientException ex) {
            throw new ServiceException(ErrorCode.PYTHON_SERVICE_ERROR, "Chaoxing auth service call failed", ex);
        }
    }

    private JsonNode requireSuccess(JsonNode envelope) {
        if (envelope == null) {
            throw new ServiceException(ErrorCode.PYTHON_SERVICE_ERROR, "Chaoxing auth service returned empty response");
        }
        if (envelope.path("code").asInt(-1) != 0) {
            throw new ServiceException(
                    ErrorCode.PYTHON_SERVICE_ERROR,
                    envelope.path("message").asText("Chaoxing auth service failed")
            );
        }
        return envelope.path("data");
    }

    private ChaoxingAuthSessionView toView(JsonNode payload) {
        return new ChaoxingAuthSessionView(
                payload.path("session_id").asText(payload.path("sessionId").asText("")),
                payload.path("status").asText("UNKNOWN"),
                toBackendQrCodeUrl(payload),
                payload.path("message").isNull() ? null : payload.path("message").asText(null),
                payload.path("expires_at").asText(payload.path("expiresAt").asText(null)),
                payload.path("authorized_at").asText(payload.path("authorizedAt").asText(null))
        );
    }

    private String toBackendQrCodeUrl(JsonNode payload) {
        String sessionId = payload.path("session_id").asText(payload.path("sessionId").asText(""));
        if (!StringUtils.hasText(sessionId)) {
            return null;
        }
        return "/api/v1/chaoxing/auth/sessions/" + sessionId + "/qrcode";
    }

    private String baseUrl() {
        return props.getBaseUrl() + props.getChaoxingAuthPath();
    }

    private String emptyToNull(String value) {
        return StringUtils.hasText(value) ? value.trim() : null;
    }
}
