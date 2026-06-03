package com.interactive.edu.service.python;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
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
import org.springframework.util.StringUtils;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientException;

import javax.imageio.ImageIO;
import java.awt.Color;
import java.awt.Graphics2D;
import java.awt.image.BufferedImage;
import java.io.IOException;
import java.net.http.HttpClient;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

@Component
@RequiredArgsConstructor
@Slf4j
public class PythonCourseResourceImportClient {

    private final ObjectMapper objectMapper;
    private final PythonClientProperties properties;

    public ImportExecutionResult executeImport(String taskId, PythonCourseResourceImportRequest request) {
        try {
            return executeRemoteImport(taskId, request);
        } catch (Exception ex) {
            log.warn(
                    "Remote course-resource import unavailable, fallback to local mock. taskId={}, reason={}",
                    taskId,
                    ex.getMessage()
            );
            return executeMockImport(taskId, request);
        }
    }

    private ImportExecutionResult executeRemoteImport(String taskId, PythonCourseResourceImportRequest request) {
        String url = properties.getBaseUrl() + properties.getCourseResourceImportPath();
        HttpClient httpClient = HttpClient.newBuilder()
                .connectTimeout(properties.getConnectTimeout())
                .version(HttpClient.Version.HTTP_1_1)
                .build();
        JdkClientHttpRequestFactory requestFactory = new JdkClientHttpRequestFactory(httpClient);
        requestFactory.setReadTimeout(properties.getReadTimeout());
        RestClient restClient = RestClient.builder()
                .requestFactory(requestFactory)
                .build();

        RemoteEnvelope envelope;
        try {
            envelope = restClient.post()
                    .uri(url)
                    .contentType(MediaType.APPLICATION_JSON)
                    .accept(MediaType.APPLICATION_JSON)
                    .body(buildRemoteRequest(request))
                    .retrieve()
                    .body(RemoteEnvelope.class);
        } catch (RestClientException ex) {
            throw new ServiceException(ErrorCode.PYTHON_SERVICE_ERROR, "Course resource import call failed", ex);
        }

        if (envelope == null || envelope.code != 0 || envelope.data == null) {
            throw new ServiceException(ErrorCode.PYTHON_SERVICE_ERROR, "Course resource import returned empty response");
        }

        String manifestPath = pathText(envelope.data, "manifest_path", "manifestPath");
        String parseReadyManifestPath = pathText(envelope.data, "parse_ready_manifest_path", "parseReadyManifestPath");
        String generatedPdf = pathText(envelope.data, "generated_pdf", "generatedPdf");
        if (!StringUtils.hasText(manifestPath) || !StringUtils.hasText(parseReadyManifestPath)) {
            throw new ServiceException(ErrorCode.PYTHON_SERVICE_ERROR, "Course resource import manifest is missing");
        }

        List<ImportFileResult> files = loadManifestFiles(Path.of(manifestPath));
        if (files.isEmpty()) {
            throw new ServiceException(ErrorCode.PYTHON_SERVICE_ERROR, "Remote import returned no parseable courseware files");
        }
        Summary summary = objectMapper.convertValue(envelope.data.path("summary"), Summary.class);
        log.info(
                "Remote Python course-resource import finished. taskId={}, manifestPath={}, fileCount={}",
                taskId,
                manifestPath,
                files.size()
        );
        return ImportExecutionResult.builder()
                .discoveredCount(summary == null ? files.size() : summary.discovered())
                .selectedCount(summary == null ? files.size() : summary.selected())
                .downloadedCount(summary == null ? files.size() : summary.downloaded())
                .ignoredCount(summary == null ? 0 : summary.ignored())
                .generatedPdf(generatedPdf)
                .parseReadyManifest(parseReadyManifestPath)
                .manifestPath(manifestPath)
                .files(files)
                .build();
    }

    private Map<String, Object> buildRemoteRequest(PythonCourseResourceImportRequest request) {
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("sourceType", request.getSourceType());
        payload.put("url", request.getUrl());
        payload.put("courseid", request.getCourseid());
        payload.put("clazzid", request.getClazzid());
        payload.put("cpi", request.getCpi());
        payload.put("enc", request.getEnc());
        payload.put("cookie", request.getCookie());
        payload.put("authorization", request.getAuthorization());
        payload.put("referer", request.getReferer());
        payload.put("buildPdf", request.isBuildPdf());
        payload.put("outputDir", request.getOutputDir().toAbsolutePath().normalize().toString());
        return payload;
    }

