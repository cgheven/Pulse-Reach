from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import re
import sqlite3
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml
from anthropic import Anthropic
from dotenv import load_dotenv
from outscraper import ApiClient
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
log = logging.getLogger("pulsehub")


class Qualification(BaseModel):
    relevant: bool
    priority: str = Field(description="Exactly one of A, B, C")
    property_type: str
    estimated_property_count: str
    independent_operator: bool
    ideal_customer: bool
    reasons: list[str] = Field(min_length=1, max_length=3)


class QualificationBatch(BaseModel):
    results: list[Qualification]


@dataclass
class Lead:
    place_id: str
    google_id: str
    name: str
    category: str
    subtypes: str
    website: str
    phone: str
    address: str
    city: str
    postal_code: str
    country: str
    rating: float | None
    reviews: int | None
    business_status: str
    google_maps_url: str
    query: str
    email: str = ""
    linkedin: str = ""
    facebook: str = ""
    instagram: str = ""
    relevant: str = ""
    priority: str = ""
    property_type: str = ""
    estimated_property_count: str = ""
    independent_operator: str = ""
    ideal_customer: str = ""
    claude_reason: str = ""


RAW_FIELDS = list(Lead.__annotations__.keys())


def safe_str(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return ", ".join(str(x) for x in value)
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False)
    return str(value).strip()


def parse_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def normalize_url(value: str) -> str:
    value = value.strip()
    if not value:
        return ""
    if not re.match(r"^https?://", value, re.I):
        value = "https://" + value
    try:
        parsed = urlparse(value)
        host = parsed.netloc.lower().removeprefix("www.")
        path = parsed.path.rstrip("/")
        return f"{host}{path}" if host else value.lower().rstrip("/")
    except Exception:
        return value.lower().rstrip("/")


