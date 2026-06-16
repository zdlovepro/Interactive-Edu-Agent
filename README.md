# Interactive-Edu-Agent

## Full Persistent Mode

When `SPRING_PROFILES_ACTIVE=full`:

- MySQL stores courseware metadata, parsed pages, scripts, render tasks, lecture sessions, QA records, interrupt records, and course-resource import tasks.
- Redis stores lecture-session runtime cache and short-lived import-task secrets such as Cookie / Authorization.
- MinIO stores uploaded courseware files when `storage.type=minio`, and TTS audio when `TTS_ENABLED=true`.
- The backend no longer relies on in-memory-only session/task state for the main teaching chain.

Interactive-Edu-Agent 是一个多服务项目，当前主链路包括：

- 课件上传或超星课程导入
- Python 解析课件页内容和页图
- 生成逐页讲稿
- 课堂播放与问答
- 课件页图 + 讲稿 + 音频合成讲解视频并输出 HLS

## 推荐启动方式

推荐优先使用 `Docker Desktop full` 模式。这是目前最完整、最接近最终部署形态的启动方式。

如果你只是想快速改代码或排查某个接口，可以使用 `local` 模式。

## 项目结构

```text
backend/                 Spring Boot 后端
python-service/          FastAPI 服务
frontend/                Vue 3 前端
docs/                    规格与规约
docker-compose.full.yml  完整容器编排
docker-compose-dev.yml   仅依赖容器编排
```

## 运行前准备

### Docker full 模式需要

- Docker Desktop
- 可用网络，用于首次构建镜像
- `docker compose`

### Local 模式需要

- Java 17+
- Maven 3.9+
- Node.js 20+ 和 npm
- Python 3.10 到 3.12

## 环境文件

### 1. Docker full 模式

```powershell
cd D:\205zd\Desktop\Interactive-Edu-Agent
Copy-Item .env.docker.example .env.docker
```

`Docker full` 模式主要读取 `.env.docker`。

至少需要检查这些变量：

- `MYSQL_ROOT_PASSWORD`
- `MYSQL_PASSWORD`
- `MINIO_ACCESS_KEY`
- `MINIO_SECRET_KEY`

如果你希望真实走大模型脚本/问答链路，再补：

- `LLM_API_KEY`
- `DASHSCOPE_API_KEY`

如果你要测试 TTS/ASR，再补：

- `TTS_DASHSCOPE_API_KEY`
- `ASR_QWEN_API_KEY`

默认值说明：

- `TTS_ENABLED=false`
- `ASR_ENABLED=false`
- `STRICT_CHAIN=false`
- `LLM_ENABLE_THINKING=false`

如果你要开启右上角数字人小窗，再补这些变量：

- `DIGITAL_HUMAN_ENABLED=true`
- `DIGITAL_HUMAN_API_KEY`
- `DIGITAL_HUMAN_REF_VIDEO_PATH`
- `DIGITAL_HUMAN_REF_IMAGE_PATH`

`Docker full` 默认会把仓库根目录只读挂载到容器内的 `/workspace`，所以如果你把数字人参考视频和人物图片放在仓库根目录，可以直接配置成：

```properties
DIGITAL_HUMAN_REF_VIDEO_PATH=/workspace/assets/digital-human/reference/avatar.mp4
DIGITAL_HUMAN_REF_IMAGE_PATH=/workspace/assets/digital-human/reference/OIP.png
```

### 2. Local 模式

```powershell
cd D:\205zd\Desktop\Interactive-Edu-Agent
Copy-Item .env.example .env
Copy-Item python-service\.env.example python-service\.env
```

`local` 模式默认不要求 MySQL、Redis、MinIO。

## 从头到尾启动项目

### 方案 A：Docker Desktop full 模式

这是推荐方式。

#### 第 1 步：准备环境变量

```powershell
cd D:\205zd\Desktop\Interactive-Edu-Agent
Copy-Item .env.docker.example .env.docker
```

按需修改 `.env.docker`。

#### 第 2 步：启动全部服务

```powershell
docker compose --env-file .env.docker -f docker-compose.full.yml up -d --build
```

首次构建会比较慢，因为会拉镜像并安装 Python 侧依赖、LibreOffice、ffmpeg、字体等。

#### 第 3 步：检查容器状态

```powershell
docker compose --env-file .env.docker -f docker-compose.full.yml ps
```

健康状态正常时，常用入口如下：

- 前端: `http://localhost`
- 后端健康检查: `http://localhost/api/v1/health`
- Python 健康检查: `http://localhost:8001/python/v1/health`
- Python 文档: `http://localhost:8001/docs`
- MinIO Console: `http://localhost:9001`

#### 第 4 步：验证主链路

1. 打开前端首页。
2. 上传一个 `pdf` 或 `pptx`。
3. 等待课件解析完成。
4. 进入讲稿页，点击“生成讲稿”。
5. 如果讲稿已生成，再点击“生成讲解视频”。
6. 视频渲染完成后，页面会直接预览 HLS。

#### 第 5 步：停止服务

```powershell
docker compose --env-file .env.docker -f docker-compose.full.yml down
```

如果你还想清理卷：

```powershell
docker compose --env-file .env.docker -f docker-compose.full.yml down -v
```

### 方案 B：Local 最小联调模式

这个模式适合改代码、看日志、快速调试。

#### 第 1 步：准备环境变量