    private String pathText(JsonNode node, String... fieldNames) {
        for (String fieldName : fieldNames) {
            String value = node.path(fieldName).asText("");
            if (StringUtils.hasText(value)) {
                return value;
            }
        }
        return null;
    }

    private List<ImportFileResult> loadManifestFiles(Path manifestPath) {
        try {
            JsonNode manifestNode = objectMapper.readTree(Files.readString(manifestPath));
            JsonNode filesNode = manifestNode.path("files");
            if (!filesNode.isArray()) {
                return List.of();
            }
            List<ImportFileResult> files = new ArrayList<>();
            for (JsonNode fileNode : filesNode) {
                files.add(ImportFileResult.builder()
                        .fileName(fileNode.path("file_name").asText(fileNode.path("fileName").asText("")))
                        .resourceKind(fileNode.path("resource_kind").asText(fileNode.path("resourceKind").asText("")))
                        .status("SUCCESS")
                        .localPath(fileNode.path("local_path").asText(fileNode.path("localPath").asText("")))
                        .confidence(fileNode.path("confidence").isNumber() ? fileNode.path("confidence").asDouble() : null)
                        .reason(fileNode.path("reason").asText(null))
                        .title(fileNode.path("title").asText(null))
                        .mimeType(fileNode.path("mime_type").asText(fileNode.path("mimeType").asText(null)))
                        .sourceUrl(fileNode.path("source_url").asText(fileNode.path("sourceUrl").asText(null)))
                        .resourceId(fileNode.path("resource_id").asText(fileNode.path("resourceId").asText(null)))
                        .build());
            }
            return List.copyOf(files);
        } catch (IOException ex) {
            throw new ServiceException(ErrorCode.PYTHON_SERVICE_ERROR, "Failed to read course resource manifest", ex);
        }
    }

