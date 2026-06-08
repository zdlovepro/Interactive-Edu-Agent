# Full 模式联调与部署方案

本文档用于记录 `Interactive-Edu-Agent` 从本地最小联调走向 full 模式、Docker Desktop 部署和后续服务器部署的实施路线。

## 目标边界

full 模式目标是把前端、Java 后端、Python 服务、MySQL、Redis、MinIO、Milvus 放进一套可启动、可联调、可迁移到服务器的部署单元。

当前优先级不是大规模重构业务代码，而是先保证：

1. Docker Desktop 可一键启动完整依赖。
2. 超星课程资源导入可以通过扫码授权完成，不要求用户手填 Cookie。
3. 导入产物可以进入现有课件解析链路。
4. 敏感信息不进入日志、不进入 Git。
5. 后续持久化和 Rive 数字人有清晰扩展路线。

## 当前完成状态

已具备：

1. `docker-compose.full.yml` 包含 MySQL、Redis、MinIO、Milvus、Python、Backend、Frontend。
2. Python 和 Backend 共享 `course_import_data` 卷，用于读取导入 manifest 和课件文件。
3. Python 服务新增超星扫码授权会话，支持 Playwright 打开超星登录页、截取二维码、保存授权 Cookie 到 Redis 或内存 TTL。
4. Backend 新增超星授权代理接口，前端不直接访问 Python 内部 API。
5. Frontend `/course-resource-import` 支持扫码授权、轮询状态、提交 `authSessionId`。
6. Python 超星导入支持 `auth_session_id`，也保留手动 Cookie/Authorization 兜底。
7. Python parse 已支持从 MinIO 下载对象到临时文件后复用现有 PDF/PPTX 解析。

仍未完成：

1. 真实扫码授权需要在 Docker Desktop 启动后联调验证。
2. Java 业务核心仍存在内存态，服务重启后任务、解析结果、讲稿等会丢失。
3. Rive 数字人尚未接入前端运行时。
4. Python 自动化测试环境需要重建，当前本机 `.venv` 指向失效解释器。

## 阶段一：full 模式本地可启动

目标：

1. Docker Desktop 下完整启动所有服务。
2. 前端可以访问后端，后端可以访问 Python。
3. Backend 使用 MySQL、Redis、MinIO。
4. Python 使用 Redis、MinIO、Milvus。

环境要求：

1. Docker Desktop 已启动。
2. `.env.docker` 从 `.env.docker.example` 复制并补齐。
3. 至少提供一个 LLM API key。
4. 如果测试 TTS/ASR，再提供对应阿里云或 DashScope key。

启动命令：

```powershell
Copy-Item .env.docker.example .env.docker
docker compose --env-file .env.docker -f docker-compose.full.yml up -d --build
```

验收方式：

1. `http://localhost` 可以打开前端。
2. `http://localhost/api/v1/health` 或后端健康接口可访问。
3. `http://localhost/python/v1/health` 通过 Nginx 代理或容器网络可访问。
4. MinIO 控制台可登录。
5. Backend 日志没有 MySQL、Redis、MinIO 连接失败。

## 阶段二：超星扫码授权与导入联调

目标：

1. 前端生成超星扫码二维码。
2. 用户用学习通扫码确认。
3. Python 捕获 `_uid` 等超星 Cookie。
4. Cookie 仅保存在 Redis/内存 TTL，不返回前端。
5. 后端导入任务只传 `authSessionId`。
6. Python 完成资源发现、筛选、下载、图片合成 PDF、生成 `parse_ready_manifest.json`。

重点链路：

```text
Frontend
  -> Backend /api/v1/chaoxing/auth/sessions
  -> Python /python/v1/chaoxing/auth/sessions
  -> Playwright opens Chaoxing login page
  -> user scans with Learning App
  -> Python stores Cookie
  -> Frontend submits import task with authSessionId
  -> Backend calls Python course-resource-import/import
```

本阶段已修正的风险点：

1. `transferUrl` 不再直接作为 `studentstudyAjax` 的 Referer。
2. Python 会记录 transfer 跳转后的最终章节页 URL。
3. 后续 `studentstudyAjax` 和 `knowledge/cards` 使用最终章节页 URL 作为 Referer。
4. 如果最终章节页 URL 中包含新的 `cpi`，优先使用该 `cpi`。

