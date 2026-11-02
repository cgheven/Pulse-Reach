"""Command-line lead finder: Outscraper -> dedupe -> Postgres (lead_engine schema).

Run from the repo root:
    .venv/bin/python scripts/leads.py find --category "Girls Hostel" --city Lahore --country Pakistan --limit 20
    .venv/bin/python scripts/leads.py list --country Pakistan --type Hostel --gender Female --format table

Machine-readable results go to stdout (JSON by default); progress goes to stderr.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from typing import Any

from .database import SessionLocal, init_db
from .migrate import migrate_schema
from .models import Campaign, Lead
from .services.directory import ACCOMMODATION_TYPES, GENDERS, OTHER_TYPE, TIERS, UNKNOWN_GENDER, query_directory, refresh_directory
from .services.leads import lead_to_dict, load_index, upsert_discovered
from .services.logging_service import log_event
from .services.outscraper import region_for, search_places
from .services.settings_service import get_outscraper_key

PREVIEW_FIELDS = ("name", "accommodation_type", "gender", "city", "country", "phone", "mobile", "email", "website", "rating", "reviews", "google_maps_url")


def _err(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def _ensure_schema() -> None:
    init_db()
    migrate_schema()


def _get_or_create_campaign(db, name: str, country: str) -> Campaign:
    campaign = db.query(Campaign).filter(Campaign.name == name).first()
    if campaign:
        return campaign
    campaign = Campaign(name=name, market=region_for(country) or country, country=country, status="completed")
    db.add(campaign)
    db.flush()
    return campaign


def cmd_find(args: argparse.Namespace) -> int:
    _ensure_schema()
    db = SessionLocal()
    try:
        api_key = get_outscraper_key(db)
        if not api_key:
            _err("Outscraper API key is not configured (set OUTSCRAPER_API_KEY in .env or Settings → API Keys).")
            return 2
        region = args.region or region_for(args.country)
        campaign = _get_or_create_campaign(db, args.campaign, args.country) if args.campaign else None
        campaign_id = campaign.id if campaign else None

        index = load_index(db)
        seen: set[str] = set()
        new_leads: list[Lead] = []
        per_query: list[dict[str, Any]] = []
        raw_total = existing_total = 0

        for city in args.city:
            for category in args.category:
                query = f"{category} {city} {args.country}".strip()
                _err(f"→ Outscraper: '{query}' (limit {args.limit}, region {region or 'none'})")
                try:
                    rows = search_places(api_key, query=query, limit=args.limit, region=region, enrich_contacts=not args.no_enrich)
                except Exception as exc:  # keep going; report the failure
                    _err(f"  ✗ failed: {exc}")
                    per_query.append({"query": query, "error": str(exc)})
                    continue
                raw_total += len(rows)
                n_new = n_existing = n_dupe = 0
                for row in rows:
                    key = row.get("place_id") or row.get("normalized_website") or row.get("normalized_name_city")
                    if not key or key in seen:
                        n_dupe += 1
                        continue
                    seen.add(key)
                    lead, kind = upsert_discovered(db, row, campaign_id, index=index)
                    if kind == "new":
                        n_new += 1
                        new_leads.append(lead)
                    else:
                        n_existing += 1
                existing_total += n_existing
                if args.dry_run:
                    db.flush()
                else:
                    db.commit()
                per_query.append({"query": query, "results": len(rows), "new": n_new, "existing": n_existing, "duplicates_in_run": n_dupe})
                _err(f"  ✓ {len(rows)} results: {n_new} new, {n_existing} already in DB, {n_dupe} duplicate in this run")

        summary: dict[str, Any] = {
            "dry_run": args.dry_run,
            "region": region,
            "campaign": {"id": str(campaign_id), "name": campaign.name} if campaign else None,
            "raw_results": raw_total,
            "new_leads": len(new_leads),
            "existing_leads": existing_total,
            "queries": per_query,
        }
        if args.dry_run:
            summary["preview"] = [_row(lead) for lead in new_leads]
            db.rollback()
        else:
            if campaign:
                campaign.last_run_at = datetime.now(timezone.utc)
                db.commit()
            summary["directory"] = refresh_directory(db)
            log_event(
                db,
                type="outscraper",
                action="cli_find",
                message=f"CLI find: {len(new_leads)} new / {existing_total} existing from {len(per_query)} queries",
                status="success",
                campaign_id=campaign_id,
            )
            summary["new_lead_ids"] = [str(lead.id) for lead in new_leads]
        print(json.dumps(summary, indent=2, default=str))
        failed = [q for q in per_query if "error" in q]
        return 1 if failed and len(failed) == len(per_query) else 0
    finally:
        db.close()


def _row(lead: Lead) -> dict[str, Any]:
    from .services.directory import classify_lead

    classify_lead(lead)
    data = lead_to_dict(lead) | {"accommodation_type": lead.accommodation_type, "gender": lead.gender, "mobile": lead.mobile}
    return {field: data.get(field) for field in PREVIEW_FIELDS}


def cmd_list(args: argparse.Namespace) -> int:
    db = SessionLocal()
    try:
        filters = {
            "country": args.country, "city": args.city, "type": args.type, "gender": args.gender,
            "tier": args.size, "contact": args.contact, "search": args.search,
        }
        operators = query_directory(db, filters)["operators"]
        shown = operators[: args.limit]
        if args.format == "json":
            if not args.listings:
                shown = [{k: v for k, v in op.items() if k not in {"listings", "matched_ids"}} for op in shown]
            print(json.dumps({"total_operators": len(operators), "count": len(shown), "items": shown}, indent=2, default=str))
        elif args.format == "csv":
            writer = csv.writer(sys.stdout)
            writer.writerow(["Operator", "Properties", "Size", "Type", "Gender", "Cities", "Country", "Mobile", "Email", "Phone", "Website"])
            for op in shown:
                writer.writerow([op["name"], op["property_count"], op["tier"], ", ".join(op["types"]), ", ".join(op["genders"]),
                                 ", ".join(op["cities"]), op["country"], op["mobile"], op["email"], op["phone"], op["website"]])
        else:
            for op in shown:
                print(f"{op['property_count']:>3}  {op['tier']:<8} {op['name'][:34]:<34} {', '.join(op['types'])[:16]:<16} "
                      f"{', '.join(op['genders'])[:14]:<14} {', '.join(op['cities'])[:16]:<16} {op['mobile'] or '-':<16} {op['email'] or '-'}")
            _err(f"{len(shown)} of {len(operators)} operators")
        return 0
    finally:
        db.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="leads", description="Find leads with Outscraper and store them in the Lead Engine database.")
    sub = parser.add_subparsers(dest="command", required=True)

    find = sub.add_parser("find", help="Search Google Maps via Outscraper and save results to the DB")
    find.add_argument("--category", "-c", action="append", required=True, help="Search term, e.g. 'Hostel'. Repeatable.")
    find.add_argument("--city", action="append", required=True, help="City to search. Repeatable.")
    find.add_argument("--country", default="United Kingdom", help="Country appended to the query and used for region bias.")
    find.add_argument("--limit", type=int, default=20, help="Max results per category×city query (default 20).")
    find.add_argument("--region", help="Override the Google region code (e.g. gb, us, ae).")
    find.add_argument("--campaign", help="Tag new leads with this campaign name (created if missing) so they group in the UI.")
    find.add_argument("--dry-run", action="store_true", help="Call Outscraper and preview, but don't write to the DB. Still uses credits.")
    find.add_argument("--no-enrich", action="store_true", help="Skip the Emails & Contacts enrichment (cheaper, but usually no email).")
    find.set_defaults(func=cmd_find)

    lst = sub.add_parser("list", help="Read leads from the DB, grouped by operator and ranked by number of properties")
    lst.add_argument("--country", help="e.g. 'United Kingdom', 'Pakistan'")
    lst.add_argument("--city")
    lst.add_argument("--type", choices=ACCOMMODATION_TYPES + [OTHER_TYPE])
    lst.add_argument("--gender", choices=GENDERS + [UNKNOWN_GENDER])
    lst.add_argument("--size", choices=TIERS, help="Low = 1 property, Medium = 2–3, High = 4–5, Premium = 6+")
    lst.add_argument("--contact", choices=["both", "mobile", "email"], help="Only operators with this contact info")
    lst.add_argument("--search", help="Match name, website, email, phone or address")
    lst.add_argument("--limit", type=int, default=50)
    lst.add_argument("--listings", action="store_true", help="JSON only: include every property listing per operator")
    lst.add_argument("--format", choices=["json", "csv", "table"], default="json")
    lst.set_defaults(func=cmd_list)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if getattr(args, "limit", 1) < 1:
        _err("--limit must be at least 1")
        return 2
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
