package com.interactive.edu.service.python;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.interactive.edu.config.PythonClientProperties;
import com.interactive.edu.exception.ErrorCode;
import com.interactive.edu.exception.ServiceException;
import lombok.Builder;
import lombok.RequiredArgsConstructor;
import lombok.Value;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.MediaType;
import org.springframework.http.client.JdkClientHttpRequestFactory;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientException;

import java.net.http.HttpClient;
import java.util.List;

@Component
@RequiredArgsConstructor
@Slf4j
public class PythonDigitalHumanClient {

    private final PythonClientProperties properties;

    public AudioDriveResult generateAudioDrive(AudioDriveRequest request) {
        HttpClient httpClient = HttpClient.newBuilder()
                .connectTimeout(properties.getConnectTimeout())
                .version(HttpClient.Version.HTTP_1_1)
                .build();
        JdkClientHttpRequestFactory requestFactory = new JdkClientHttpRequestFactory(httpClient);
        requestFactory.setReadTimeout(properties.getReadTimeout());
        RestClient restClient = RestClient.builder()
                .requestFactory(requestFactory)
                .build();

        String url = properties.getBaseUrl() + properties.getDigitalHumanAudioDrivePath();
        try {
            AudioDriveEnvelope envelope = restClient.post()
                    .uri(url)
                    .contentType(MediaType.APPLICATION_JSON)
                    .accept(MediaType.APPLICATION_JSON)
                    .body(request)
                    .retrieve()
                    .body(AudioDriveEnvelope.class);

            if (envelope == null || envelope.code() != 0 || envelope.data() == null) {
                throw new ServiceException(ErrorCode.PYTHON_SERVICE_ERROR, "Digital-human audio-drive returned empty response");
            }

            log.info(
                    "Python digital-human audio-drive succeeded. coursewareId={}, pageIndex={}, frames={}",
                    request.getCoursewareId(),
                    request.getPageIndex(),
                    envelope.data().safeFrames().size()
            );
            return envelope.data();
        } catch (RestClientException ex) {
            throw new ServiceException(ErrorCode.PYTHON_SERVICE_ERROR, "Digital-human audio-drive call failed", ex);
        }
    }

    @Value
    @Builder
    public static class AudioDriveRequest {
        String coursewareId;
        Integer pageIndex;
        String scriptText;
        String audioPath;
        String audioUrl;
        Integer audioDurationMs;
        String protocolFormat;
        String avatarId;
        String sdkVersion;
    }

    public record AudioDriveEnvelope(int code, String message, AudioDriveResult data) {
    }

    @JsonIgnoreProperties(ignoreUnknown = true)
    public record AudioDriveResult(
            String coursewareId,
            Integer pageIndex,
            Object audio,
            List<Object> tokens,
            List<Object> phonemes,
            List<Object> frames,
            Object protocolJson,
            String protocolXml,
            List<String> warnings
    ) {
        public List<Object> safeTokens() {
            return tokens == null ? List.of() : tokens;
        }

        public List<Object> safePhonemes() {
            return phonemes == null ? List.of() : phonemes;
        }

        public List<Object> safeFrames() {
            return frames == null ? List.of() : frames;
        }

        public List<String> safeWarnings() {
            return warnings == null ? List.of() : warnings;
        }
    }
}
