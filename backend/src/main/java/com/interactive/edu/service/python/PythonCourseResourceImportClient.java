package com.interactive.edu.service.python;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.interactive.edu.config.PythonClientProperties;
import com.interactive.edu.exception.ErrorCode;
import com.interactive.edu.exception.ServiceException;
import lombok.Builder;
import lombok.Value;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.MediaType;
import org.springframework.http.client.JdkClientHttpRequestFactory;
import org.springframework.stereotype.Component;
import org.springframework.util.StringUtils;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientException;

import java.net.http.HttpClient;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

@Component
@Slf4j
public class PythonCourseResourceImportClient {

    private final PythonClientProperties props;
    private final ObjectMapper objectMapper;
    private final RestClient restClient;

    public PythonCourseResourceImportClient(PythonClientProperties props, ObjectMapper objectMapper) {
        this.props = props;
        this.objectMapper = objectMapper;

        HttpClient httpClient = HttpClient.newBuilder()
                .connectTimeout(props.getConnectTimeout())
                .build();

        JdkClientHttpRequestFactory requestFactory = new JdkClientHttpRequestFactory(httpClient);
        requestFactory.setReadTimeout(props.getReadTimeout());

        this.restClient = RestClient.builder()
                .requestFactory(requestFactory)
                .build();
    }

    public ImportExecutionResult executeImport(String taskId, PythonCourseResourceImportRequest request) {
        String url = props.getBaseUrl() + props.getCourseResourceImportPath();
        long startAt = System.currentTimeMillis();
        try {
            JsonNode envelope = restClient.post()
                    .uri(url)
                    .contentType(MediaType.APPLICATION_JSON)
                    .accept(MediaType.APPLICATION_JSON)
                    .body(buildRequestBody(request))
                    .retrieve()
                    .body(JsonNode.class);

            if (envelope == null) {
                throw new ServiceException(ErrorCode.PYTHON_SERVICE_ERROR, "Course resource importer returned empty response");
            }
            if (envelope.path("code").asInt(-1) != 0) {
                String message = envelope.path("message").asText("Course resource importer failed");
                throw new ServiceException(ErrorCode.PYTHON_SERVICE_ERROR, message);
            }

            ImportExecutionResult result = toImportExecutionResult(envelope.path("data"));
            log.info(
                    "Python course-resource import succeeded. taskId={}, downloaded={}, ignored={}, latencyMs={}",
                    taskId,
                    result.getDownloadedCount(),
                    result.getIgnoredCount(),
                    Math.max(1, System.currentTimeMillis() - startAt)
            );
            return result;
        } catch (ServiceException ex) {
            log.warn(
                    "Python course-resource import returned failure. taskId={}, latencyMs={}, reason={}",
                    taskId,
                    Math.max(1, System.currentTimeMillis() - startAt),
                    ex.getMessage()
            );
            throw ex;
        } catch (RestClientException ex) {
            throw new ServiceException(ErrorCode.PYTHON_SERVICE_ERROR, "Course resource importer call failed", ex);
        }
    }

    private Map<String, Object> buildRequestBody(PythonCourseResourceImportRequest request) {
        Map<String, Object> body = new LinkedHashMap<>();
        body.put("source_type", request.getSourceType());
        body.put("url", emptyToNull(request.getUrl()));
        body.put("courseid", emptyToNull(request.getCourseid()));
        body.put("clazzid", emptyToNull(request.getClazzid()));
        body.put("cpi", emptyToNull(request.getCpi()));
        body.put("enc", emptyToNull(request.getEnc()));
        body.put("auth_session_id", emptyToNull(request.getAuthSessionId()));
        body.put("cookie", emptyToNull(request.getCookie()));
        body.put("authorization", emptyToNull(request.getAuthorization()));
        body.put("referer", emptyToNull(request.getReferer()));
        body.put("output_dir", request.getOutputDir().toString());
        body.put("build_pdf", request.isBuildPdf());
        return body;
    }

