# PulseHub Lead Engine

Internal sales prospecting workspace for PulseHub.

Outscraper → deduplication → lead storage → Claude qualification → review → pipeline → follow-ups → CSV export.

After setup, the entire workflow is operated from the web UI. There is no CLI for scraping, qualification, import, export, or lead management.

**Setup and login:** see [SETUP.md](SETUP.md).

## 1. Files created / modified

### Backend
- `backend/app/main.py` — FastAPI app, startup import, job worker
- `backend/app/models.py` — PostgreSQL schema
- `backend/app/routers/` — auth, dashboard, campaigns, leads, pipeline, follow-ups, jobs, imports, exports, settings, logs
- `backend/app/services/` — Outscraper, Claude, dedupe, import/export, campaign runner
- `backend/app/worker.py` — in-process background job runner

### Frontend
- `frontend/` — Next.js + TypeScript + Tailwind UI

### Also kept
- `main.py` — legacy CLI (not required for normal use)
- `data/raw_leads.csv` and `data/qualified_leads.csv` — imported automatically on first launch

## 2. Database schema

All Lead Engine tables live in the `lead_engine` schema so they stay isolated from any other database on the same host.

| Table | Purpose |
| --- | --- |
| `users` | Login accounts |
| `leads` | Prospect records + qualification + sales fields |
| `campaigns` | Market / country campaigns |
| `campaign_searches` | City × category × limit |
| `qualification_runs` | Claude batch runs |
| `sales_activity` | Status history |
| `follow_ups` | Follow-up history |
| `jobs` | Background job state |
| `imports` | CSV import results |
| `exports` | Generated CSV files |
| `system_logs` | Operator-visible activity log |
| `app_settings` | Server-side settings and API keys |
| `saved_filters` | Saved lead views |

## 3. Environment variables

Copy `.env.example` to `.env` if needed. Current required values:

```env
DATABASE_URL=postgresql://...          # dedicated Lead Engine database, not PulseHub production
JWT_SECRET=long-random-string
ADMIN_EMAIL=admin@pulsehub.local
ADMIN_PASSWORD=choose-a-strong-password
OUTSCRAPER_API_KEY=...
ANTHROPIC_API_KEY=...
CLAUDE_MODEL=claude-haiku-4-5-20251001
CORS_ORIGINS=http://localhost:3000
DB_SCHEMA=lead_engine
```

API keys are stored server-side only. The browser never receives the raw keys.

## 4. One-time setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cd frontend && npm install && cd ..
```

Confirm `.env` points at a **separate** PostgreSQL database for Lead Engine, not the PulseHub customer/production database.

## 5. Start the application

```bash
chmod +x scripts/dev.sh
./scripts/dev.sh
```

Or in two terminals:

```bash
source .venv/bin/activate
uvicorn app.main:app --app-dir backend --reload --port 8000
```

```bash
cd frontend
npm run dev
```

Open [http://localhost:3000](http://localhost:3000). If that port is already in use, start the frontend with `npx next dev --port 3010`.

Default login:

- Email: `admin@pulsehub.local`
- Password: the `ADMIN_PASSWORD` you set in `.env`

## 6. Import existing leads

On first startup, if the leads table is empty, the app imports:

1. `data/raw_leads.csv`
2. `data/qualified_leads.csv`

Qualification data is preserved and never overwritten by blanks.

You can also import from **Imports**:

- Upload a CSV
- Or click **Re-import bundled CSVs**

The import summary shows Imported / Updated / Skipped / Duplicates / Errors.

## 7. Run a campaign from the UI

1. Open **Campaigns**
2. Click **+ New Campaign**
3. Enter name, market, country
4. Add cities
5. Choose categories and limits
6. Click **Create & Run**
7. Watch live progress (do not leave the page)
8. Review new A+ / A / B / Rejected leads on **Leads**
9. Move them on **Pipeline**
10. Set follow-ups and export from **Export**

Re-running a campaign only sends **new / unqualified** leads to Claude. Existing qualified leads are left untouched.

## 8. How background jobs work

The FastAPI process starts a daemon worker thread.

- `POST /api/campaigns/{id}/run` creates a `jobs` row with status `queued`
- The worker picks it up and sets `running`
- Progress is written to `jobs.progress` after each Outscraper search and Claude batch
- The UI polls `GET /api/jobs/{id}`
- Cancel sets `cancel_requested`
- Failures mark the job `failed` and allow **Retry**

No Redis or Celery is required for this internal deployment. Job state is stored in PostgreSQL.
