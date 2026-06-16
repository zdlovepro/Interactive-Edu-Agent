package com.interactive.edu.service.python;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.interactive.edu.config.PythonClientProperties;
import com.interactive.edu.exception.ErrorCode;
import com.interactive.edu.exception.ServiceException;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.MediaType;
import org.springframework.http.client.JdkClientHttpRequestFactory;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientException;

import java.net.http.HttpClient;

@Slf4j
@Component
public class PythonQaIngestClient {

    private final PythonClientProperties props;
    private final RestClient restClient;

    public PythonQaIngestClient(PythonClientProperties props) {
        this.props = props;

        HttpClient httpClient = HttpClient.newBuilder()
                .version(HttpClient.Version.HTTP_1_1)
                .connectTimeout(props.getConnectTimeout())
                .build();

        JdkClientHttpRequestFactory requestFactory = new JdkClientHttpRequestFactory(httpClient);
        requestFactory.setReadTimeout(props.getReadTimeout());

        this.restClient = RestClient.builder()
                .requestFactory(requestFactory)
                .build();
    }

    public IngestPayload ingestPages(PythonQaIngestRequest request) {
        String url = props.getBaseUrl() + props.getQaIngestPagesPath();
        try {
            IngestEnvelope envelope = restClient.post()
                    .uri(url)
                    .contentType(MediaType.APPLICATION_JSON)
                    .accept(MediaType.APPLICATION_JSON)
                    .body(request)
                    .retrieve()
                    .body(IngestEnvelope.class);

            if (envelope == null) {
                throw new ServiceException(ErrorCode.PYTHON_SERVICE_ERROR, "Python QA ingest returned empty response");
            }
            if (envelope.code() != 0 || envelope.data() == null) {
                throw new ServiceException(ErrorCode.PYTHON_SERVICE_ERROR, "Python QA ingest is unavailable");
            }

            log.info(
                    "Python QA ingest succeeded. coursewareId={}, inserted={}, backend={}",
                    request.getCoursewareId(),
                    envelope.data().inserted(),
                    envelope.data().backend()
            );
            return envelope.data();
        } catch (ServiceException ex) {
            throw ex;
        } catch (RestClientException ex) {
            throw new ServiceException(ErrorCode.PYTHON_SERVICE_ERROR, "Python QA ingest request failed", ex);
        }
    }

    @JsonIgnoreProperties(ignoreUnknown = true)
    public record IngestEnvelope(int code, String message, IngestPayload data) {
    }

    @JsonIgnoreProperties(ignoreUnknown = true)
    public record IngestPayload(
            int inserted,
            String backend
    ) {
    }
}
