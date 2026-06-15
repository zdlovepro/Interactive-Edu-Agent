package com.interactive.edu.service.python;

import com.fasterxml.jackson.databind.JsonNode;
import com.interactive.edu.config.PythonClientProperties;
import com.interactive.edu.exception.ErrorCode;
import com.interactive.edu.exception.ServiceException;
import lombok.Builder;
import lombok.Value;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.MediaType;
import org.springframework.http.client.JdkClientHttpRequestFactory;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientException;

import java.net.http.HttpClient;

@Slf4j
@Component
public class PythonVideoRenderClient {

    private final PythonClientProperties props;
    private final RestClient restClient;

    public PythonVideoRenderClient(PythonClientProperties props) {
        this.props = props;

        HttpClient httpClient = HttpClient.newBuilder()
                .version(HttpClient.Version.HTTP_1_1)
                .connectTimeout(props.getConnectTimeout())
                .build();

        JdkClientHttpRequestFactory requestFactory = new JdkClientHttpRequestFactory(httpClient);
        requestFactory.setReadTimeout(props.getVideoRenderReadTimeout());

        this.restClient = RestClient.builder()
                .requestFactory(requestFactory)
                .build();
    }

    public VideoRenderResult render(PythonVideoRenderRequest request) {
        String url = props.getBaseUrl() + props.getVideoRenderPath();
        long startAt = System.currentTimeMillis();
        try {
            JsonNode envelope = restClient.post()
                    .uri(url)
                    .contentType(MediaType.APPLICATION_JSON)
                    .accept(MediaType.APPLICATION_JSON)
                    .body(request)
                    .retrieve()
                    .body(JsonNode.class);

            if (envelope == null) {
                throw new ServiceException(ErrorCode.PYTHON_SERVICE_ERROR, "Video render service returned empty response");
            }
            if (envelope.path("code").asInt(-1) != 0) {
                throw new ServiceException(
                        ErrorCode.PYTHON_SERVICE_ERROR,
                        envelope.path("message").asText("Video render service failed")
                );
            }

            VideoRenderResult result = toResult(envelope.path("data"));
            log.info(
                    "Python video render succeeded. coursewareId={}, segmentCount={}, latencyMs={}",
                    request.getCoursewareId(),
                    result.getSegmentCount(),
                    Math.max(1, System.currentTimeMillis() - startAt)
            );
            return result;
        } catch (ServiceException ex) {
            throw ex;
        } catch (RestClientException ex) {
            throw new ServiceException(ErrorCode.PYTHON_SERVICE_ERROR, "Video render service call failed", ex);
        }
    }

    private VideoRenderResult toResult(JsonNode data) {
        if (data == null || data.isMissingNode() || data.isNull()) {
            throw new ServiceException(ErrorCode.PYTHON_SERVICE_ERROR, "Video render service returned empty data");
        }
        return VideoRenderResult.builder()
                .outputDir(data.path("outputDir").asText(""))
                .inputManifestPath(data.path("inputManifestPath").asText(""))
                .timelinePath(data.path("timelinePath").asText(""))
                .subtitlePath(data.path("subtitlePath").asText(""))
                .mp4Path(data.path("mp4Path").asText(""))
                .hlsPlaylistPath(data.path("hlsPlaylistPath").asText(""))
                .durationMs(data.path("durationMs").asLong(0))
                .segmentCount(data.path("segmentCount").asInt(0))
                .build();
    }

    @Value
    @Builder
    public static class VideoRenderResult {
        String outputDir;
        String inputManifestPath;
        String timelinePath;
        String subtitlePath;
        String mp4Path;
        String hlsPlaylistPath;
        long durationMs;
        int segmentCount;
    }
}
