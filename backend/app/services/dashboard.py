from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from collections import Counter, defaultdict

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models import Campaign, Lead
from .taxonomy import PROPERTY_TYPES


FUNNEL = ["new", "contacted", "replied", "trial", "customer", "lost"]


_COLUMNS = (
    Lead.campaign_id, Lead.priority, Lead.sales_status, Lead.sales_priority, Lead.contactability_score,
    Lead.decision_maker_name, Lead.multi_property_signal, Lead.research_status, Lead.next_followup_at,
    Lead.city, Lead.property_type, Lead.estimated_property_count, Lead.overall_score, Lead.created_at, Lead.qualified_at,
)


def _aware(value: datetime | None) -> datetime | None:
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _rows(db: Session, campaign_ids: list | None = None):
    query = db.query(*_COLUMNS)
    if campaign_ids is not None:
        query = query.filter(Lead.campaign_id.in_(campaign_ids))
    return query.all()


def dashboard_payload(db: Session) -> dict[str, Any]:
    """Everything is computed from one lightweight query: the DB is remote, so round trips dominate."""
    now = datetime.now(timezone.utc)
    week_ago = now - timedelta(days=7)
    start_today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end_today = start_today + timedelta(days=1)

    rows = _rows(db)
    total = len(rows)
    priority_counts = Counter(row.priority or "" for row in rows)
    status_counts = Counter(row.sales_status or "new" for row in rows)
    a_plus, a_leads, b_leads, rejected = (priority_counts.get(k, 0) for k in ("A+", "A", "B", "C"))
    followups = [_aware(row.next_followup_at) for row in rows if row.next_followup_at]

    city_counts = Counter(row.city or "Unknown" for row in rows)
    type_counts = Counter(row.property_type for row in rows)
    scale_counts = Counter(row.estimated_property_count for row in rows)
    scores = [row.overall_score for row in rows if row.overall_score is not None]

    campaigns = db.query(Campaign).order_by(Campaign.created_at.desc()).limit(6).all()
    quality = _quality_from_rows([row for row in rows if row.campaign_id in {c.id for c in campaigns}])

    return {
        "kpis": {
            "total_leads": total,
            "ai_reviewed": sum(1 for row in rows if row.priority and row.priority != ""),
            "a_plus_leads": a_plus,
            "a_leads": a_leads,
            "b_leads": b_leads,
            "rejected": rejected,
            "qualified": a_plus + a_leads + b_leads,
            "hot_prospects": sum(1 for row in rows if row.sales_priority == "Hot"),
            "contactable_leads": sum(1 for row in rows if (row.contactability_score or 0) >= 50),
            "decision_makers": sum(1 for row in rows if row.decision_maker_name),
            "multi_property": sum(1 for row in rows if row.multi_property_signal),
            "sales_ready": sum(1 for row in rows if row.research_status == "sales_ready"),
            "customers": status_counts.get("customer", 0),
            "new": status_counts.get("new", 0),
            "contacted": status_counts.get("contacted", 0),
            "replied": status_counts.get("replied", 0),
            "trials": status_counts.get("trial", 0),
            "lost": status_counts.get("lost", 0),
            "today_followups": sum(1 for due in followups if start_today <= due < end_today),
            "overdue_followups": sum(1 for due in followups if due < start_today),
            "new_leads_this_week": sum(1 for row in rows if row.created_at and _aware(row.created_at) >= week_ago),
            "new_qualified_this_week": sum(
                1 for row in rows if row.qualified_at and _aware(row.qualified_at) >= week_ago and row.priority in {"A+", "A", "B"}
            ),
        },
        "charts": {
            "by_city": [{"name": name, "value": value} for name, value in city_counts.most_common(8)],
            "by_property_type": [{"name": name, "value": type_counts.get(name, 0)} for name in PROPERTY_TYPES],
            "by_score": [
                {"name": "80–100", "value": sum(1 for v in scores if v >= 80)},
                {"name": "65–79", "value": sum(1 for v in scores if 65 <= v < 80)},
                {"name": "40–64", "value": sum(1 for v in scores if 40 <= v < 65)},
                {"name": "0–39", "value": sum(1 for v in scores if v < 40)},
            ],
            "by_scale": [{"name": label, "value": scale_counts.get(label, 0)} for label in ("unknown", "1", "2–3", "4–10", "10+")],
            "funnel": [{"name": status.title(), "value": status_counts.get(status, 0)} for status in FUNNEL],
            "campaign_quality": [quality.get(c.id, _quality([])) | {"name": c.name, "id": str(c.id)} for c in campaigns],
            "query_performance": _query_performance(rows),
        },
    }


