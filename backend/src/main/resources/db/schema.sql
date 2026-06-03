-- 1. 课件表
CREATE TABLE IF NOT EXISTS courseware (
    id VARCHAR(64) PRIMARY KEY COMMENT '课件唯一ID，如 cware_xxxxx',
    name VARCHAR(255) NOT NULL COMMENT '课件名称',
    file_url VARCHAR(512) NOT NULL COMMENT '在 MinIO 中的存储路径/URL',
    file_type VARCHAR(32) NOT NULL COMMENT '文件类型：PDF/PPTX 等',
    status VARCHAR(64) NOT NULL DEFAULT 'UPLOADED' COMMENT '状态：UPLOADED, PARSING, PARSED, GENERATING, READY, FAILED',
    uploader_id VARCHAR(64) COMMENT '上传教师ID',
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='课件基础信息表';

-- 2. 课件解析页面表
CREATE TABLE IF NOT EXISTS courseware_page (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    courseware_id VARCHAR(64) NOT NULL COMMENT '关联课件ID',
    page_index INT NOT NULL COMMENT '页码，从1开始',
    original_text TEXT COMMENT '通过 Python 解析引擎提取的原文',
    image_url VARCHAR(512) COMMENT '该页的截图/截图地址',
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    INDEX idx_cw_page (courseware_id, page_index)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='课件分页解析内容表';

-- 3. 讲稿脚本表
CREATE TABLE IF NOT EXISTS lecture_script (
    id VARCHAR(64) PRIMARY KEY COMMENT '主键ID',
    courseware_id VARCHAR(64) NOT NULL COMMENT '关联课件ID',
    page_index INT NOT NULL COMMENT '所在页码',
    node_id VARCHAR(64) NOT NULL COMMENT '讲授片段节点ID，例如 node_001',
    content TEXT COMMENT '由大模型生成的讲授文本脚本',
    audio_url VARCHAR(512) COMMENT 'TTS 语音播报地址',
    edit_status VARCHAR(32) DEFAULT 'AUTO' COMMENT '编辑状态：AUTO(AI生成), EDITED(教师修改过)',
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    UNIQUE KEY uk_node_id (node_id),
    INDEX idx_cw_script (courseware_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='结构化讲稿表';

-- 4. 问答记录表
CREATE TABLE IF NOT EXISTS qa_record (
    id BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '主键ID',
    session_id VARCHAR(128) NOT NULL COMMENT '讲课交互会话ID',
    courseware_id VARCHAR(64) NOT NULL COMMENT '关联的课件ID',
    node_id VARCHAR(64) COMMENT '当前打断在哪一个节点ID',
    user_id VARCHAR(64) NOT NULL COMMENT '提问的用户(学生)ID',
    ask_text TEXT NOT NULL COMMENT '学生的提问内容',
    answer_text TEXT COMMENT '大模型的回答内容',
    reference_fragments JSON COMMENT '引用的溯源课件片段',
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '产生时间',
    INDEX idx_session_cw (session_id, courseware_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='实时问答交互记录表';

-- 5. 讲课会话与进度表
CREATE TABLE IF NOT EXISTS lecture_session (
    id VARCHAR(128) PRIMARY KEY COMMENT '会话ID，如 sess_xxxxx',
    courseware_id VARCHAR(64) NOT NULL COMMENT '正在学习的课件ID',
    user_id VARCHAR(64) NOT NULL COMMENT '学习该课件的学生/用户ID',
    current_page_index INT DEFAULT 1 COMMENT '当前播放到的页码',
    current_node_id VARCHAR(64) COMMENT '当前播放/打断的具体节点ID',
    resume_token VARCHAR(255) COMMENT '恢复讲课所需的续接 Token',
    status VARCHAR(32) DEFAULT 'ACTIVE' COMMENT '状态：ACTIVE(进行中), PAUSED(暂停), FINISHED(已完成)',
    understanding_level VARCHAR(32) DEFAULT 'NORMAL' COMMENT 'AI判定的学生理解度：POOR, NORMAL, GOOD (用于动态调速)',
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '会话开始时间',
    update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '最近一次进度更新时间',
    INDEX idx_user_cw (user_id, courseware_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='讲课交互会话与学习进度表';

-- 6. 系统用户表
CREATE TABLE IF NOT EXISTS sys_user (
    id VARCHAR(64) PRIMARY KEY COMMENT '用户ID',
    username VARCHAR(128) NOT NULL COMMENT '用户名/学号/工号',
    password VARCHAR(255) NOT NULL COMMENT '密码哈希',
    real_name VARCHAR(64) COMMENT '真实姓名',
    role VARCHAR(32) NOT NULL DEFAULT 'STUDENT' COMMENT '角色：TEACHER, STUDENT, ADMIN',
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '注册时间',
    update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    UNIQUE KEY uk_username (username)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='系统用户表';

-- 7. 超星导入任务表
CREATE TABLE IF NOT EXISTS chaoxing_import_task (
    id VARCHAR(64) PRIMARY KEY COMMENT '导入任务ID',
    course_url VARCHAR(1024) COMMENT '课程URL',
    course_id VARCHAR(64) COMMENT '课程ID',
    clazz_id VARCHAR(64) COMMENT '班级ID',
    cpi VARCHAR(64) COMMENT '超星cpi',
    enc VARCHAR(255) COMMENT '超星enc',
    owner_user_id VARCHAR(64) COMMENT '提交任务的用户ID',
    status VARCHAR(32) NOT NULL COMMENT '任务状态',
    stage VARCHAR(64) COMMENT '任务阶段',
    progress INT DEFAULT 0 COMMENT '进度百分比',
    message VARCHAR(1024) COMMENT '提示信息',
    error_message TEXT COMMENT '错误信息',
    output_dir VARCHAR(1024) COMMENT '输出目录',
    manifest_path VARCHAR(1024) COMMENT 'manifest路径',
    parse_ready_manifest_path VARCHAR(1024) COMMENT 'parse-ready manifest路径',
    generated_pdf VARCHAR(1024) COMMENT '导入生成的PDF',
    courseware_id VARCHAR(64) COMMENT '转化后的课件ID',
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='超星导入任务表';

-- 8. 超星资源明细表
CREATE TABLE IF NOT EXISTS chaoxing_resource (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    task_id VARCHAR(64) NOT NULL COMMENT '导入任务ID',
    resource_id VARCHAR(128) COMMENT '资源ID',
    title VARCHAR(512) COMMENT '资源标题',
    file_name VARCHAR(255) COMMENT '文件名',
    resource_kind VARCHAR(64) COMMENT '资源类型',
    status VARCHAR(32) COMMENT '下载状态',
    local_path VARCHAR(1024) COMMENT '本地路径',
    mime_type VARCHAR(128) COMMENT 'MIME类型',
    source_url VARCHAR(1024) COMMENT '来源URL',
    confidence DOUBLE COMMENT '分类置信度',
    reason TEXT COMMENT '分类理由',
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    INDEX idx_chaoxing_resource_task (task_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='超星资源明细表';

-- 9. TTS 音频表
CREATE TABLE IF NOT EXISTS tts_audio (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    courseware_id VARCHAR(64) NOT NULL COMMENT '课件ID',
    script_id VARCHAR(64) COMMENT '讲稿ID',
    page_no INT COMMENT '页码',
    audio_url VARCHAR(1024) NOT NULL COMMENT '音频URL',
    provider VARCHAR(64) COMMENT 'TTS提供方',
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    INDEX idx_tts_audio_courseware (courseware_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='TTS音频表';

-- 10. 课堂记录表
CREATE TABLE IF NOT EXISTS lecture_record (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    courseware_id VARCHAR(64) NOT NULL COMMENT '课件ID',
    page_no INT COMMENT '页码',
    record_type VARCHAR(64) NOT NULL COMMENT '记录类型',
    payload_json LONGTEXT COMMENT '记录载荷',
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    INDEX idx_lecture_record_courseware (courseware_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='课堂记录表';

-- 11. 数字人任务表
CREATE TABLE IF NOT EXISTS digital_human_task (
    id VARCHAR(64) PRIMARY KEY COMMENT '数字人任务ID',
    courseware_id VARCHAR(64) NOT NULL COMMENT '课件ID',
    page_no INT COMMENT '页码',
    script_id VARCHAR(64) COMMENT '讲稿ID',
    audio_url VARCHAR(1024) COMMENT '音频URL',
    mode VARCHAR(32) COMMENT '任务模式',
    status VARCHAR(32) NOT NULL COMMENT '任务状态',
    stage VARCHAR(64) COMMENT '任务阶段',
    progress INT DEFAULT 0 COMMENT '进度',
    message VARCHAR(1024) COMMENT '提示信息',
    error_message TEXT COMMENT '错误信息',
    timeline_json LONGTEXT COMMENT '时间轴JSON',
    phonemes_json LONGTEXT COMMENT '音素JSON',
    action_frames_json LONGTEXT COMMENT '动作帧JSON',
    audio_json TEXT COMMENT '音频元数据JSON',
    protocol_json LONGTEXT COMMENT '协议JSON',
    protocol_xml LONGTEXT COMMENT '协议XML',
    warnings_json TEXT COMMENT '告警信息JSON',
    video_asset_id VARCHAR(64) COMMENT '绑定视频资产ID',
    video_url VARCHAR(1024) COMMENT '视频URL',
    hls_asset_id VARCHAR(64) COMMENT '绑定HLS资产ID',
    hls_url VARCHAR(1024) COMMENT 'HLS URL',
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    INDEX idx_digital_human_courseware_page (courseware_id, page_no)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='数字人任务表';

-- 12. 视频资产表
CREATE TABLE IF NOT EXISTS video_asset (
    id VARCHAR(64) PRIMARY KEY COMMENT '视频资产ID',
    name VARCHAR(255) COMMENT '展示名',
    original_filename VARCHAR(255) COMMENT '原始文件名',
    status VARCHAR(32) COMMENT '状态',
    source_url VARCHAR(1024) COMMENT '源视频URL',
    sample BIT DEFAULT 0 COMMENT '是否样例视频',
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='视频资产表';

-- 13. HLS 资产表
CREATE TABLE IF NOT EXISTS hls_asset (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    video_asset_id VARCHAR(64) NOT NULL COMMENT '视频资产ID',
    playlist_url VARCHAR(1024) COMMENT 'm3u8地址',
    segment_urls_json LONGTEXT COMMENT '切片URL列表JSON',
    status VARCHAR(32) COMMENT '状态',
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    INDEX idx_hls_asset_video (video_asset_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='HLS资产表';

-- 14. 视觉问答记录表
CREATE TABLE IF NOT EXISTS visual_qa_record (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    courseware_id VARCHAR(64) NOT NULL COMMENT '课件ID',
    page_no INT COMMENT '页码',
    question TEXT NOT NULL COMMENT '问题',
    answer TEXT COMMENT '回答',
    used_vision BIT DEFAULT 0 COMMENT '是否使用视觉信号',
    fallback_reason VARCHAR(512) COMMENT '降级原因',
    evidence_json LONGTEXT COMMENT '证据JSON',
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    INDEX idx_visual_qa_courseware (courseware_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='视觉问答记录表';