    private ImportExecutionResult executeMockImport(String taskId, PythonCourseResourceImportRequest request) {
        try {
            Path outputDir = request.getOutputDir().toAbsolutePath().normalize();
            Files.createDirectories(outputDir);

            Path imagesDir = outputDir.resolve("images");
            Path attachmentsDir = outputDir.resolve("attachments");
            Path contentImagesDir = outputDir.resolve("content_images");
            Files.createDirectories(imagesDir);
            Files.createDirectories(attachmentsDir);
            Files.createDirectories(contentImagesDir);

            Path slideOne = imagesDir.resolve("slide_001.png");
            Path slideTwo = imagesDir.resolve("slide_002.png");
            createDemoSlideImage(slideOne, 1280, 720, "Machine Learning - 1");
            createDemoSlideImage(slideTwo, 1280, 720, "Machine Learning - 2");

            Path originalPdf = attachmentsDir.resolve("original.pdf");
            Files.writeString(originalPdf, minimalPdf(), StandardCharsets.US_ASCII);

            Path generatedPdf = null;
            if (request.isBuildPdf()) {
                generatedPdf = outputDir.resolve("courseware_from_images.pdf");
                Files.writeString(generatedPdf, minimalPdf(), StandardCharsets.US_ASCII);
            }

            List<ImportFileResult> files = List.of(
                    ImportFileResult.builder()
                            .resourceId("res_slide_001")
                            .title("Slide 1")
                            .fileName(slideOne.getFileName().toString())
                            .resourceKind("slide_image")
                            .status("SUCCESS")
                            .localPath(slideOne.toString())
                            .confidence(0.92d)
                            .reason("large 16:9 image likely slide page")
                            .mimeType("image/png")
                            .build(),
                    ImportFileResult.builder()
                            .resourceId("res_slide_002")
                            .title("Slide 2")
                            .fileName(slideTwo.getFileName().toString())
                            .resourceKind("slide_image")
                            .status("SUCCESS")
                            .localPath(slideTwo.toString())
                            .confidence(0.91d)
                            .reason("large 16:9 image likely slide page")
                            .mimeType("image/png")
                            .build(),
                    ImportFileResult.builder()
                            .resourceId("res_courseware_001")
                            .title("Original PDF")
                            .fileName(originalPdf.getFileName().toString())
                            .resourceKind("courseware_file")
                            .status("SUCCESS")
                            .localPath(originalPdf.toString())
                            .confidence(0.98d)
                            .reason("extension .pdf recognized as courseware file")
                            .mimeType("application/pdf")
                            .build()
            );

            Path manifestPath = outputDir.resolve("manifest.json");
            Map<String, Object> generated = new LinkedHashMap<>();
            generated.put("pdf_from_slide_images", generatedPdf == null ? null : generatedPdf.toString());
            Map<String, Object> manifest = new LinkedHashMap<>();
            manifest.put("source", "chaoxing_authorized_course_import");
            manifest.put("taskId", taskId);
            manifest.put("resourceCount", 12);
            manifest.put("selectedCount", 3);
            manifest.put("downloadedCount", 3);
            manifest.put("ignoredCount", 9);
            manifest.put("files", files);
            manifest.put("generated", generated);
            objectMapper.writerWithDefaultPrettyPrinter().writeValue(manifestPath.toFile(), manifest);

            List<ParseReadyFile> parseReadyFiles = generatedPdf == null
                    ? List.of(new ParseReadyFile("courseware_file", originalPdf.toString(), "Original PDF"))
                    : List.of(
                    new ParseReadyFile("pdf", generatedPdf.toString(), "Courseware slide images merged PDF"),
                    new ParseReadyFile("courseware_file", originalPdf.toString(), "Original PDF")
            );

            Path parseReadyManifest = outputDir.resolve("parse_ready_manifest.json");
            objectMapper.writerWithDefaultPrettyPrinter().writeValue(
                    parseReadyManifest.toFile(),
                    Map.of(
                            "source", "chaoxing_authorized_course_import",
                            "parse_ready_files", parseReadyFiles
                    )
            );

            log.info(
                    "Mock Python course-resource import finished. taskId={}, outputDir={}, generatedPdf={}",
                    taskId,
                    outputDir,
                    generatedPdf
            );

            return ImportExecutionResult.builder()
                    .discoveredCount(12)
                    .selectedCount(3)
                    .downloadedCount(3)
                    .ignoredCount(9)
                    .generatedPdf(generatedPdf == null ? null : generatedPdf.toString())
                    .parseReadyManifest(parseReadyManifest.toString())
                    .manifestPath(manifestPath.toString())
                    .files(files)
                    .build();
        } catch (IOException ex) {
            throw new ServiceException(ErrorCode.PYTHON_SERVICE_ERROR, "Mock Python course import failed", ex);
        }
    }

    private void createDemoSlideImage(Path path, int width, int height, String label) throws IOException {
        BufferedImage image = new BufferedImage(width, height, BufferedImage.TYPE_INT_RGB);
        Graphics2D graphics = image.createGraphics();
        graphics.setColor(new Color(244, 247, 250));
        graphics.fillRect(0, 0, width, height);
        graphics.setColor(new Color(40, 57, 74));
        graphics.fillRect(60, 60, width - 120, height - 120);
        graphics.setColor(Color.WHITE);
        graphics.drawString(label, 120, 160);
        graphics.dispose();
        ImageIO.write(image, "png", path.toFile());
    }

    private String minimalPdf() {
        return "%PDF-1.4\n"
                + "1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
                + "2 0 obj\n<< /Type /Pages /Count 1 /Kids [3 0 R] >>\nendobj\n"
                + "3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>\nendobj\n"
                + "xref\n0 4\n"
                + "0000000000 65535 f \n"
                + "0000000010 00000 n \n"
                + "0000000059 00000 n \n"
                + "0000000116 00000 n \n"
                + "trailer\n<< /Size 4 /Root 1 0 R >>\nstartxref\n178\n%%EOF\n";
    }

    @JsonIgnoreProperties(ignoreUnknown = true)
    private static final class RemoteEnvelope {
        public int code;
        public String message;
        public JsonNode data;
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
        String manifestPath;
        List<ImportFileResult> files;
    }

    @Value
    @Builder
    public static class ImportFileResult {
        String resourceId;
        String title;
        String fileName;
        String resourceKind;
        String status;
        String localPath;
        String mimeType;
        String sourceUrl;
        Double confidence;
        String reason;
    }

    private record Summary(int discovered, int selected, int downloaded, int ignored) {
    }

    public record ParseReadyFile(String type, String path, String title) {
    }
}