```powershell
cd D:\205zd\Desktop\Interactive-Edu-Agent
Copy-Item .env.example .env
Copy-Item python-service\.env.example python-service\.env
```

#### 第 2 步：启动 Python 服务

```powershell
cd D:\205zd\Desktop\Interactive-Edu-Agent\python-service
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
```

#### 第 3 步：启动后端

```powershell
cd D:\205zd\Desktop\Interactive-Edu-Agent\backend
mvn spring-boot:run
```

`application.yml` 默认 profile 是 `local`，不需要额外切换。

#### 第 4 步：启动前端

```powershell
cd D:\205zd\Desktop\Interactive-Edu-Agent\frontend
npm install
npm run dev
```

#### 第 5 步：访问入口

- 前端: `http://localhost:5173`
- 后端健康检查: `http://localhost:8080/api/v1/health`
- Python 健康检查: `http://localhost:8001/python/v1/health`
- Python 文档: `http://localhost:8001/docs`

## 完整业务使用顺序

推荐按这个顺序验证：

1. 启动前端、后端、Python。
2. 上传课件，或进入 `/course-resource-import` 做超星导入。
3. 等待课件状态进入已解析。
4. 打开讲稿页，生成讲稿。
5. 进入课堂页验证播放与问答。
6. 在讲稿页触发“生成讲解视频”。
7. 等待 HLS 生成后直接播放。

## 超星课程导入

前端入口：

- `http://localhost/course-resource-import`，用于 Docker full
- `http://localhost:5173/course-resource-import`，用于 local

推荐优先使用扫码授权链路，而不是手填 Cookie。

当前链路是：

```text
前端创建授权会话
-> Python Playwright 打开超星登录页
-> 用户扫码确认
-> Python 保存短期授权态
-> 前端提交 authSessionId + 课程 URL
-> Python 发现并下载课件资源
-> 生成 parse_ready_manifest
-> 回到现有课件解析主链路
```

## 讲解视频渲染

当前视频链路默认仍然是“课件页图 + 讲稿 + 音频/静音占位 + 字幕”的主闭环。
如果开启 `DIGITAL_HUMAN_ENABLED=true`，Python 渲染层会额外做这些事：

- 只处理你在讲稿页手动勾选的段落
- 连续勾选的页面会自动合并成一段 `videoretalk` 任务
- 复用现有 TTS 音频，并先把参考人物视频拉伸到相同长度再送到阿里云 `videoretalk`
- 把生成的人像视频缩放后叠加到右上角小窗
- 数字人片段会移除自身音轨，最终成片继续使用原始 TTS 音频
- 如果阿里云任务失败，会自动降级回普通课件视频，不阻断主渲染

渲染产物默认在：

- local: `./data/render`
- Docker full: `/app/data/render`

渲染成功后会生成：

- `video_render_input.json`
- `timeline.json`
- `subtitles.srt`
- `lecture.mp4`
- `hls/index.m3u8`

如果某些段落暂时没有 `audioUrl`，系统会生成静音占位视频，方便先验收整体流程。

## 常用排查命令

### Docker full 模式看日志

```powershell
docker compose --env-file .env.docker -f docker-compose.full.yml logs -f backend
docker compose --env-file .env.docker -f docker-compose.full.yml logs -f python-service
docker compose --env-file .env.docker -f docker-compose.full.yml logs -f frontend
```

### 只重建某个服务

```powershell
docker compose --env-file .env.docker -f docker-compose.full.yml build python-service
docker compose --env-file .env.docker -f docker-compose.full.yml up -d python-service
```

### 本地编译检查

```powershell
cd backend
mvn -q -DskipTests compile

cd ..\frontend
npm run build
```

## 常见问题

### `502 Bad Gateway`

通常不是前端问题，而是 `backend` 容器没起来，或者后端没法访问 Python。

先查：

```powershell
docker compose --env-file .env.docker -f docker-compose.full.yml ps
docker compose --env-file .env.docker -f docker-compose.full.yml logs -f backend
```

### Python 服务正常，但课件解析很慢

大文件、超星资源导入、多页渲染时都可能比较慢。可以适当调大：

```properties
PYTHON_CLIENT_READ_TIMEOUT=180s
```

### Docker full 模式里不要把服务地址写成 `localhost`

容器之间访问应该使用服务名，当前 `docker-compose.full.yml` 已经处理好了：

- `mysql`
- `redis`
- `minio`
- `milvus`
- `python-service`
- `backend`

### 讲解视频渲染失败

优先检查三件事：

1. 讲稿是否已经生成。
2. 每页是否已经带有 `pageImagePath`。
3. Python 渲染日志里 `ffmpeg` 是否报错。

## 参考

- [README.md](/D:/205zd/Desktop/Interactive-Edu-Agent/README.md)
- [docs/05-接口与API通信规约.md](/D:/205zd/Desktop/Interactive-Edu-Agent/docs/05-接口与API通信规约.md)
- [backend/src/main/resources/application-local.yml](/D:/205zd/Desktop/Interactive-Edu-Agent/backend/src/main/resources/application-local.yml)
- [backend/src/main/resources/application-full.yml](/D:/205zd/Desktop/Interactive-Edu-Agent/backend/src/main/resources/application-full.yml)
- [docker-compose.full.yml](/D:/205zd/Desktop/Interactive-Edu-Agent/docker-compose.full.yml)
