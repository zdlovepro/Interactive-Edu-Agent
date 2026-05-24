package com.interactive.edu.service.python;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.interactive.edu.exception.ErrorCode;
import com.interactive.edu.exception.ServiceException;
import lombok.Builder;
import lombok.RequiredArgsConstructor;
import lombok.Value;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;

import javax.imageio.ImageIO;
import java.awt.Color;
import java.awt.Graphics2D;
import java.awt.image.BufferedImage;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

@Component
@RequiredArgsConstructor
@Slf4j
public class PythonCourseResourceImportClient {

    private final ObjectMapper objectMapper;

    public ImportExecutionResult executeImport(String taskId, PythonCourseResourceImportRequest request) {
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
                            .fileName(slideOne.getFileName().toString())
                            .resourceKind("slide_image")
                            .status("SUCCESS")
                            .localPath(slideOne.toString())
                            .confidence(0.92d)
                            .reason("large 16:9 image likely slide page")
                            .build(),
                    ImportFileResult.builder()
                            .fileName(slideTwo.getFileName().toString())
                            .resourceKind("slide_image")
                            .status("SUCCESS")
                            .localPath(slideTwo.toString())
                            .confidence(0.91d)
                            .reason("large 16:9 image likely slide page")
                            .build(),
                    ImportFileResult.builder()
                            .fileName(originalPdf.getFileName().toString())
                            .resourceKind("courseware_file")
                            .status("SUCCESS")
                            .localPath(originalPdf.toString())
                            .confidence(0.98d)
                            .reason("extension .pdf recognized as courseware file")
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
            objectMapper.writerWithDefaultPrettyPrinter().writeValue(
                    manifestPath.toFile(),
                    manifest
            );

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

    public record ParseReadyFile(String type, String path, String title) {
    }
}