def normalize_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def load_config(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def db_init(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS leads (
            place_id TEXT PRIMARY KEY,
            google_id TEXT,
            name TEXT,
            category TEXT,
            subtypes TEXT,
            website TEXT,
            phone TEXT,
            address TEXT,
            city TEXT,
            postal_code TEXT,
            country TEXT,
            rating REAL,
            reviews INTEGER,
            business_status TEXT,
            google_maps_url TEXT,
            query TEXT,
            email TEXT,
            linkedin TEXT,
            facebook TEXT,
            instagram TEXT,
            relevant TEXT,
            priority TEXT,
            property_type TEXT,
            estimated_property_count TEXT,
            independent_operator TEXT,
            ideal_customer TEXT,
            claude_reason TEXT,
            raw_json TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            qualified_at TEXT
        )
        """
    )
    # Lightweight migration for databases created by V1.
    cols = {row[1] for row in conn.execute("PRAGMA table_info(leads)").fetchall()}
    if "qualified_at" not in cols:
        conn.execute("ALTER TABLE leads ADD COLUMN qualified_at TEXT")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_leads_priority ON leads(priority)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_leads_website ON leads(website)")
    conn.commit()
    return conn


def normalize_place(raw: dict[str, Any], query: str) -> Lead:
    place_id = safe_str(raw.get("place_id") or raw.get("google_id"))
    website = safe_str(raw.get("site") or raw.get("website"))
    return Lead(
        place_id=place_id,
        google_id=safe_str(raw.get("google_id")),
        name=safe_str(raw.get("name")),
        category=safe_str(raw.get("type")),
        subtypes=safe_str(raw.get("subtypes")),
        website=website,
        phone=safe_str(raw.get("phone")),
        address=safe_str(raw.get("full_address") or raw.get("address")),
        city=safe_str(raw.get("city")),
        postal_code=safe_str(raw.get("postal_code")),
        country=safe_str(raw.get("country")),
        rating=parse_float(raw.get("rating")),
        reviews=parse_int(raw.get("reviews")),
        business_status=safe_str(raw.get("business_status")),
        google_maps_url=safe_str(raw.get("location_link")),
        query=query,
        email=safe_str(raw.get("email")),
        linkedin=safe_str(raw.get("linkedin")),
        facebook=safe_str(raw.get("facebook")),
        instagram=safe_str(raw.get("instagram")),
    )


def lead_key(lead: Lead) -> str:
    if lead.place_id:
        return f"place:{lead.place_id.lower()}"
    if lead.google_id:
        return f"google:{lead.google_id.lower()}"
    if lead.website:
        return f"site:{normalize_url(lead.website)}"
    return f"name:{normalize_name(lead.name)}|city:{normalize_name(lead.city)}"


def merge_leads(leads: list[Lead]) -> list[Lead]:
    merged: dict[str, Lead] = {}
    for lead in leads:
        key = lead_key(lead)
        if not key:
            continue
        if key not in merged:
            merged[key] = lead
            continue
        current = merged[key]
        # Merge complementary fields rather than replacing useful data with blanks.
        for field in RAW_FIELDS:
            if field in {"relevant", "priority", "property_type", "estimated_property_count", "independent_operator", "ideal_customer", "claude_reason"}:
                continue
            current_value = getattr(current, field)
            new_value = getattr(lead, field)
            if (current_value in ("", None)) and new_value not in ("", None):
                setattr(current, field, new_value)
        # Keep the richest query context.
        if lead.query and lead.query not in current.query:
            current.query = f"{current.query}; {lead.query}" if current.query else lead.query
    return list(merged.values())


def fetch_outscraper(config: dict[str, Any]) -> list[Lead]:
    api_key = require_env("OUTSCRAPER_API_KEY")
    client = ApiClient(api_key=api_key)
    results: list[Lead] = []

    for item in config.get("searches", []):
        city = str(item["city"]).strip()
        category = str(item["category"]).strip()
        limit = int(item.get("limit", 20))
        query = f"{category} {city} {config.get('country', 'United Kingdom')}"
        log.info("Searching Outscraper: %s (limit=%d)", query, limit)
        try:
            # Current SDK method. Avoid google_maps_search_v2 because it is not
            # exposed by all supported versions of the Python client.
            result = client.google_maps_search(
                [query],
                limit=limit,
                language=config.get("language", "en"),
                region=config.get("region", "gb"),
            )
        except Exception as exc:
            log.exception("Outscraper failed for %s: %s", query, exc)
            continue

        if isinstance(result, list) and result and isinstance(result[0], list):
            places = result[0]
        elif isinstance(result, list):
            places = result
        else:
            places = []

        count = 0
        for raw in places:
            if not isinstance(raw, dict):
                continue
            lead = normalize_place(raw, query)
            if not lead.place_id or not lead.name:
                continue
            results.append(lead)
            count += 1
        log.info("Received %d results for %s", count, query)

    return merge_leads(results)


def passes_basic_filters(lead: Lead, config: dict[str, Any]) -> bool:
    filters = config.get("filters", {})
    if filters.get("only_operational") and lead.business_status and lead.business_status.upper() not in {"OPERATIONAL", "OPEN"}:
        return False
    min_reviews = int(filters.get("min_reviews", 0))
    if (lead.reviews or 0) < min_reviews:
        return False
    excluded = {str(x).lower().strip() for x in filters.get("exclude_categories", [])}
    blob = f"{lead.category} {lead.subtypes} {lead.name}".lower()
    if any(x and x in blob for x in excluded):
        return False
    return True


def db_upsert_raw(conn: sqlite3.Connection, leads: list[Lead]) -> None:
    for lead in leads:
        existing = conn.execute("SELECT relevant, priority, property_type, estimated_property_count, independent_operator, ideal_customer, claude_reason, qualified_at FROM leads WHERE place_id=?", (lead.place_id,)).fetchone()
        conn.execute(
            """
            INSERT INTO leads (
                place_id, google_id, name, category, subtypes, website, phone, address,
                city, postal_code, country, rating, reviews, business_status,
                google_maps_url, query, email, linkedin, facebook, instagram,
                relevant, priority, property_type, estimated_property_count,
                independent_operator, ideal_customer, claude_reason, raw_json, qualified_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(place_id) DO UPDATE SET
                google_id=excluded.google_id,
                name=excluded.name,
                category=excluded.category,
                subtypes=excluded.subtypes,
                website=CASE WHEN excluded.website!='' THEN excluded.website ELSE leads.website END,
                phone=CASE WHEN excluded.phone!='' THEN excluded.phone ELSE leads.phone END,
                address=CASE WHEN excluded.address!='' THEN excluded.address ELSE leads.address END,
                city=CASE WHEN excluded.city!='' THEN excluded.city ELSE leads.city END,
                postal_code=CASE WHEN excluded.postal_code!='' THEN excluded.postal_code ELSE leads.postal_code END,
                country=CASE WHEN excluded.country!='' THEN excluded.country ELSE leads.country END,
                rating=COALESCE(excluded.rating, leads.rating),
                reviews=COALESCE(excluded.reviews, leads.reviews),
                business_status=excluded.business_status,
                google_maps_url=CASE WHEN excluded.google_maps_url!='' THEN excluded.google_maps_url ELSE leads.google_maps_url END,
                query=excluded.query,
                email=CASE WHEN excluded.email!='' THEN excluded.email ELSE leads.email END,
                linkedin=CASE WHEN excluded.linkedin!='' THEN excluded.linkedin ELSE leads.linkedin END,
                facebook=CASE WHEN excluded.facebook!='' THEN excluded.facebook ELSE leads.facebook END,
                instagram=CASE WHEN excluded.instagram!='' THEN excluded.instagram ELSE leads.instagram END,
                raw_json=excluded.raw_json,
                updated_at=CURRENT_TIMESTAMP
            """,
            (
                lead.place_id, lead.google_id, lead.name, lead.category, lead.subtypes,
                lead.website, lead.phone, lead.address, lead.city, lead.postal_code,
                lead.country, lead.rating, lead.reviews, lead.business_status,
                lead.google_maps_url, lead.query, lead.email, lead.linkedin,
                lead.facebook, lead.instagram,
                existing["relevant"] if existing else lead.relevant,
                existing["priority"] if existing else lead.priority,
                existing["property_type"] if existing else lead.property_type,
                existing["estimated_property_count"] if existing else lead.estimated_property_count,
                existing["independent_operator"] if existing else lead.independent_operator,
                existing["ideal_customer"] if existing else lead.ideal_customer,
                existing["claude_reason"] if existing else lead.claude_reason,
                json.dumps(asdict(lead), ensure_ascii=False),
                existing["qualified_at"] if existing else None,
            ),
        )
    conn.commit()


def rows_to_leads(rows: list[sqlite3.Row]) -> list[Lead]:
    output: list[Lead] = []
    for row in rows:
        values = dict(row)
        output.append(Lead(
            place_id=values.get("place_id", ""),
            google_id=values.get("google_id", ""),
            name=values.get("name", ""),
            category=values.get("category", ""),
            subtypes=values.get("subtypes", ""),
            website=values.get("website", ""),
            phone=values.get("phone", ""),
            address=values.get("address", ""),
            city=values.get("city", ""),
            postal_code=values.get("postal_code", ""),
            country=values.get("country", ""),
            rating=values.get("rating"),
            reviews=values.get("reviews"),
            business_status=values.get("business_status", ""),
            google_maps_url=values.get("google_maps_url", ""),
            query=values.get("query", ""),
            email=values.get("email", ""),
            linkedin=values.get("linkedin", ""),
            facebook=values.get("facebook", ""),
            instagram=values.get("instagram", ""),
            relevant=values.get("relevant", ""),
            priority=values.get("priority", ""),
            property_type=values.get("property_type", ""),
            estimated_property_count=values.get("estimated_property_count", ""),
            independent_operator=values.get("independent_operator", ""),
            ideal_customer=values.get("ideal_customer", ""),
            claude_reason=values.get("claude_reason", ""),
        ))
    return output


def candidates_for_qualification(conn: sqlite3.Connection, config: dict[str, Any], force: bool = False) -> list[Lead]:
    where = ["(priority IS NULL OR priority='')"] if not force else ["1=1"]
    params: list[Any] = []
    only_with_website = bool(config.get("qualification", {}).get("only_send_to_claude_if", {}).get("has_website", False))
    if only_with_website:
        where.append("COALESCE(website,'') != ''")
    sql = "SELECT * FROM leads WHERE " + " AND ".join(where) + " ORDER BY CASE WHEN COALESCE(website,'')='' THEN 1 ELSE 0 END, reviews DESC"
    rows = conn.execute(sql, params).fetchall()
    return rows_to_leads(rows)


def qualification_system_prompt(config: dict[str, Any]) -> str:
    market = config.get("market", "UK")
    return f"""
You qualify business leads for PulseHub, an accommodation management SaaS targeting the {market} market.

IDEAL CUSTOMER:
- Independent accommodation operator or small/mid-sized operating company.
- Usually manages 1-10 properties.
- Accommodation types: hostel, student accommodation, guest house, hotel, co-living, HMO/shared accommodation, boarding house.
- Good prospect: they actually operate/manage accommodation, not merely sell property services.

REJECT / LOW PRIORITY:
- Large national/international chains or institutional PBSA operators.
- Universities, colleges, student unions, charities or public institutions.
- Estate agents, property consultants, licensing firms, construction firms, or software companies that do not themselves operate accommodation.
- Pubs/restaurants/bars where accommodation is incidental and clearly not the core business.

IMPORTANT:
- Do not invent property count, ownership, or business facts.
- Use "unknown" when the evidence is insufficient.
- You are classifying for SALES PRIORITY, not proving legal ownership.
- A = strong fit for founder-led outreach.
- B = potentially relevant but scale/fit is less certain.
- C = poor fit / reject.
- Keep reasons concise and evidence-based.
""".strip()


def lead_prompt(lead: Lead) -> str:
    return f"""
Business:
Name: {lead.name}
Category: {lead.category}
Subtypes: {lead.subtypes}
Website: {lead.website or 'none'}
Phone: {lead.phone or 'none'}
Address: {lead.address}
City: {lead.city}
Postcode: {lead.postal_code}
Rating: {lead.rating if lead.rating is not None else 'unknown'}
Reviews: {lead.reviews if lead.reviews is not None else 'unknown'}
Google Maps URL: {lead.google_maps_url}
Search query that found it: {lead.query}

Classify this business for PulseHub sales outreach.
""".strip()


def qualify_with_claude(conn: sqlite3.Connection, leads: list[Lead], config: dict[str, Any]) -> None:
    if not leads:
        log.info("No new leads require Claude qualification")
        return
    api_key = require_env("ANTHROPIC_API_KEY")
    model = require_env("CLAUDE_MODEL")
    client = Anthropic(api_key=api_key)
    cfg = config.get("qualification", {})
    batch_size = max(1, min(int(cfg.get("batch_size", 10)), 25))
    system = qualification_system_prompt(config)

    for start in range(0, len(leads), batch_size):
        batch = leads[start:start + batch_size]
        numbered = "\n\n".join(f"LEAD {idx+1}\n{lead_prompt(lead)}" for idx, lead in enumerate(batch))
        user = f"Classify each lead independently. Return exactly {len(batch)} results in the same order as the leads.\n\n{numbered}"
        log.info("Qualifying %d-%d of %d leads with Claude", start + 1, start + len(batch), len(leads))
        try:
            response = client.messages.parse(
                model=model,
                max_tokens=max(800, 300 * len(batch)),
                system=system,
                messages=[{"role": "user", "content": user}],
                output_format=QualificationBatch,
            )
            parsed = response.parsed_output
            results = parsed.results if parsed else []
            if len(results) != len(batch):
                raise RuntimeError(f"Claude returned {len(results)} results for {len(batch)} leads")

            for lead, result in zip(batch, results, strict=True):
                priority = result.priority.upper().strip()
                if priority not in {"A", "B", "C"}:
                    priority = "C"
                conn.execute(
                    """
                    UPDATE leads SET relevant=?, priority=?, property_type=?,
                    estimated_property_count=?, independent_operator=?, ideal_customer=?,
                    claude_reason=?, qualified_at=CURRENT_TIMESTAMP, updated_at=CURRENT_TIMESTAMP
                    WHERE place_id=?
                    """,
                    (
                        str(result.relevant).lower(),
                        priority,
                        result.property_type.strip(),
                        result.estimated_property_count.strip(),
                        str(result.independent_operator).lower(),
                        str(result.ideal_customer).lower(),
                        "; ".join(x.strip() for x in result.reasons if x.strip()),
                        lead.place_id,
                    ),
                )
            conn.commit()
        except Exception as exc:
            log.exception("Claude batch failed: %s", exc)
            # Do not mark failed records as qualified. They will retry on the next run.
        time.sleep(float(cfg.get("batch_delay_seconds", 0.2)))


def export_csv_from_db(conn: sqlite3.Connection, path: Path, priority: str | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    sql = "SELECT place_id, google_id, name, category, subtypes, website, phone, address, city, postal_code, country, rating, reviews, business_status, google_maps_url, query, email, linkedin, facebook, instagram, relevant, priority, property_type, estimated_property_count, independent_operator, ideal_customer, claude_reason FROM leads"
    params: list[Any] = []
    if priority:
        sql += " WHERE UPPER(priority)=?"
        params.append(priority.upper())
    sql += " ORDER BY CASE UPPER(priority) WHEN 'A' THEN 1 WHEN 'B' THEN 2 WHEN 'C' THEN 3 ELSE 4 END, reviews DESC"
    rows = conn.execute(sql, params).fetchall()
    if not rows:
        log.warning("No rows to export: %s", path)
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows([dict(row) for row in rows])
    log.info("Exported %d leads to %s", len(rows), path)


def run(config_path: str, force_requalify: bool = False) -> None:
    config = load_config(ROOT / config_path)
    db_path = ROOT / config["output"]["database"]
    conn = db_init(db_path)

    before = conn.execute("SELECT COUNT(*) AS n FROM leads").fetchone()["n"]
    raw_results = fetch_outscraper(config)
    filtered = [lead for lead in raw_results if passes_basic_filters(lead, config)]
    db_upsert_raw(conn, filtered)
    after = conn.execute("SELECT COUNT(*) AS n FROM leads").fetchone()["n"]
    log.info("Discovery: %d raw unique results | %d passed filters | %d total leads in DB | %d new", len(raw_results), len(filtered), after, max(0, after - before))

    candidates = candidates_for_qualification(conn, config, force=force_requalify)
    qualify_with_claude(conn, candidates, config)

    output = config["output"]
    export_csv_from_db(conn, ROOT / output["raw_csv"])
    allowed = [str(x).upper() for x in config.get("qualification", {}).get("priority_to_export", ["A", "B"])]
    if allowed:
        # Keep a single qualified export containing only accepted priorities.
        conn.execute("DROP VIEW IF EXISTS _pulsehub_export")
        placeholders = ",".join("?" for _ in allowed)
        export_path = ROOT / output["qualified_csv"]
        sql = f"SELECT place_id, google_id, name, category, subtypes, website, phone, address, city, postal_code, country, rating, reviews, business_status, google_maps_url, query, email, linkedin, facebook, instagram, relevant, priority, property_type, estimated_property_count, independent_operator, ideal_customer, claude_reason FROM leads WHERE UPPER(priority) IN ({placeholders}) ORDER BY CASE UPPER(priority) WHEN 'A' THEN 1 WHEN 'B' THEN 2 ELSE 3 END, reviews DESC"
        rows = conn.execute(sql, allowed).fetchall()
        export_path.parent.mkdir(parents=True, exist_ok=True)
        if rows:
            with export_path.open("w", newline="", encoding="utf-8-sig") as f:
                writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
                writer.writeheader()
                writer.writerows([dict(r) for r in rows])
            log.info("Exported %d qualified leads to %s", len(rows), export_path)
        else:
            log.warning("No qualified A/B rows yet: %s", export_path)

    counts = conn.execute("SELECT COALESCE(priority,'UNQUALIFIED') AS priority, COUNT(*) AS n FROM leads GROUP BY COALESCE(priority,'UNQUALIFIED') ORDER BY priority").fetchall()
    log.info("Status: %s", ", ".join(f"{row['priority']}={row['n']}" for row in counts))
    log.info("Done. Raw: %s | Qualified: %s | DB: %s", ROOT / output["raw_csv"], ROOT / output["qualified_csv"], db_path)
    conn.close()


def export_existing(config_path: str, priority: str | None = None) -> None:
    config = load_config(ROOT / config_path)
    conn = db_init(ROOT / config["output"]["database"])
    export_csv_from_db(conn, ROOT / "data/exported_leads.csv", priority=priority)
    conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="PulseHub Lead Finder: Outscraper -> Claude -> persistent SQLite/CSV")
    sub = parser.add_subparsers(dest="cmd", required=True)

    run_p = sub.add_parser("run", help="Discover new leads, dedupe, qualify new/unqualified leads, and export")
    run_p.add_argument("--config", default="config.yaml")
    run_p.add_argument("--force-requalify", action="store_true", help="Re-run Claude qualification for every lead in the DB")

    exp_p = sub.add_parser("export", help="Export existing DB rows")
    exp_p.add_argument("--config", default="config.yaml")
    exp_p.add_argument("--priority", choices=["A", "B", "C"], default=None)

    args = parser.parse_args()
    try:
        if args.cmd == "run":
            run(args.config, force_requalify=args.force_requalify)
        elif args.cmd == "export":
            export_existing(args.config, args.priority)
        return 0
    except KeyboardInterrupt:
        log.warning("Interrupted")
        return 130
    except Exception as exc:
        log.exception("Fatal error: %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
