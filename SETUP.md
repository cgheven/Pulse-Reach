# PulseHub Lead Engine — Setup Guide

This is the one-time setup for the internal sales app. After this, scraping, qualification, import, export, and lead management are all done in the web UI.

## Login

| Field | Value |
| --- | --- |
| URL | http://localhost:3000 |
| Email | `admin@pulsehub.local` |
| Password | the `ADMIN_PASSWORD` from your `.env` |

If port 3000 is already in use, open http://localhost:3010 instead.

Change the password after first login by creating a new admin user in **Settings → Team**, or by updating `ADMIN_EMAIL` / `ADMIN_PASSWORD` in `.env` before the first start.

---

## What you need

- Python 3.10+
- Node.js 18+
- A **separate** PostgreSQL database for Lead Engine
- Outscraper API key
- Anthropic API key

Do **not** point `DATABASE_URL` at the PulseHub production / customer database.

Lead Engine stores its tables in the `lead_engine` schema so they stay isolated even if the host is shared.

---

## 1. Clone and enter the repo

```bash
cd Pulse-Reach
```

---

## 2. Create the environment file

```bash
cp .env.example .env
```

Edit `.env`:

```env
# Dedicated Lead Engine database — not PulseHub production
DATABASE_URL=postgresql://USER:PASSWORD@HOST/lead_engine?sslmode=require

JWT_SECRET=replace-with-a-long-random-string
ADMIN_EMAIL=admin@pulsehub.local
ADMIN_PASSWORD=choose-a-strong-password
ADMIN_NAME=PulseHub Admin

OUTSCRAPER_API_KEY=your-outscraper-key
ANTHROPIC_API_KEY=your-anthropic-key
CLAUDE_MODEL=claude-haiku-4-5-20251001

CORS_ORIGINS=http://localhost:3000
DB_SCHEMA=lead_engine
```

Notes:

- `JWT_SECRET` should be a long random string in any shared or deployed environment.
- API keys stay on the server. The browser never receives the raw values.
- You can also paste keys later in **Settings → API Keys**.

---

## 3. Install dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cd frontend
npm install
cd ..
```

On Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
cd frontend
npm install
cd ..
```

---

## 4. Start the app

### Option A — one command

```bash
chmod +x scripts/dev.sh
./scripts/dev.sh
```

### Option B — two terminals

Terminal 1, API:

```bash
source .venv/bin/activate
uvicorn app.main:app --app-dir backend --reload --host 127.0.0.1 --port 8000
```

Terminal 2, UI:

```bash
cd frontend
npm run dev
```

If port 3000 is taken:

```bash
cd frontend
npx next dev --port 3010
```

Then add `http://localhost:3010` to `CORS_ORIGINS` if you are not using the Next.js `/api` rewrite.

---

## 5. Open and sign in

1. Open http://localhost:3000
2. Email: `admin@pulsehub.local`
3. Password: the `ADMIN_PASSWORD` from your `.env`

On first start the app will:

- Create the `lead_engine` schema and tables
- Create the admin user
- Import `data/raw_leads.csv` and `data/qualified_leads.csv` if the leads table is empty
- Create a default **UK – London Campaign**

You should see the imported leads on the dashboard immediately.

---

## 6. Day-to-day use (no CLI)

| Task | Where in the UI |
| --- | --- |
| See KPIs and charts | Dashboard |
| Discover new leads | Campaigns → New Campaign → Create & Run |
| Review A / B / C leads | Leads |
| Move deals | Pipeline (drag and drop) |
| Work today's list | Follow-ups |
| Download CSVs | Export |
| Upload more CSVs | Settings → Imports |
| Change API keys / model | Settings |
| Inspect job history | Logs |

Campaigns run in the background. Stay on the progress screen; do not run `python scrape.py` or `python qualify.py`.

Re-running a campaign only sends **new or unqualified** leads to Claude. Existing qualified leads are not overwritten.

---

## 7. Import more leads later

Go to **Settings → Imports**.

- Upload a CSV, or
- Click **Re-import bundled CSVs**

The summary shows Imported, Updated, Skipped, Duplicates, and Errors.

Expected columns match `data/raw_leads.csv` / `data/qualified_leads.csv`:

`place_id`, `google_id`, `name`, `category`, `website`, `phone`, `email`, `city`, `country`, `priority`, `property_type`, `claude_reason`, and the other qualification fields.

---

## 8. Add another user

**Settings → Team**

- Name
- Email
- Password

They sign in on the same login screen.

---

## Troubleshooting

**Login rejected**
- Confirm the API is running on port 8000.
- Use `ADMIN_EMAIL` / `ADMIN_PASSWORD` from `.env`. They only apply when the admin user is first created; changing them later doesn't change an existing user's password.
- The first-start admin is created only if that email does not already exist.

**Dashboard is empty**
- Check **Settings → Imports** and re-import the bundled CSVs.
- Confirm `data/raw_leads.csv` and `data/qualified_leads.csv` are in the repo.

**Campaign fails immediately**
- Confirm Outscraper and Claude keys in **Settings → API Keys**.
- Open **Logs** for the error.

**Port already in use**
- API: change `--port 8000`
- UI: `npx next dev --port 3010`

**Database connection error**
- `DATABASE_URL` must be a reachable PostgreSQL URL.
- Do not use the PulseHub production database.
- Neon URLs should include `sslmode=require`.

**Frontend cannot reach the API**
- Start the backend first.
- The Next.js app proxies `/api/*` to `http://127.0.0.1:8000`.

---

## What not to do

Do not use these for normal operation:

```bash
python main.py run
python main.py export
```

`main.py` is the old CLI. The web app replaces it.
