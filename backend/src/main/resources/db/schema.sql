CREATE TABLE IF NOT EXISTS courseware (
    id VARCHAR(64) PRIMARY KEY COMMENT 'Courseware id',
    name VARCHAR(255) NOT NULL COMMENT 'Display name',
    file_url VARCHAR(512) NOT NULL COMMENT 'Storage key or local path',
    storage_type VARCHAR(32) NOT NULL DEFAULT 'local' COMMENT 'local or minio',
    original_filename VARCHAR(255) COMMENT 'Original file name',
    file_type VARCHAR(128) NOT NULL COMMENT 'MIME type',
    status VARCHAR(64) NOT NULL DEFAULT 'UPLOADED' COMMENT 'Courseware status',
    current_task_status VARCHAR(32) NOT NULL DEFAULT 'PENDING' COMMENT 'Task status',
    script_opening TEXT COMMENT 'Script opening text',
    script_closing TEXT COMMENT 'Script closing text',
    uploader_id VARCHAR(64) COMMENT 'Uploader user id',
    course_code VARCHAR(64) COMMENT 'Teacher shared course code',
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT 'Created at',
    update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'Updated at'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Courseware metadata';

CREATE TABLE IF NOT EXISTS courseware_page (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    courseware_id VARCHAR(64) NOT NULL COMMENT 'Courseware id',
    page_index INT NOT NULL COMMENT '1-based page index',
    title VARCHAR(255) COMMENT 'Page title',
    original_text TEXT COMMENT 'Parsed text content',
    knowledge_points_json TEXT COMMENT 'Knowledge points JSON',
    image_url VARCHAR(512) COMMENT 'Page image path',
    visual_summary TEXT COMMENT 'Visual summary',
    visual_objects_json TEXT COMMENT 'Visual objects JSON',
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT 'Created at',
    INDEX idx_cw_page (courseware_id, page_index)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Parsed courseware pages';

CREATE TABLE IF NOT EXISTS lecture_script (
    id VARCHAR(64) PRIMARY KEY COMMENT 'Primary key',
    courseware_id VARCHAR(64) NOT NULL COMMENT 'Courseware id',
    page_index INT NOT NULL COMMENT '1-based page index',
    node_id VARCHAR(64) NOT NULL COMMENT 'Script node id',
    title VARCHAR(255) COMMENT 'Page title',
    content TEXT COMMENT 'Generated script content',
    knowledge_points_json TEXT COMMENT 'Knowledge points JSON',
    audio_url VARCHAR(512) COMMENT 'Generated audio URL',
    page_image_url VARCHAR(512) COMMENT 'Page image URL',
    visual_summary TEXT COMMENT 'Visual summary',
    visual_objects_json TEXT COMMENT 'Visual objects JSON',
    digital_human_enabled TINYINT(1) NOT NULL DEFAULT 0 COMMENT 'Whether this segment should use digital human overlay',
    edit_status VARCHAR(32) DEFAULT 'AUTO' COMMENT 'AUTO or EDITED',
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT 'Created at',
    update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'Updated at',
    UNIQUE KEY uk_node_id (node_id),
    INDEX idx_cw_script (courseware_id, page_index)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Lecture script nodes';

CREATE TABLE IF NOT EXISTS courseware_video_render_task (
    courseware_id VARCHAR(64) PRIMARY KEY COMMENT 'Courseware id',
    status VARCHAR(32) NOT NULL DEFAULT 'PENDING' COMMENT 'PENDING/RENDERING/READY/FAILED',
    progress INT NOT NULL DEFAULT 0 COMMENT 'Progress percentage',
    message VARCHAR(255) COMMENT 'Stage message',
    mp4_path VARCHAR(1024) COMMENT 'Rendered mp4 path',
    hls_playlist_path VARCHAR(1024) COMMENT 'Rendered hls playlist path',
    duration_ms BIGINT COMMENT 'Rendered duration',
    segment_count INT COMMENT 'Rendered segment count',
    error_message VARCHAR(1024) COMMENT 'Failure reason',
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT 'Created at',
    update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'Updated at'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Courseware video render task';

CREATE TABLE IF NOT EXISTS qa_record (
    id BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT 'Primary key',
    session_id VARCHAR(128) NOT NULL COMMENT 'Lecture session id',
    courseware_id VARCHAR(64) NOT NULL COMMENT 'Courseware id',
    page_index INT COMMENT 'Current page index',
    node_id VARCHAR(64) COMMENT 'Current node id',
    user_id VARCHAR(64) NOT NULL COMMENT 'Student id',
    ask_text TEXT NOT NULL COMMENT 'Question',
    answer_text TEXT COMMENT 'Answer',
    reference_fragments JSON COMMENT 'Referenced fragments',
    latency_ms BIGINT COMMENT 'Answer latency in milliseconds',
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT 'Created at',
    INDEX idx_session_cw (session_id, courseware_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='QA records';

CREATE TABLE IF NOT EXISTS lecture_interrupt_record (
    id VARCHAR(128) PRIMARY KEY COMMENT 'Interrupt record id',
    session_id VARCHAR(128) NOT NULL COMMENT 'Lecture session id',
    courseware_id VARCHAR(64) NOT NULL COMMENT 'Courseware id',
    page_index INT COMMENT 'Current page index',
    playback_time_seconds DOUBLE COMMENT 'Current playback time',
    asr_text TEXT COMMENT 'ASR transcript during interrupt',
    status VARCHAR(32) NOT NULL DEFAULT 'INTERRUPTED' COMMENT 'INTERRUPTED/ANSWERED/RESUMED',
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT 'Created at',
    update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'Updated at',
    INDEX idx_intr_session (session_id, create_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Lecture interrupt records';

CREATE TABLE IF NOT EXISTS lecture_session (
    id VARCHAR(128) PRIMARY KEY COMMENT 'Session id',
    courseware_id VARCHAR(64) NOT NULL COMMENT 'Courseware id',
    user_id VARCHAR(64) NOT NULL COMMENT 'User id',
    current_page_index INT DEFAULT 1 COMMENT 'Current page index',
    current_node_id VARCHAR(64) COMMENT 'Current node id',
    resume_token VARCHAR(255) COMMENT 'Resume token',
    status VARCHAR(32) DEFAULT 'IDLE' COMMENT 'IDLE/PLAYING/INTERRUPTED/ANSWERING/RESUMING/ENDED',
    breakpoint_time DOUBLE DEFAULT 0 COMMENT 'Current breakpoint time',
    last_seen_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT 'Latest heartbeat time',
    understanding_level VARCHAR(32) DEFAULT 'NORMAL' COMMENT 'POOR/NORMAL/GOOD',
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT 'Created at',
    update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'Updated at',
    INDEX idx_user_cw (user_id, courseware_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Lecture sessions';

CREATE TABLE IF NOT EXISTS course_resource_import_task (
    id VARCHAR(128) PRIMARY KEY COMMENT 'Import task id',
    user_id VARCHAR(64) NOT NULL COMMENT 'Owner user id',
    source_type VARCHAR(64) NOT NULL COMMENT 'Import source type',
    source_url VARCHAR(1024) COMMENT 'Source course URL',
    courseid VARCHAR(128) COMMENT 'Chaoxing courseid',
    clazzid VARCHAR(128) COMMENT 'Chaoxing clazzid',
    cpi VARCHAR(128) COMMENT 'Chaoxing cpi',
    enc VARCHAR(255) COMMENT 'Chaoxing enc',
    referer VARCHAR(1024) COMMENT 'Source referer',
    build_pdf TINYINT(1) NOT NULL DEFAULT 0 COMMENT 'Whether build PDF from slide images',
    auto_parse TINYINT(1) NOT NULL DEFAULT 0 COMMENT 'Whether trigger auto parse',
    output_dir VARCHAR(1024) COMMENT 'Working output directory',
    status VARCHAR(32) NOT NULL DEFAULT 'PENDING' COMMENT 'Task status',
    progress INT NOT NULL DEFAULT 0 COMMENT 'Task progress percentage',
    discovered_count INT NOT NULL DEFAULT 0 COMMENT 'Discovered resources count',
    selected_count INT NOT NULL DEFAULT 0 COMMENT 'Selected resources count',
    downloaded_count INT NOT NULL DEFAULT 0 COMMENT 'Downloaded resources count',
    ignored_count INT NOT NULL DEFAULT 0 COMMENT 'Ignored resources count',
    generated_pdf VARCHAR(1024) COMMENT 'Generated PDF path',
    message VARCHAR(1024) COMMENT 'Task message',
    courseware_id VARCHAR(64) COMMENT 'Auto-created courseware id',
    files_json LONGTEXT COMMENT 'Imported file summary JSON',
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT 'Created at',
    update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'Updated at',
    INDEX idx_import_task_user (user_id, create_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Course resource import tasks';

CREATE TABLE IF NOT EXISTS sys_user (
    id VARCHAR(64) PRIMARY KEY COMMENT 'User id',
    username VARCHAR(128) NOT NULL COMMENT 'Username',
    password VARCHAR(255) NOT NULL COMMENT 'Password hash',
    real_name VARCHAR(64) COMMENT 'Real name',
    role VARCHAR(32) NOT NULL DEFAULT 'STUDENT' COMMENT 'TEACHER/STUDENT/ADMIN',
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT 'Created at',
    update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'Updated at',
    UNIQUE KEY uk_username (username)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='System users';
