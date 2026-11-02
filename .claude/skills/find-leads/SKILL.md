---
name: find-leads
description: Find accommodation leads (Dormitory, HMO, Hostel, PG, Guest House) on Google Maps via the Outscraper API and save them to the PulseHub Lead Engine Postgres database, or read saved leads back out by country, city, type, gender, size or contact info. Use when the user asks to find, scrape, search for or pull leads (e.g. "find girls hostels in Lahore", "get 50 PGs in Karachi", "HMOs in Manchester"), or to list/export leads from the database.
---

# Find leads

All commands run from the repo root with the project venv. Results print as JSON on stdout; progress goes to stderr.

## Search and save

```bash
.venv/bin/python scripts/leads.py find --category "Girls Hostel" --category "PG" --city Lahore --country Pakistan --limit 20
```

- `--category` and `--city` are repeatable; every category × city pair is one Outscraper query.
- Search wording drives what Google returns. Useful terms: `Hostel`, `Boys Hostel`, `Girls Hostel`, `PG`, `Paying Guest`, `Dormitory`, `Student Accommodation`, `HMO`, `Guest House`.
- `--country` defaults to `United Kingdom`; it's added to the query and sets the Google region (`--region` overrides).
- Emails are fetched by default through Outscraper's Emails & Contacts enrichment, which costs extra per result. Use `--no-enrich` only if the user wants it cheaper.
- `--campaign "Name"` tags new leads with a campaign (created if missing).
- `--dry-run` previews without writing to the DB. It still spends Outscraper credits.

After saving, every lead is automatically:
- classified by **type** (Dormitory, HMO, Hostel, PG, Guest House, Other) and **gender** (Male, Female, Mixed, or Unknown when the listing doesn't say), using its name and Google categories
- given a **mobile** number when one of its phone numbers is a mobile line
- grouped into an **operator** (listings that share a website domain or phone number) and given a **size**: 1 property = Low, 2–3 = Medium, 4–5 = High, 6+ = Premium

Deduplication runs against the database, so re-running a search only adds new places.

### Before running

- Work out the maximum number of results: `categories × cities × limit`. If it's over 200, tell the user the number and the cost implication (enrichment is on), then confirm before running.
- If the user doesn't give a limit, use 20.

### After running

Report `raw_results`, `new_leads` and `existing_leads`, plus any query with an `error`. Then run `list` for that city and show the top operators. Don't paste the raw JSON.

## Read leads back

Same view as the web app's Leads page: grouped by operator and ranked by number of properties.

```bash
.venv/bin/python scripts/leads.py list --country Pakistan --city Lahore --type Hostel --gender Female --format table
.venv/bin/python scripts/leads.py list --contact both --size Premium --format csv > premium_with_contacts.csv
.venv/bin/python scripts/leads.py list --type PG --listings          # JSON with every property per operator
```

Filters: `--country --city --type --gender --size (Low|Medium|High|Premium) --contact (both|mobile|email) --search`. Output: `--format json|csv|table`, `--limit N`, `--listings`.

## Where the data lives

The Postgres database in `DATABASE_URL` (`.env`), schema `lead_engine`, table `leads`. The useful columns are `name, city, country, accommodation_type, gender, phone, mobile, email, website, google_maps_url, operator_key, operator_name, property_count, size_tier`. The web app serves the same view at `GET /api/directory` (with the same filters) and `GET /api/directory/export` (CSV).