    private ImportExecutionResult toImportExecutionResult(JsonNode payload) {
        String manifestPath = payload.path("manifest_path").asText("");
        String parseReadyManifestPath = payload.path("parse_ready_manifest_path").asText("");
        String generatedPdf = payload.path("generated_pdf").isMissingNode() || payload.path("generated_pdf").isNull()
                ? null
                : payload.path("generated_pdf").asText();

        if (!StringUtils.hasText(manifestPath)) {
            throw new ServiceException(ErrorCode.PYTHON_SERVICE_ERROR, "Course resource importer did not return manifest_path");
        }
        if (!StringUtils.hasText(parseReadyManifestPath)) {
            throw new ServiceException(ErrorCode.PYTHON_SERVICE_ERROR, "Course resource importer did not return parse_ready_manifest_path");
        }

        JsonNode manifest = readManifest(manifestPath);
        JsonNode generatedNode = manifest.path("generated").path("pdf_from_slide_images");
        if (!StringUtils.hasText(generatedPdf) && !generatedNode.isMissingNode() && !generatedNode.isNull()) {
            generatedPdf = generatedNode.asText(null);
        }

        int discoveredCount = manifest.path("resource_count").asInt(payload.path("summary").path("discovered").asInt(0));
        int selectedCount = manifest.path("selected_count").asInt(payload.path("summary").path("selected").asInt(0));
        int downloadedCount = manifest.path("downloaded_count").asInt(payload.path("summary").path("downloaded").asInt(0));
        int ignoredCount = manifest.path("ignored_count").asInt(payload.path("summary").path("ignored").asInt(0));

        return ImportExecutionResult.builder()
                .discoveredCount(discoveredCount)
                .selectedCount(selectedCount)
                .downloadedCount(downloadedCount)
                .ignoredCount(ignoredCount)
                .generatedPdf(generatedPdf)
                .parseReadyManifest(parseReadyManifestPath)
                .files(parseFiles(manifest.path("files")))
                .build();
    }

    private JsonNode readManifest(String manifestPath) {
        try {
            Path path = Path.of(manifestPath).toAbsolutePath().normalize();
            if (!Files.exists(path) || !Files.isRegularFile(path)) {
                throw new ServiceException(ErrorCode.PYTHON_SERVICE_ERROR, "Course resource manifest not found: " + path);
            }
            return objectMapper.readTree(path.toFile());
        } catch (ServiceException ex) {
            throw ex;
        } catch (Exception ex) {
            throw new ServiceException(ErrorCode.PYTHON_SERVICE_ERROR, "Failed to read course resource manifest", ex);
        }
    }

    private List<ImportFileResult> parseFiles(JsonNode filesNode) {
        List<ImportFileResult> files = new ArrayList<>();
        if (!filesNode.isArray()) {
            return List.of();
        }

        for (JsonNode item : filesNode) {
            String localPath = item.path("local_path").asText("");
            String fileName = item.path("file_name").asText("");
            if (!StringUtils.hasText(fileName) && StringUtils.hasText(localPath)) {
                fileName = Path.of(localPath).getFileName().toString();
            }

            files.add(ImportFileResult.builder()
                    .fileName(fileName)
                    .resourceKind(item.path("resource_kind").asText("unknown"))
                    .status(item.path("status").asText("SUCCESS").toUpperCase())
                    .localPath(StringUtils.hasText(localPath) ? localPath : null)
                    .confidence(item.path("confidence").isNumber() ? item.path("confidence").asDouble() : null)
                    .reason(item.path("reason").asText(""))
                    .build());
        }
        return List.copyOf(files);
    }

    private String emptyToNull(String value) {
        return StringUtils.hasText(value) ? value.trim() : null;
    }

    @Value
    @Builder
    public static class ImportExecutionResult {
        int discoveredCount;
        int selectedCount;
        int downloadedCount;
        int ignoredCount;
        String generatedPdf;
        String parseReadyManifest;
        List<ImportFileResult> files;
    }

    @Value
    @Builder
    public static class ImportFileResult {
        String fileName;
        String resourceKind;
        String status;
        String localPath;
        Double confidence;
        String reason;
    }
}