def _quality(rows: list) -> dict[str, Any]:
    total = len(rows)
    counts = Counter(row.priority for row in rows)
    a_plus, a_leads, b_leads, c_leads = (counts.get(k, 0) for k in ("A+", "A", "B", "C"))
    reviewed = a_plus + a_leads + b_leads + c_leads
    contactable = sum(1 for row in rows if (row.contactability_score or 0) >= 50)
    multi = sum(1 for row in rows if row.multi_property_signal)
    hot = sum(1 for row in rows if row.sales_priority == "Hot")
    quality = round(((a_plus + a_leads) / reviewed) * 100) if reviewed else 0
    return {
        "total": total,
        "unique": total,
        "ai_reviewed": reviewed,
        "a_plus": a_plus,
        "a": a_leads,
        "b": b_leads,
        "c": c_leads,
        "hot": hot,
        "contactable": contactable,
        "multi_property": multi,
        "quality_score": quality,
        "a_plus_rate": round((a_plus / reviewed) * 100) if reviewed else 0,
        "aa_plus_rate": quality,
        "contactability_rate": round((contactable / total) * 100) if total else 0,
        "multi_property_rate": round((multi / total) * 100) if total else 0,
        "ab_rate": round(((a_plus + a_leads + b_leads) / reviewed) * 100) if reviewed else 0,
    }


def _quality_from_rows(rows: list) -> dict[Any, dict[str, Any]]:
    grouped: dict[Any, list] = defaultdict(list)
    for row in rows:
        grouped[row.campaign_id].append(row)
    return {campaign_id: _quality(items) for campaign_id, items in grouped.items()}


def campaign_quality_map(db: Session, campaign_ids: list) -> dict[Any, dict[str, Any]]:
    """Quality stats for many campaigns in one query (instead of ~9 queries per campaign)."""
    if not campaign_ids:
        return {}
    found = _quality_from_rows(_rows(db, campaign_ids))
    return {campaign_id: found.get(campaign_id, _quality([])) for campaign_id in campaign_ids}


def campaign_quality(db: Session, campaign_id) -> dict[str, Any]:
    return campaign_quality_map(db, [campaign_id])[campaign_id]


def _query_performance(rows: list) -> list[dict[str, Any]]:
    buckets: dict[tuple[str, str], dict[str, int]] = {}
    for row in rows:
        if not row.property_type:
            continue
        key = (row.city or "Unknown", row.property_type or "Other")
        item = buckets.setdefault(key, {"total": 0, "a_plus": 0, "a": 0, "b": 0, "c": 0})
        item["total"] += 1
        mapped = {"A+": "a_plus", "A": "a", "B": "b", "C": "c"}.get(row.priority)
        if mapped:
            item[mapped] += 1
    ranked = []
    for (city, category), item in buckets.items():
        reviewed = item["a_plus"] + item["a"] + item["b"] + item["c"]
        ranked.append(
            {
                "city": city,
                "category": category,
                "query": f"{city} + {category}",
                "total": item["total"],
                "a_plus": item["a_plus"],
                "a": item["a"],
                "b": item["b"],
                "c": item["c"],
                "aa_plus_rate": round(((item["a_plus"] + item["a"]) / reviewed) * 100) if reviewed else 0,
            }
        )
    ranked.sort(key=lambda row: (-row["aa_plus_rate"], -row["total"]))
    return ranked[:12]
