#  Interactive-Edu-Agent (基于泛雅平台的AI互动智课生成与实时问答系统)

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Version](https://img.shields.io/badge/version-v3.0.0-green.svg)
![Spring Boot](https://img.shields.io/badge/Spring%20Boot-3.x-brightgreen.svg)
![Vue3](https://img.shields.io/badge/Vue.js-3.x-4FC08D.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688.svg)

> **超星集团企业命题**：本项目旨在依托泛雅网络教学平台，通过大语言模型、数字人与 Edu-Agent 技术，将传统的静态课件（PPT/PDF）一键转化为具备“多模态视觉讲授、随时语音打断问答、学情诊断与主动提问”能力的智能互动课程。

---

##  核心功能与亮点 (Key Features)

本项目突破了传统“录播课”单向输出的局限，实现了真正意义上的 **AI 互动教学**：

1.  **自动化课件获取与解析**：内置智能爬虫，支持通过 URL 一键抓取外部/泛雅平台课件，并进行高精度结构化解析与多模态图表特征提取。
2.  **数字人沉浸式讲授**：自动生��结构化讲稿（开场、讲解、过渡），并通过 TTS 与音素时间戳对齐技术，驱动 2D/3D 数字人进行流媒体视频播报。
3.  **毫秒级 VAD 打断与断点续播**：支持学生通过麦克风随时语音打断。检测到打断时，数字人瞬间切换为“聆听/思考”状态，解答完毕后**精准回到断点继续播放**。
4.  **Edu-Agent 主动式教学**：搭载长短期记忆（Memory）的教学智能体。根据打断提问的内容动态诊断学生掌握度（0-100分）；当学情低于阈值时，Agent 会**主动弹出随堂测验**，并根据作答情况动态“快进”或“重讲”。
5.  **泛雅平台级无缝集成**：提供 10+ 个标准 RESTful API，完美适配学习通移动端 H5 与泛雅 Web 端，支持 OAuth2 鉴权与高并发访问。

---

##  技术栈与架构分工 (Tech Stack)

本项目由 4 人敏捷团队全栈开发，按微服务架构解耦：

### 1. 后端控制中心 (Java)
* **核心框架**：Spring Boot, Spring Security OAuth2, MyBatis-Plus
* **中间件**：Redis, MySQL, MinIO, Quartz (任务调度)
* **实时通信与流媒体**：WebSocket (Netty), FFmpeg (视频 M3U8 切片)
* **职责**：全局状态机管理、第三方语音/数字人 SDK 鉴权对接、10+ 标准 API 封装、高并发限流调优。

### 2. Edu-Agent & 爬虫引擎 
* **核心框架**：FastAPI, LangChain Agent Executor, Pydantic
* **爬虫链路**：Scrapy, Selenium, Aiohttp, BeautifulSoup
* **职责**：反爬绕过与资源下载、大模型结构化讲稿 Prompt 工程、Agent Tool 注册（工具调用）、短期会话 Memory 管理。

### 3. 多模态 RAG & 视觉对齐 
* **核心框架**：FastAPI, LlamaIndex, Transformers
* **向量检索**：PostgreSQL + pgvector, OpenAI/BGE-m3 Embedding
* **音视频与视觉**：MFA (音素时间戳对齐), GPT-4V/Qwen-VL (图表识别)
* **职责**：切片向量入库、多模态上下文 RAG 检索、数字人驱动特征合成、NLP 学情诊断分类器与主动提问引擎。

### 4. 互动流媒体前端 (Vue)
* **核心框架**：Vue3, Element-Plus, Pinia, TypeScript
* **媒体与交互**：Video.js/HLS.js (流媒体渲染), WebRTC/VAD.js (语音端点检测)
* **通信协议**：Axios, WebSocket, SSE (Server-Sent Events)
* **职责**：音频/视频流媒体播放器重构、状态机 UI 渲染（播放/思考/解答）、打断断点控制、移动端/Iframe 跨域集成适配。

---

##  敏捷演进路线 (Roadmap)

本项目采用敏捷开发模式，包含 1 次 MVP 冲刺与 2 次迭代演进：

###  Sprint 0: 纯语音 MVP 原型 (2026.04.04 - 04.22)
- [x] PPT/PDF 文档结构化解析与讲稿生成
- [x] 接入 TTS 与 ASR，实现音频同步播报
- [x] 前端 WebRTC 接入，实现 VAD 语音打断
- [x] 基于 pgvector 的上下文 RAG 检索与 SSE 流式答疑
- [x] 精准记录时间戳，跑通“打断-答疑-断点续播”闭环

###  Iteration 1: 数字人视觉与爬虫自动化 (2026.04.23 - 05.06)
- [x] 目标网站防反爬分析与 URL 批量下载调度
- [x] MFA 音素特征提取与数字人驱动报文对齐
- [x] 后端 FFmpeg 视频 M3U8 流式切片分发
- [x] 前端流媒体播放器重构，实现数字人无缝画面切换
- [x] PPT 图表多模态视觉信息提取入库
###  Iteration 2: Edu-Agent 智能体与验收交付 (2026.05.07 - 05.16)
- [x] 引入 LangChain 升级为具有反思与计划能力的 Agent
- [x] 建立学生长期错题画像与单次授课短期记忆窗口
- [x] NLP 学情诊断引擎：低于阈值触发随堂测验出题
- [x] 动态节奏调控（自动执行视频 `seek` 重讲或跳过）
- [x] 封装泛雅 10+ 标准接口，通过 JMeter 高并发压测
- [x] Docker 容器化打包与方案文档归档

---

##  快速启动 (Quick Start)

项目采用 Docker Compose 进行一键容器化编排，需预先安装 `Docker` 与 `docker-compose`。
### 环境准备
- Docker
- Docker Compose
- JDK 17 或与项目后端实际版本一致的 Java 环境
- Python 3.10+ 或与项目服务依赖一致的版本
- Node.js 18+ 或与前端实际依赖一致的版本

```bash
# 1. 克隆代码仓库
git clone https://github.com/zdlovepro/Interactive-Edu-Agent.git
cd Interactive-Edu-Agent

# 2. 环境变量配置
cp .env.example .env
# 请在 .env 中填入大模型 API Key、数字人 SDK Token 及数据库密码
需要配置的内容通常包括：
- 大模型 API Key
- 对象存储配置
- 数据库地址与账号密码
- Python 服务访问地址
- 媒体或数字人服务密钥

# 3. 一键启动所有服务 (MySQL, Redis, MinIO, Java, Python x2, Nginx)
docker-compose up -d

# 4. 查看服务运行状态
docker-compose ps
```
---
- 前端页面：`http://localhost`
- Java 接口文档：`http://localhost:8080/swagger-ui.html`
- Python 服务文档：`http://localhost:8001/docs`



---


##  接口文档与集成方案
本项目已完全解耦，可按需作为第三方组件嵌入泛雅平台：
* 详细的 10+ 个核心 API 文档位于 `docs/api_reference.md`
* 泛雅平台跨域集成与 Iframe 消息通信方案请参考 `docs/fanya_integration.md`
* 架构设计图与技术演进详见 `docs/architecture/`

##  许可证 (License)
本项目基于 [MIT License](LICENSE) 协议开源。赛事相关所有最终解释权归团队所有。