# Interactive-Edu-Agent

Interactive-Edu-Agent is a multi-service project for courseware parsing, script generation, lecture playback, and Q&A integration. The default startup path is `local`, and the repository also keeps a `full` mode for MySQL/Redis/MinIO-backed persistence.

## Project Structure

```text
backend/          Spring Boot backend
python-service/   FastAPI parsing service
frontend/         Vue 3 frontend
docs/             Specifications and API docs
docker-compose-dev.yml
```

## Environment Files

### Root `.env`

The repository root `.env` is used by:

- `docker-compose-dev.yml`
- backend placeholder values loaded from `backend/src/main/resources/application.yml`

Create it from the sample:

```powershell
cd D:\205zd\Desktop\Interactive-Edu-Agent
cp .env.example .env
```

Important notes:

- `local` mode can run with the sample values as-is.
- `full` mode requires you to review and fill the MySQL / Redis / MinIO values in `.env`.
- `SPRING_PROFILES_ACTIVE` is included as a sample variable, but the safest way to switch the backend to `full` is still the startup argument shown below.

### Python `.env`

The Python service reads `python-service/.env` directly.

```powershell
cd D:\205zd\Desktop\Interactive-Edu-Agent\python-service
cp .env.example .env
```

Important notes:

- Local minimal integration can leave `MILVUS_*` and `LLM_*` values empty.
- Real Milvus retrieval requires `MILVUS_URI` and related credentials.
- Real script generation or model calls require `LLM_API_KEY` and the matching `LLM_*` settings.

### Frontend `.env`

The frontend already has safe defaults in `frontend/.env.example`. If you want local overrides, copy it to `.env.local`:

```powershell
cd D:\205zd\Desktop\Interactive-Edu-Agent\frontend
cp .env.example .env.local
```

## Modes

### Local Minimal Integration Mode

This is the default mode.

- Profile: `local`
- No MySQL, Redis, or MinIO required
- Storage path: `backend/data/courseware`
- Python parse service: `http://localhost:8001/python/v1/parse`
- `TTS_ENABLED=false` by default

Minimum variables that matter in this mode:

- root `.env`: `PYTHON_CLIENT_BASE_URL`, optional `SPRING_PROFILES_ACTIVE`
- `python-service/.env`: defaults are enough
- `frontend/.env.example`: defaults are enough

### Full Persistence Mode

This mode enables the Repository / JPA / MinIO path.

- Profile: `full`
- Requires MySQL, Redis, and MinIO
- Storage type: `minio`
- `docker-compose-dev.yml` reads the root `.env`
- `TTS_ENABLED=false` by default, so Aliyun keys are optional unless you enable TTS

Required variables for full mode:

- `MYSQL_HOST`
- `MYSQL_PORT`
- `MYSQL_DATABASE`
- `MYSQL_USERNAME`
- `MYSQL_PASSWORD`
- `REDIS_HOST`
- `REDIS_PORT`
- `MINIO_ENDPOINT`
- `MINIO_ACCESS_KEY`
- `MINIO_SECRET_KEY`
- `MINIO_BUCKET`
- `PYTHON_CLIENT_BASE_URL`

Optional variables for full mode:

- `REDIS_DATABASE`
- `REDIS_PASSWORD`
- `MINIO_SECURE`
- `TTS_ENABLED`
- `TTS_ALIYUN_APP_KEY`
- `TTS_ALIYUN_ACCESS_KEY_ID`
- `TTS_ALIYUN_ACCESS_KEY_SECRET`

## TTS

TTS is disabled by default in both `local` and `full` modes.

- `TTS_ENABLED=false`: the main parsing / script / lecture flow stays text-only, and `audioUrl` may be `null`
- `TTS_ENABLED=true`: the backend will try to synthesize script audio and attach `audioUrl` to each script node
- If synthesis or upload fails, the backend degrades to text-only and does not fail courseware parsing or script generation

To enable TTS:

1. Set `TTS_ENABLED=true` in the root `.env`
2. Fill `TTS_ALIYUN_APP_KEY`
3. Fill `TTS_ALIYUN_ACCESS_KEY_ID`
4. Fill `TTS_ALIYUN_ACCESS_KEY_SECRET`

Storage behavior:

- `local` mode returns backend-served URLs like `/api/v1/tts/audio/tts-audio/...`
- `full` mode returns MinIO-backed signed URLs when `storage.type=minio`

## Start Local Minimal Integration

1. Prepare environment files.

```powershell
cd D:\205zd\Desktop\Interactive-Edu-Agent
cp .env.example .env
cd python-service
cp .env.example .env
```

2. Start the Python service.

```powershell
cd D:\205zd\Desktop\Interactive-Edu-Agent\python-service
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
```

3. Start the backend.

```powershell
cd D:\205zd\Desktop\Interactive-Edu-Agent\backend
mvn spring-boot:run
```

4. Start the frontend.

```powershell
cd D:\205zd\Desktop\Interactive-Edu-Agent\frontend
npm install
npm run dev
```

URLs:

- Frontend: `http://localhost:5173`
- Backend health: `http://localhost:8080/api/v1/health`
- Python health: `http://localhost:8001/python/v1/health`
- Python docs: `http://localhost:8001/docs`

## Start Full Persistence Mode

1. Prepare the root `.env` and fill the required MySQL / Redis / MinIO values.

```powershell
cd D:\205zd\Desktop\Interactive-Edu-Agent
cp .env.example .env
```

2. Start MySQL, Redis, and MinIO.

```powershell
cd D:\205zd\Desktop\Interactive-Edu-Agent
docker compose -f docker-compose-dev.yml up -d
```

3. Prepare and start the Python service.

```powershell
cd D:\205zd\Desktop\Interactive-Edu-Agent\python-service
cp .env.example .env
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
```

4. Start the backend with the `full` profile.

```powershell
cd D:\205zd\Desktop\Interactive-Edu-Agent\backend
mvn spring-boot:run "-Dspring-boot.run.profiles=full"
```

5. Start the frontend.

```powershell
cd D:\205zd\Desktop\Interactive-Edu-Agent\frontend
npm install
npm run dev
```

## Integration Checklist

1. Upload a `pptx` or `pdf` from the frontend.
2. Confirm the backend calls `POST /python/v1/parse`.
3. Wait for the courseware status to move into the lecture-ready path.
4. Verify text Q&A from the lecture page.

## References

- API contract: `docs/05-接口与API通信规约.md`
- Frontend env sample: `frontend/.env.example`
- Python env sample: `python-service/.env.example`
