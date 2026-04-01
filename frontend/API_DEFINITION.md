# API 接口定义 (阶段一)

基于 **AI互动智课生成与实时问答系统** 的核心API接口定义。

---

## 基础信息

- **BaseURL**: `http://localhost:3000/api/v1`
- **协议**: REST + JSON
- **认证**: Bearer Token (后续实现)
- **时区**: UTC+8

---

## 1. 课件管理接口

### 1.1 上传课件
**POST** `/courseware/upload`

**功能**: 接收PPT/PDF文件，存储至MinIO/本地，返回courseware_id

**请求** (FormData):
```
file: File (PPT或PDF, 最大100MB)
teacherId: string (可选)
courseName: string (可选)
```

**响应** (201):
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "coursewareId": "cw_12345",
    "fileName": "course.pptx",
    "fileSize": 5242880,
    "uploadedAt": "2026-04-01T08:00:00Z",
    "status": "parsing",
    "parseProgress": 0
  }
}
```

**错误** (400, 413, 500):
```json
{
  "code": 1001,
  "message": "文件大小超过100MB"
}
```

---

### 1.2 查询上传进度
**GET** `/courseware/{coursewareId}/status`

**功能**: 查询课件解析进度

**响应** (200):
```json
{
  "code": 0,
  "data": {
    "coursewareId": "cw_12345",
    "status": "parsing",
    "parseProgress": 45,
    "pages": 24,
    "parsedPages": 11,
    "estimatedTime": "2m30s",
    "error": null
  }
}
```

---

### 1.3 获取知识点列表
**GET** `/courseware/{coursewareId}/knowledge-points`

**功能**: 获取解析后的知识点及章节层级

**响应** (200):
```json
{
  "code": 0,
  "data": {
    "knowledgePoints": [
      {
        "id": "kp_001",
        "title": "计算机基础",
        "confidence": 0.95,
        "pageIndices": [0, 1, 2],
        "subPoints": [
          {
            "id": "kp_001_1",
            "title": "硬件组成",
            "confidence": 0.92,
            "pageIndices": [0, 1]
          }
        ]
      }
    ],
    "totalPages": 24,
    "extractedAt": "2026-04-01T08:15:00Z"
  }
}
```

---

## 2. 讲稿生成接口

### 2.1 生成讲稿
**POST** `/script/generate`

**功能**: 基于解析文本调用LLM生成结构化讲稿

**请求**:
```json
{
  "coursewareId": "cw_12345",
  "model": "gpt-4",
  "tone": "interactive",
  "language": "zh-CN",
  "style": {
    "openingStyle": "engaging",
    "explanationLevel": "medium",
    "summaryLevel": "concise"
  }
}
```

**响应** (202):
```json
{
  "code": 0,
  "data": {
    "scriptId": "sc_12345",
    "coursewareId": "cw_12345",
    "status": "generating",
    "generatedAt": "2026-04-01T08:30:00Z",
    "segments": [
      {
        "id": "seg_001",
        "pageIndex": 0,
        "type": "opening",
        "title": "课程介绍",
        "content": "欢迎各位同学...",
        "knowledgePoints": ["课程目标", "学习路径"],
        "estimatedDuration": 120,
        "nodeId": "node_001"
      }
    ]
  }
}
```

---

### 2.2 编辑讲稿
**PUT** `/script/{scriptId}`

**功能**: 教师对生成的讲稿进行编辑修改

**请求**:
```json
{
  "segments": [
    {
      "id": "seg_001",
      "content": "修改后的讲稿内容...",
      "knowledgePoints": ["更新的知识点"]
    }
  ]
}
```

**响应** (200):
```json
{
  "code": 0,
  "data": {
    "scriptId": "sc_12345",
    "updatedAt": "2026-04-01T08:45:00Z",
    "version": 2
  }
}
```

---

## 3. 讲课会话接口

### 3.1 开始讲课
**POST** `/lecture/start`

**功能**: 创建学习会话，返回第一页内容

**请求**:
```json
{
  "coursewareId": "cw_12345",
  "scriptId": "sc_12345",
  "studentId": "student_123",
  "mode": "interactive"
}
```

**响应** (201):
```json
{
  "code": 0,
  "data": {
    "sessionId": "sess_12345",
    "nodeId": "node_001",
    "currentPage": 0,
    "totalPages": 24,
    "segment": {
      "id": "seg_001",
      "title": "课程介绍",
      "content": "欢迎...",
      "audioUrl": "http://cdn.example.com/audio/seg_001.mp3"
    },
    "resumeToken": "node_001@0@initial",
    "startedAt": "2026-04-01T09:00:00Z"
  }
}
```

---

### 3.2 暂停讲课
**POST** `/lecture/pause`

**功能**: 暂停讲课，保存当前进度

**请求**:
```json
{
  "sessionId": "sess_12345",
  "resumeToken": "node_001@0@initial"
}
```

**响应** (200):
```json
{
  "code": 0,
  "data": {
    "sessionId": "sess_12345",
    "status": "paused",
    "pausedAt": "2026-04-01T09:05:00Z"
  }
}
```

---

### 3.3 恢复讲课
**POST** `/lecture/resume`

**功能**: 从保存点恢复讲课

**请求**:
```json
{
  "sessionId": "sess_12345",
  "resumeToken": "node_001@0@initial"
}
```

**响应** (200):
```json
{
  "code": 0,
  "data": {
    "sessionId": "sess_12345",
    "nodeId": "node_001",
    "segment": {
      "id": "seg_001",
      "content": "讲稿内容..."
    },
    "resumedAt": "2026-04-01T09:10:00Z"
  }
}
```

---

## 4. 问答接口

### 4.1 文本问答
**POST** `/qa/ask-text`

**功能**: 学生提出文字问题，系统通过RAG返回答案

**请求**:
```json
{
  "sessionId": "sess_12345",
  "question": "什么是计算机？",
  "nodeId": "node_001",
  "context": {
    "currentPageIndex": 0,
    "previousQuestions": ["上一个问题内容"]
  }
}
```

**响应** (200):
```json
{
  "code": 0,
  "data": {
    "questionId": "qa_12345",
    "question": "什么是计算机？",
    "answer": "计算机是一种能够按照程序运行...",
    "confidence": 0.87,
    "evidenceSegments": [
      {
        "segmentId": "seg_002",
        "pageIndex": 5,
        "excerpt": "计算机的定义是..."
      }
    ],
    "responseTime": 2.3,
    "fallback": false,
    "answeredAt": "2026-04-01T09:05:30Z"
  }
}
```

---

### 4.2 语音问答 (后期)
**POST** `/qa/ask-voice`

**功能**: 学生通过语音提问

**请求** (FormData):
```
sessionId: string
audio: File (WAV/MP3)
nodeId: string
```

**响应** (200): 同4.1，但多返回:
```json
{
  "transcribedQuestion": "问题的文字转录",
  "audioAnswer": "http://cdn.example.com/answer.mp3"
}
```

---

## 5. 进度管理接口

### 5.1 查询进度
**GET** `/progress/{sessionId}`

**功能**: 获取学生学习进度和理解度

**响应** (200):
```json
{
  "code": 0,
  "data": {
    "sessionId": "sess_12345",
    "progress": {
      "currentPage": 5,
      "totalPages": 24,
      "completionRate": 0.208,
      "timeSpent": "5m30s"
    },
    "comprehension": {
      "overallLevel": "medium",
      "byKnowledgePoint": [
        {
          "knowledgePointId": "kp_001",
          "level": "high",
          "confidence": 0.92
        }
      ]
    },
    "resume_checkpoint": {
      "nodeId": "node_005",
      "nodeOffset": 30,
      "state": "answered_question"
    }
  }
}
```

---

### 5.2 调整讲解节奏 (后期)
**POST** `/progress/adjust-pace`

**功能**: 根据理解度自动调整讲解速度

**请求**:
```json
{
  "sessionId": "sess_12345",
  "nodeId": "node_005",
  "recommendedPace": "slow",
  "reason": "学生对该知识点提问多次"
}
```

**响应** (200):
```json
{
  "code": 0,
  "data": {
    "sessionId": "sess_12345",
    "newPace": "slow",
    "nextSegmentId": "seg_005_extended",
    "supplementaryContent": "补充讲解内容..."
  }
}
```

---

## 6. 数据看板接口 (后期)

### 6.1 教学指标看板
**GET** `/metrics/dashboard`

**功能**: 获取教学效果指标

**响应** (200):
```json
{
  "code": 0,
  "data": {
    "course": {
      "coursewareId": "cw_12345",
      "totalSessions": 42,
      "averageCompletionRate": 0.82,
      "averageQuestionCount": 3.2
    },
    "qa": {
      "totalQuestions": 134,
      "averageResponseTime": 3.2,
      "accuracyRate": 0.87,
      "topQuestions": [
        {
          "question": "热门问题",
          "frequency": 12,
          "avgAnswerTime": 2.1
        }
      ]
    },
    "knowledge": {
      "averageComprehension": 0.78,
      "difficultPoints": ["难点知识1", "难点知识2"],
      "masteredPoints": ["掌握的知识点"]
    }
  }
}
```

---

## 错误码

| 错误码 | 含义 | 状态码 |
|--------|------|--------|
| 0 | 成功 | 200/201/202 |
| 1001 | 文件大小超限 | 413 |
| 1002 | 不支持的文件类型 | 400 |
| 1003 | 课件不存在 | 404 |
| 1004 | 解析失败 | 500 |
| 1005 | 讲稿生成失败 | 500 |
| 2001 | 会话不存在 | 404 |
| 2002 | 会话已过期 | 410 |
| 3001 | 问答检索失败 | 500 |
| 3002 | 问题为空 | 400 |
| 9999 | 内部服务错误 | 500 |

---

## 通用响应格式

**成功响应**:
```json
{
  "code": 0,
  "message": "success",
  "data": { ... },
  "timestamp": "2026-04-01T08:00:00Z"
}
```

**失败响应**:
```json
{
  "code": 1001,
  "message": "文件大小超过100MB",
  "errors": [
    {
      "field": "file",
      "message": "size exceeds maximum"
    }
  ],
  "timestamp": "2026-04-01T08:00:00Z",
  "traceId": "trace_abc123"
}
```

---

## 实现建议

1. **课件上传**: 异步处理，前端轮询 `/courseware/{id}/status`
2. **讲稿生成**: 支持分页返回，前端增量更新
3. **问答缓存**: Redis 存储会话上下文 (TTL: 24h)
4. **错误重试**: 指数退避 (500ms, 1s, 2s, 4s)
5. **并发控制**: 单会话锁定，防止冲突

