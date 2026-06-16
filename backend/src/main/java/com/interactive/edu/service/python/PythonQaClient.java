package com.interactive.edu.service.python;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.interactive.edu.config.PythonClientProperties;
import com.interactive.edu.exception.ErrorCode;
import com.interactive.edu.exception.ServiceException;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.MediaType;
import org.springframework.http.client.JdkClientHttpRequestFactory;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientException;

import java.io.IOException;
import java.io.OutputStream;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.Duration;

@Slf4j
@Component
public class PythonQaClient {

    private static final Duration STREAM_READ_TIMEOUT = Duration.ofSeconds(60);

    private final PythonClientProperties props;
    private final ObjectMapper objectMapper;
    private final RestClient restClient;
    private final HttpClient streamHttpClient;

    public PythonQaClient(PythonClientProperties props, ObjectMapper objectMapper) {
        this.props = props;
        this.objectMapper = objectMapper;

        HttpClient httpClient = HttpClient.newBuilder()
                .version(HttpClient.Version.HTTP_1_1)
                .connectTimeout(props.getConnectTimeout())
                .build();

        JdkClientHttpRequestFactory requestFactory = new JdkClientHttpRequestFactory(httpClient);
        requestFactory.setReadTimeout(props.getReadTimeout());

        this.restClient = RestClient.builder()
                .requestFactory(requestFactory)
                .build();
        this.streamHttpClient = httpClient;
    }

    public PythonQaResponse askText(PythonQaRequest request) {
        String url = props.getBaseUrl() + props.getQaPath();
        try {
            QaEnvelope envelope = restClient.post()
                    .uri(url)
                    .contentType(MediaType.APPLICATION_JSON)
                    .accept(MediaType.APPLICATION_JSON)
                    .body(request)
                    .retrieve()
                    .body(QaEnvelope.class);

            if (envelope == null) {
                throw new ServiceException(ErrorCode.PYTHON_SERVICE_ERROR, "Python QA returned empty response");
            }
            if (envelope.code() != 0 || envelope.data() == null) {
                throw new ServiceException(ErrorCode.PYTHON_SERVICE_ERROR, "Python QA is unavailable");
            }

            log.info(
                    "Python QA succeeded. sessionId={}, coursewareId={}, evidenceCount={}, latencyMs={}",
                    request.getSessionId(),
                    request.getCoursewareId(),
                    envelope.data().safeEvidence().size(),
                    envelope.data().latencyMs()
            );
            return envelope.data();
        } catch (ServiceException ex) {
            throw ex;
        } catch (RestClientException ex) {
            throw new ServiceException(ErrorCode.PYTHON_SERVICE_ERROR, "Python QA request failed", ex);
        }
    }

    public void streamText(PythonQaRequest request, OutputStream outputStream) {
        HttpRequest httpRequest = HttpRequest.newBuilder(java.net.URI.create(props.getBaseUrl() + props.getQaStreamPath()))
                .POST(HttpRequest.BodyPublishers.ofString(serializeRequest(request), StandardCharsets.UTF_8))
                .header("Content-Type", MediaType.APPLICATION_JSON_VALUE)
                .header("Accept", MediaType.TEXT_EVENT_STREAM_VALUE)
                .timeout(STREAM_READ_TIMEOUT)
                .build();

        try {
            HttpResponse<java.io.InputStream> response = streamHttpClient.send(
                    httpRequest,
                    HttpResponse.BodyHandlers.ofInputStream()
            );

            if (response.statusCode() >= 400) {
                throw new ServiceException(ErrorCode.PYTHON_SERVICE_ERROR, "Python QA stream is unavailable");
            }

            String contentType = response.headers().firstValue("Content-Type").orElse("");
            if (!contentType.contains(MediaType.TEXT_EVENT_STREAM_VALUE)) {
                throw new ServiceException(ErrorCode.PYTHON_SERVICE_ERROR, "Python QA stream returned invalid content type");
            }

            try (java.io.InputStream bodyStream = response.body()) {
                bodyStream.transferTo(outputStream);
                outputStream.flush();
            }

            log.info(
                    "Python QA stream finished. sessionId={}, coursewareId={}, pageIndex={}",
                    request.getSessionId(),
                    request.getCoursewareId(),
                    request.getPageIndex()
            );
        } catch (ServiceException ex) {
            throw ex;
        } catch (IOException | InterruptedException ex) {
            if (ex instanceof InterruptedException) {
                Thread.currentThread().interrupt();
            }
            throw new ServiceException(ErrorCode.PYTHON_SERVICE_ERROR, "Python QA stream request failed", ex);
        }
    }

    private String serializeRequest(PythonQaRequest request) {
        try {
            return objectMapper.writeValueAsString(request);
        } catch (JsonProcessingException ex) {
            throw new ServiceException(ErrorCode.PYTHON_SERVICE_ERROR, "Python QA stream request serialization failed", ex);
        }
    }

    public record QaEnvelope(int code, String message, PythonQaResponse data) {
    }
}
