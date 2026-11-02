from __future__ import annotations

import csv
from io import StringIO
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import Campaign, ExportRecord, ImportRecord, Lead
from .leads import apply_contact_updates, apply_lead_filters, apply_qualification, load_index, row_from_raw
from .scoring import apply_derived_fields
from .normalize import name_city_key, normalize_url


def import_csv_text(db: Session, text: str, filename: str) -> ImportRecord:
    reader = csv.DictReader(StringIO(text))
    imported = updated = skipped = duplicates = errors = 0
    seen_keys: set[str] = set()
    index = load_index(db)
    for row in reader:
        try:
            payload = row_from_raw(row, row.get("query", ""))
            if not payload["name"] and not payload["place_id"]:
                skipped += 1
                continue
            key = payload["place_id"] or payload["normalized_website"] or payload["normalized_name_city"]
            if key and key in seen_keys:
                duplicates += 1
                continue
            if key:
                seen_keys.add(key)
            existing = index.find(
                place_id=payload["place_id"],
                google_id=payload["google_id"],
                website=payload["website"],
                name=payload["name"],
                city=payload["city"],
            )
            if existing:
                contact_changed = apply_contact_updates(existing, payload, overwrite_blank_only=True)
                qual_changed = apply_qualification(existing, payload, only_if_empty=True)
                if contact_changed or qual_changed:
                    db.add(existing)
                    updated += 1
                else:
                    duplicates += 1
                continue
            lead = Lead(
                **{k: v for k, v in payload.items() if hasattr(Lead, k)},
                sales_status="qualified" if payload.get("priority") else "new",
            )
            if payload.get("priority"):
                from datetime import datetime, timezone

                lead.qualified_at = datetime.now(timezone.utc)
            apply_derived_fields(lead, overwrite_scores=True)
            db.add(lead)
            index.add(lead)
            imported += 1
        except Exception:
            errors += 1
    db.flush()
    record = ImportRecord(
        filename=filename,
        imported=imported,
        updated=updated,
        skipped=skipped,
        duplicates=duplicates,
        errors=errors,
        status="completed",
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def import_existing_files(db: Session) -> list[ImportRecord]:
    data_dir = get_settings().data_dir
    results: list[ImportRecord] = []
    for name in ("raw_leads.csv", "qualified_leads.csv"):
        path = data_dir / name
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8-sig")
        results.append(import_csv_text(db, text, name))
    return results


def build_export(db: Session, filters: dict[str, Any], created_by: UUID | None = None) -> ExportRecord:
    query = apply_lead_filters(db.query(Lead), filters)
    if filters.get("lead_ids"):
        query = db.query(Lead).filter(Lead.id.in_(filters["lead_ids"]))
    preset = (filters.get("preset") or "").lower()
    if preset in {"a+", "export a+", "a+ leads"}:
        query = db.query(Lead).filter(Lead.priority == "A+")
    elif preset in {"a", "a leads", "export a"}:
        query = db.query(Lead).filter(Lead.priority == "A")
    elif preset in {"a+b", "export a+b"}:
        query = db.query(Lead).filter(Lead.priority.in_(["A+", "A", "B"]))
    elif preset in {"hot", "export hot"}:
        query = apply_lead_filters(db.query(Lead), {"view": "hot"})
    elif preset in {"trials", "trial"}:
        query = apply_lead_filters(db.query(Lead), {"sales_status": "trial"})
    elif preset in {"customers", "customer"}:
        query = apply_lead_filters(db.query(Lead), {"sales_status": "customer"})
    elif preset in {"contactable", "export contactable"}:
        query = apply_lead_filters(db.query(Lead), {"view": "contactable"})
    elif preset == "b leads":
        query = db.query(Lead).filter(Lead.priority == "B")
    elif preset == "new leads":
        query = apply_lead_filters(db.query(Lead), {**filters, "sales_status": "new"})
    elif preset in {"contacted", "replied", "trial", "customer"}:
        query = apply_lead_filters(db.query(Lead), {**filters, "sales_status": preset})
    rows = query.order_by(Lead.priority.asc(), Lead.reviews.desc().nullslast()).all()
    export_dir = get_settings().data_dir / "exports"
    export_dir.mkdir(parents=True, exist_ok=True)
    record = ExportRecord(filters=filters, status="running", created_by=created_by)
    db.add(record)
    db.commit()
    db.refresh(record)
    filename = f"leads-{record.id}.csv"
    path = export_dir / filename
    campaigns = {str(row.id): row.name for row in db.query(Campaign).all()}
    fieldnames = [
        "Business",
        "Property Type",
        "City",
        "Country",
        "Website",
        "Email",
        "Phone",
        "Decision Maker",
        "Role",
        "LinkedIn",
        "Estimated Properties",
        "Estimated Beds",
        "Overall Score",
        "ICP Score",
        "Opportunity Score",
        "Contactability Score",
        "Priority",
        "Fit Summary",
        "Current Software",
        "Campaign",
        "Sales Status",
        "Follow-up",
    ]
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for lead in rows:
            writer.writerow(
                {
                    "Business": lead.name,
                    "Property Type": lead.property_type,
                    "City": lead.city,
                    "Country": lead.country,
                    "Website": lead.website,
                    "Email": lead.email,
                    "Phone": lead.phone,
                    "Decision Maker": lead.decision_maker_name,
                    "Role": lead.decision_maker_role,
                    "LinkedIn": lead.decision_maker_linkedin or lead.linkedin,
                    "Estimated Properties": lead.estimated_property_count,
                    "Estimated Beds": lead.estimated_bed_count,
                    "Overall Score": lead.overall_score if lead.overall_score is not None else "",
                    "ICP Score": lead.icp_score if lead.icp_score is not None else "",
                    "Opportunity Score": lead.opportunity_score if lead.opportunity_score is not None else "",
                    "Contactability Score": lead.contactability_score if lead.contactability_score is not None else "",
                    "Priority": lead.priority,
                    "Fit Summary": lead.fit_summary or lead.claude_reason,
                    "Current Software": lead.current_software,
                    "Campaign": campaigns.get(str(lead.campaign_id), ""),
                    "Sales Status": lead.sales_status,
                    "Follow-up": lead.next_followup_at.isoformat() if lead.next_followup_at else "",
                }
            )
    record.filename = filename
    record.file_path = str(path)
    record.row_count = len(rows)
    record.status = "completed"
    db.add(record)
    db.commit()
    db.refresh(record)
    return record
