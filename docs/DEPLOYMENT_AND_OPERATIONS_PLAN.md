# JARVIS — Deployment and Operations Plan

This document defines the deployment architecture, cloud service orchestration, cron schedules, and operational maintenance for JARVIS on Render.

---

## 1. Cloud Architecture on Render

```text
                      Internet
                         │
                         ▼
             ┌────────────────────────┐
             │   Render Web Service   │
             │   (FastAPI Backend)    │
             │   - REST Endpoints     │
             │   - WebSocket Server   │
             │   - UI Static Host     │
             └───────────┬────────────┘
                         │
          ┌──────────────┴──────────────┐
          ▼                             ▼
┌──────────────────┐          ┌───────────────────┐
│ Render PostgreSQL│          │ Render Cron Jobs  │
│ - Database + RLS │          │ - UTC Expressions │
│ - pgvector       │          │ - Briefings/Check │
└──────────────────┘          └───────────────────┘
```

---

## 2. Service Specifications

### 2.1 Render Web Service
* **Runtime:** Python 3.11+
* **Build Command:** `pip install -r requirements.txt && npm run build --prefix frontend`
* **Start Command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
* **Health Check Path:** `/healthz`
* **Auto-Deploy:** Disabled by default (manual trigger or user approval).

### 2.2 Render Cron Jobs & Timezone Conversions
Render Cron executes on standard **UTC** schedules. All user-facing schedules must be converted to UTC:
* *Asia/Kolkata offset:* UTC + 05:30.
* **Morning Briefing (08:00 IST):**
  * UTC Time: 02:30 UTC
  * Cron Expression: `30 2 * * *`
  * Command: `python -m app.jobs.morning_briefing`
* **Meal Check-in Evaluation (14:00 IST):**
  * UTC Time: 08:30 UTC
  * Cron Expression: `30 8 * * *`
  * Command: `python -m app.jobs.meal_checkin`
* **Evening Briefing (20:00 IST):**
  * UTC Time: 14:30 UTC
  * Cron Expression: `30 14 * * *`
  * Command: `python -m app.jobs.evening_briefing`
* **Memory Consolidation & Expiry Sweep:**
  * UTC Time: 19:30 UTC (01:00 IST)
  * Cron Expression: `30 19 * * *`
  * Command: `python -m app.jobs.memory_consolidation`

---

## 3. Environment Variables & Secret Management

All secrets MUST be configured as server-side environment variables in Render:
```env
# Application
ENVIRONMENT=production
LOG_LEVEL=INFO
APP_SECRET_KEY=<32-byte-secure-hex>
TIMEZONE=Asia/Kolkata

# Database
DATABASE_URL=postgresql+asyncpg://<user>:<password>@<host>/<db>

# External AI Providers
NVIDIA_API_KEY=<nvapi-key>
ELEVENLABS_API_KEY=<elevenlabs-key>
ELEVENLABS_DEFAULT_VOICE_ID=<voice-id>

# CORS & Frontend
ALLOWED_ORIGINS=https://jarvis-app.onrender.com
```

---

## 4. Disaster Recovery & Rollback Plan

1. **Stateless Rollback:** If a bad deploy occurs, Render provides one-click rollback to the previous container build hash.
2. **Database Migrations:** All schema changes are managed via Alembic with reversible `downgrade()` methods. Never drop columns without a multi-phase migration window.
3. **Database Backups:** Automated daily PostgreSQL snapshots enabled on Render managed database.
