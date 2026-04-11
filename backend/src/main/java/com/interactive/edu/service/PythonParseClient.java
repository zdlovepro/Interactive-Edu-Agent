
import com.interactive.edu.config.PythonClientProperties;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.MediaType;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;

@Slf4j
@Component
@RequiredArgsConstructor
public class PythonParseClient {

    private final PythonClientProperties props;

    @Async
    public void callParseAsync(PythonParseRequest req) {
        try {
            String url = props.getBaseUrl() + props.getParsePath();

            RestClient client = RestClient.builder()
                    .build();

            // 解析服务响应暂不强依赖，只要调用成功就行
            String resp = client.post()
                    .uri(url)
                    .contentType(MediaType.APPLICATION_JSON)
                    .accept(MediaType.APPLICATION_JSON)
                    .body(req)
                    .retrieve()
                    .body(String.class);

            log.info("Python parse called ok, coursewareId={}, resp={}", req.getCoursewareId(), resp);
        } catch (Exception e) {
            log.error("Python parse call failed, coursewareId={}, err={}", req.getCoursewareId(), e.getMessage(), e);
        }
    }
}