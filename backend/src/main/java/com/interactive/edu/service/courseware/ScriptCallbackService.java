package com.interactive.edu.service.courseware;

import com.interactive.edu.dto.callback.ScriptCallbackRequest;
import com.interactive.edu.entity.Courseware;
import com.interactive.edu.entity.CoursewarePage;
import com.interactive.edu.entity.LectureScript;
import com.interactive.edu.repository.CoursewarePageRepository;
import com.interactive.edu.repository.CoursewareRepository;
import com.interactive.edu.repository.LectureScriptRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.Optional;
import java.util.UUID;

/**
 * 接受 Python A 端（大模型讲稿生成）发出的异步回调
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class ScriptCallbackService {

    private final CoursewareRepository coursewareRepository;
    private final CoursewarePageRepository coursewarePageRepository;
    private final LectureScriptRepository lectureScriptRepository;

    @Transactional(rollbackFor = Exception.class)
    public void processScriptCallback(ScriptCallbackRequest request) {
        log.info("收到讲稿生成异步回调, 课件ID: {}, 状态: {}", request.getCoursewareId(), request.getProcessStatus());
        String processStatus = request.getProcessStatus();
        if (!"SUCCESS".equalsIgnoreCase(processStatus) && !"FAILED".equalsIgnoreCase(processStatus)) {
            log.warn("收到未知的讲稿生成状态，忽略此次回调: coursewareId={}, processStatus={}",
                    request.getCoursewareId(), processStatus);
            return;
        }

        Optional<Courseware> coursewareOpt = coursewareRepository.findById(request.getCoursewareId());
        Courseware courseware;
        if (coursewareOpt.isEmpty()) {
            log.warn("回调的课件ID不存在，创建占位课件后继续处理: {}", request.getCoursewareId());
            courseware = new Courseware();
            courseware.setId(request.getCoursewareId());
            courseware.setStatus("PROCESSING");
            courseware = coursewareRepository.save(courseware);
        } else {
            courseware = coursewareOpt.get();
        }
        if ("FAILED".equalsIgnoreCase(processStatus)) {
            log.error("大模型生成讲稿失败，原因: {}", request.getErrorMessage());
            courseware.setStatus("FAILED");
            coursewareRepository.save(courseware);
            return;
        }

        // 处理 SUCCESS，先清理历史数据，再按本次回调结果重新落库
        List<ScriptCallbackRequest.PageScriptDto> pages = request.getPages();
        coursewarePageRepository.deleteByCoursewareId(courseware.getId());
        lectureScriptRepository.deleteByCoursewareId(courseware.getId());

        if (pages == null || pages.isEmpty()) {
            log.warn("生成状态为SUCCESS，但讲稿为空，已清理历史讲稿数据，可能是纯图或解析异常");
        } else {
            for (ScriptCallbackRequest.PageScriptDto page : pages) {
                // 1. 存储课件页面基本信息
                CoursewarePage cwPage = new CoursewarePage();
                cwPage.setCoursewareId(courseware.getId());
                cwPage.setPageIndex(page.getPageIndex());
                cwPage.setOriginalText(page.getOriginalText());
                coursewarePageRepository.save(cwPage);

                // 2. 存储讲稿的多个切割节点
                if (page.getScripts() != null) {
                    for (ScriptCallbackRequest.ScriptNodeDto node : page.getScripts()) {
                        LectureScript script = new LectureScript();
                        script.setId(UUID.randomUUID().toString().replace("-", ""));
                        script.setCoursewareId(courseware.getId());
                        script.setPageIndex(page.getPageIndex());
                        script.setNodeId(buildScopedNodeId(courseware.getId(), page.getPageIndex(), node.getNodeId()));
                        script.setContent(node.getContent());
                        script.setEditStatus("AUTO");
                        lectureScriptRepository.save(script);
                    }
                }
            }
        }

        // 修改总状态
        courseware.setStatus("READY");
        coursewareRepository.save(courseware);
        log.info("课件 {} 的讲稿落库完成，状态更新为 READY", courseware.getId());
    }

    private String buildScopedNodeId(String coursewareId, Integer pageIndex, String nodeId) {
        String scopedNodeId = coursewareId + "_" + pageIndex + "_" + nodeId;
        if (scopedNodeId.length() <= 64) {
            return scopedNodeId;
        }
        String digest = UUID.nameUUIDFromBytes(scopedNodeId.getBytes(StandardCharsets.UTF_8))
                .toString()
                .replace("-", "");
        return "n_" + digest;
    }
}