验收方式：

1. 前端二维码正常显示。
2. 扫码后状态变为 `AUTHORIZED`。
3. 提交课程 URL 后任务进入 `FETCHING/DISCOVERING/DOWNLOADING`。
4. 产出 `manifest.json` 和 `parse_ready_manifest.json`。
5. 如果发现 slide image，生成 `courseware_from_images.pdf`。
6. 日志中不出现完整 Cookie/Authorization。

## 阶段三：导入产物进入课件解析

目标：

1. 原始 PDF/PPT/PPTX 可进入现有 parse。
2. 图片合成的 `courseware_from_images.pdf` 可进入现有 parse。
3. full 模式下对象存储使用 MinIO。
4. local 模式仍允许本地文件联调。

当前策略：

1. Python 导入模块输出 `parse_ready_manifest.json`。
2. Backend 读取 manifest 中的文件。
3. Backend 将文件按现有 Courseware 解析流程提交。
4. Python parse 根据 `storage/key/fileName/contentType` 解析。
5. `storage=minio` 时，Python 从 MinIO 下载临时文件后解析。

验收方式：

1. 导入完成后生成 Courseware 解析任务。
2. 解析任务能产出页面、文本块和后续讲稿输入。
3. 不要求前端直连 Python。

## 阶段四：业务持久化补齐

这是服务器长期部署前必须继续做的部分。

优先落库对象：

1. Courseware 状态和解析结果。
2. CourseResourceImportTask 状态和文件列表。
3. Lecture script 和页面脚本。
4. Lecture session/record。
5. Video asset。

建议策略：

1. 保留 local profile 的内存实现。
2. full profile 下提供 Repository 实现。
3. Service 层用接口隔离内存实现和 Repository 实现。
4. 不再让 Controller 直接依赖 full-only Repository Bean。
5. 所有任务状态变化落库，并记录错误信息和可重试点。

验收方式：

1. full 模式服务重启后导入任务不丢。
2. 课件解析结果不丢。
3. 讲稿不丢。
4. 前端刷新后仍能看到历史状态。

## 阶段五：Rive 数字人最小接入

目标：

1. 使用根目录现有 `.riv` 文件作为教师数字人资源。
2. 前端讲课页加载 Rive runtime。
3. 播放讲稿音频时进入 speaking/talking 状态。
4. 暂停或无音频时回到 idle 状态。

建议实现：

1. 将 `.riv` 移动或复制到 `frontend/public/avatars/teacher.riv`。
2. 安装 `@rive-app/canvas`。
3. 新增 `RiveAvatarLayer.vue`。
4. 在讲课页面作为视觉层接入，不先改变主业务流程。
5. 第一版只用播放状态驱动，不做复杂口型识别。

验收方式：

1. 前端 build 通过。
2. 讲课页能显示 Rive 数字人。
3. 播放音频时动画状态变化。

## 当前测试策略

已验证：

1. Python `compileall` 通过。
2. Backend `mvn -q -DskipTests compile` 通过。
3. Frontend `npm run build` 通过。
4. Docker compose 静态配置通过。

待修复的测试环境问题：

1. 当前本机 `python-service/.venv` 指向失效的 Python 解释器。
2. 使用 bundled Python 挂载旧 `.venv` 依赖时，`langchain/pydantic v1` 在 Python 3.12 下导入失败。
3. 建议重建 Python 虚拟环境后再跑完整 `pytest -q`。

推荐重建方式：

```powershell
cd python-service
Remove-Item -Recurse -Force .venv
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
.\.venv\Scripts\pytest -q
```

如果本机没有系统 Python，优先使用 Docker 内的 Python 服务跑测试。

## 服务器部署注意事项

1. 不在镜像里写死密钥。
2. 服务器使用 `.env` 或云厂商 Secret 管理环境变量。
3. MinIO、MySQL、Redis、Milvus 数据卷必须持久化。
4. Nginx/反向代理开启 HTTPS。
5. Cookie/Authorization 相关日志必须脱敏。
6. 超星扫码授权依赖服务器 IP 与浏览器环境，可能受平台风控影响，需要保留手动 Cookie 或本地授权工具兜底。
7. 如果服务器扫码不稳定，可以改成本地小工具获取短期授权，再上传 `authSessionId` 或一次性授权包。

