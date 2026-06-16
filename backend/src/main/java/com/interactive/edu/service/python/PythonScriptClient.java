package com.interactive.edu.service.python;

import com.fasterxml.jackson.annotation.JsonProperty;
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
import java.net.http.HttpClient;
import java.time.Duration;
import java.util.Collections;
import java.util.List;

@Slf4j
@Component
public class PythonScriptClient {

    private static final Duration MIN_SCRIPT_READ_TIMEOUT = Duration.ofMinutes(10);

    private final PythonClientProperties props;
    private final ObjectMapper objectMapper;
    private final RestClient restClient;

    public PythonScriptClient(PythonClientProperties props, ObjectMapper objectMapper) {
        this.props = props;
        this.objectMapper = objectMapper;

        HttpClient httpClient = HttpClient.newBuilder()
                .version(HttpClient.Version.HTTP_1_1)
                .connectTimeout(props.getConnectTimeout())
                .build();

        JdkClientHttpRequestFactory requestFactory = new JdkClientHttpRequestFactory(httpClient);
        requestFactory.setReadTimeout(resolveReadTimeout(props));

        this.restClient = RestClient.builder()
                .requestFactory(requestFactory)
                .build();
    }

    public ScriptPayload generate(PythonScriptRequest request) {
        String url = props.getBaseUrl() + props.getScriptGeneratePath();
        try {
            byte[] responseBytes = restClient.post()
                    .uri(url)
                    .contentType(MediaType.APPLICATION_JSON)
                    .accept(MediaType.APPLICATION_JSON)
                    .body(request)
                    .retrieve()
                    .body(byte[].class);

            if (responseBytes == null || responseBytes.length == 0) {
                throw new ServiceException(ErrorCode.PYTHON_SERVICE_ERROR, "Python script generation returned empty response");
            }

            ScriptEnvelope envelope = objectMapper.readValue(responseBytes, ScriptEnvelope.class);
            if (envelope.code() != 0 || envelope.data() == null) {
                throw new ServiceException(ErrorCode.PYTHON_SERVICE_ERROR, "Python script generation is unavailable");
            }

            log.info(
                    "Python script generation succeeded. coursewareId={}, pages={}",
                    request.getCoursewareId(),
                    envelope.data().safePages().size()
            );
            return envelope.data();
        } catch (ServiceException ex) {
            throw ex;
        } catch (JsonProcessingException ex) {
            throw new ServiceException(ErrorCode.PYTHON_SERVICE_ERROR, "Python script generation response parsing failed", ex);
        } catch (IOException ex) {
            throw new ServiceException(ErrorCode.PYTHON_SERVICE_ERROR, "Python script generation response reading failed", ex);
        } catch (RestClientException ex) {
            throw new ServiceException(ErrorCode.PYTHON_SERVICE_ERROR, "Python script generation request failed", ex);
        }
    }

    public record ScriptEnvelope(int code, String message, ScriptPayload data) {
    }

    public record ScriptPayload(
            @JsonProperty("courseware_id") String coursewareId,
            String opening,
            List<PageScriptPayload> pages,
            String closing
    ) {
        public List<PageScriptPayload> safePages() {
            return pages == null ? Collections.emptyList() : pages;
        }
    }

    public record PageScriptPayload(
            @JsonProperty("page_index") int pageIndex,
            String script,
            String transition
    ) {
    }

    private static Duration resolveReadTimeout(PythonClientProperties props) {
        Duration configured = props.getReadTimeout();
        if (configured == null || configured.compareTo(MIN_SCRIPT_READ_TIMEOUT) < 0) {
            return MIN_SCRIPT_READ_TIMEOUT;
        }
        return configured;
    }
}
