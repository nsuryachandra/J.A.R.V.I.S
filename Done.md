# JARVIS — Execution and Testing Guide

This document explains how to set up, run, test, and operate JARVIS (Phases 1 through 19).

---

## 1. Prerequisites

- **Python**: 3.11+
- **Node.js**: 18+ & npm
- **Operating System**: Windows / Linux / macOS

---

## 2. Environment Setup

### Backend (.env)

In `backend/`, copy `.env.example` to `.env` (or create `.env`):

```bash
cd backend
cp .env.example .env
```

Key environment variables:

```ini
APP_NAME=JARVIS
ENVIRONMENT=development
LOG_LEVEL=INFO
APP_SECRET_KEY=dev-insecure-secret-key-at-least-32-characters-long
DATABASE_URL=sqlite+aiosqlite:///./jarvis_dev.db
TIMEZONE=Asia/Kolkata
PORT=8000
HOST=0.0.0.0
CRON_SECRET=dev-cron-secret-key-123

# AI & Voice Providers (Mocked by default for offline testing)
USE_MOCK_MODELS=true
USE_MOCK_VOICE=true
```

---

## 3. Running the Backend

From the `backend/` directory:

```bash
cd backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

The interactive OpenAPI / Swagger documentation is available at:
- **API Docs**: `http://localhost:8000/docs`
- **Health Check**: `http://localhost:8000/api/v1/health`

---

## 4. Running the Frontend

From the `frontend/` directory:

```bash
cd frontend
npm install
npm run dev
```

The frontend dashboard will be available at:
- `http://localhost:5173`

To build for production:

```bash
npm run build
```

---

## 5. Running the Test Suite

Run the full automated test suite (all 282 tests across Phases 1–19):

```bash
cd backend
pytest -v
```

Or for concise summary output:

```bash
pytest -q
```

To run focused Phase 19 Background Scheduling & Jobs tests:

```bash
pytest tests/test_job_runner_service.py tests/test_jobs_api.py -v
```

---

## 6. Operating Background Jobs & Render Cron

### Render Cron Trigger (Webhook)

Render Cron services trigger background jobs via HTTP POST with the shared secret header:

```bash
curl -X POST http://localhost:8000/api/v1/jobs/cron \
  -H "Content-Type: application/json" \
  -H "X-Cron-Secret: dev-cron-secret-key-123" \
  -d '{"job_type": "MORNING_BRIEFING"}'
```

Available `job_type` options:
- `MORNING_BRIEFING`: Daily morning briefing with calendar, routines, and pending priorities.
- `EVENING_BRIEFING`: Evening summary with completed tasks, blockers, and tomorrow's deadlines.
- `NIGHTLY_CONSOLIDATION`: Routine expansion, stale task sweep, and expired memory archiving.
- `SCHEDULER_TICK`: High-frequency periodic tick checking for due routines and check-ins.
- `STALE_TASK_SWEEP`: Categorizes overdue tasks.

### User-Initiated Job Run

Authenticated users can manually trigger a job run for their account:

```bash
curl -X POST http://localhost:8000/api/v1/jobs/trigger \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <USER_JWT_TOKEN>" \
  -d '{"job_type": "MORNING_BRIEFING"}'
```

### Viewing Job History

```bash
curl -X GET "http://localhost:8000/api/v1/jobs/runs?limit=20" \
  -H "Authorization: Bearer <USER_JWT_TOKEN>"
```

---

## 7. Verification Summary

- **Total Automated Tests**: 282 passed (0 failures, 0 errors).
- **Tool Registry**: 54 registered tools governed under the Policy Broker.
- **Frontend**: Clean TypeScript compilation (`tsc -b && vite build` in 152ms).
