package com.interactive.edu.service.python;

import com.interactive.edu.config.PythonClientProperties;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.MediaType;
import org.springframework.http.client.JdkClientHttpRequestFactory;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;

import java.net.http.HttpClient;

@Slf4j
@Component
public class PythonParseClient {

    private final PythonClientProperties props;
    private final RestClient restClient;

    public PythonParseClient(PythonClientProperties props) {
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

    @Async
    public void callParseAsync(PythonParseRequest req) {
        try {
            String url = props.getBaseUrl() + props.getParsePath();

            // 解析服务响应暂不强依赖，只要调用成功就行
            String resp = restClient.post()
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