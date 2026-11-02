from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from ..models import Campaign, CampaignSearch, Job, Lead
from .claude import QualificationError, qualify_leads
from .directory import refresh_directory
from .grouping import group_companies
from .leads import load_index, upsert_discovered
from .logging_service import append_job_log, log_event
from .outscraper import region_for, search_places
from .research import research_promising
from .scoring import apply_derived_fields
from .settings_service import get_anthropic_key, get_claude_model, get_outscraper_key, get_value


class JobCancelled(RuntimeError):
    pass


def default_categories() -> list[dict[str, Any]]:
    return [
        {"category": "Hostel", "result_limit": 30},
        {"category": "Student Accommodation", "result_limit": 40},
        {"category": "HMO", "result_limit": 30},
        {"category": "Co-living", "result_limit": 20},
        {"category": "Guest House", "result_limit": 20},
        {"category": "Boarding House", "result_limit": 10},
    ]


def replace_searches(db: Session, campaign: Campaign, cities: list[str], categories: list[dict[str, Any]]) -> None:
    campaign.searches.clear()
    db.flush()
    for city in cities:
        city = city.strip()
        if not city:
            continue
        for item in categories:
            category = str(item.get("category") or item.get("name") or "").strip()
            if not category:
                continue
            campaign.searches.append(
                CampaignSearch(
                    city=city,
                    category=category,
                    result_limit=int(item.get("result_limit") or item.get("limit") or 20),
                )
            )


def campaign_to_dict(campaign: Campaign) -> dict[str, Any]:
    return {
        "id": str(campaign.id),
        "name": campaign.name,
        "market": campaign.market,
        "country": campaign.country,
        "status": campaign.status,
        "last_run_at": campaign.last_run_at.isoformat() if campaign.last_run_at else None,
        "created_at": campaign.created_at.isoformat() if campaign.created_at else None,
        "searches": [
            {
                "id": str(item.id),
                "city": item.city,
                "category": item.category,
                "result_limit": item.result_limit,
                "status": item.status,
                "results_count": item.results_count,
                "query_text": item.query_text,
                "a_plus_count": item.a_plus_count,
                "a_count": item.a_count,
                "b_count": item.b_count,
                "c_count": item.c_count,
                "contactable_count": item.contactable_count,
                "quality_score": item.quality_score,
            }
            for item in campaign.searches
        ],
        "cities": sorted({item.city for item in campaign.searches}),
        "categories": _unique_categories(campaign.searches),
    }


def _unique_categories(searches: list[CampaignSearch]) -> list[dict[str, Any]]:
    seen: dict[str, int] = {}
    for item in searches:
        seen[item.category] = item.result_limit
    return [{"category": name, "result_limit": limit} for name, limit in seen.items()]


def _refresh_search_quality(db: Session, campaign: Campaign) -> None:
    for search in campaign.searches:
        leads = (
            db.query(Lead)
            .filter(
                Lead.campaign_id == campaign.id,
                Lead.city.ilike(search.city),
                Lead.query.ilike(f"%{search.category}%"),
            )
            .all()
        )
        if not leads:
            leads = (
                db.query(Lead)
                .filter(Lead.campaign_id == campaign.id, Lead.property_type == search.category, Lead.city.ilike(search.city))
                .all()
            )
        if not leads:
            continue
        search.a_plus_count = sum(1 for lead in leads if lead.priority == "A+")
        search.a_count = sum(1 for lead in leads if lead.priority == "A")
        search.b_count = sum(1 for lead in leads if lead.priority == "B")
        search.c_count = sum(1 for lead in leads if lead.priority == "C")
        search.contactable_count = sum(1 for lead in leads if (lead.contactability_score or 0) >= 50)
        reviewed = search.a_plus_count + search.a_count + search.b_count + search.c_count
        search.quality_score = round(((search.a_plus_count + search.a_count) / reviewed) * 100) if reviewed else 0
        db.add(search)
    db.commit()


def enqueue_campaign_run(db: Session, campaign: Campaign, user_id: UUID | None) -> Job:
    job = Job(
        type="campaign_run",
        status="queued",
        campaign_id=campaign.id,
        created_by=user_id,
        progress=_initial_progress(campaign),
        logs=[],
        result={},
    )
    campaign.status = "queued"
    db.add(job)
    db.add(campaign)
    db.commit()
    db.refresh(job)
    log_event(
        db,
        type="campaign",
        action="queued",
        message=f"Campaign queued: {campaign.name}",
        campaign_id=campaign.id,
        job_id=job.id,
    )
    return job


def _initial_progress(campaign: Campaign) -> dict[str, Any]:
    steps = [{"id": "prepare", "name": "Preparing searches", "status": "waiting", "detail": ""}]
    for search in campaign.searches:
        steps.append(
            {
                "id": str(search.id),
                "name": f"{search.category} · {search.city}",
                "status": "waiting",
                "detail": "",
            }
        )
    steps.append({"id": "qualify", "name": "Claude Qualification", "status": "waiting", "detail": ""})
    return {
        "phase": "queued",
        "steps": steps,
        "progress_current": 0,
        "progress_total": sum(item.result_limit for item in campaign.searches) or 1,
        "raw_results": 0,
        "unique_results": 0,
        "existing_leads": 0,
        "new_leads": 0,
        "qualification": {"current": 0, "total": 0, "a_plus": 0, "a": 0, "b": 0, "c": 0},
    }


def _set_step(progress: dict[str, Any], step_id: str, status: str, detail: str = "") -> None:
    for step in progress["steps"]:
        if step["id"] == step_id:
            step["status"] = status
            if detail:
                step["detail"] = detail


def run_campaign_job(db: Session, job: Job) -> None:
    campaign = db.query(Campaign).filter(Campaign.id == job.campaign_id).first()
    if not campaign:
        raise RuntimeError("Campaign not found")

    def cancelled() -> bool:
        db.refresh(job)
        return bool(job.cancel_requested)

    def save_progress() -> None:
        job.progress = dict(job.progress)
        db.add(job)
        db.commit()
        db.refresh(job)

    campaign.status = "running"
    campaign.last_run_at = datetime.now(timezone.utc)
    job.status = "running"
    job.started_at = datetime.now(timezone.utc)
    progress = job.progress or _initial_progress(campaign)
    progress["phase"] = "preparing"
    _set_step(progress, "prepare", "running")
    job.progress = progress
    db.add(job)
    db.add(campaign)
    db.commit()
    append_job_log(db, job, "Outscraper search started")
    log_event(db, type="outscraper", action="started", message="Outscraper search started", campaign_id=campaign.id, job_id=job.id)

    api_key = get_outscraper_key(db)
    if not api_key:
        raise RuntimeError("Outscraper API key is not configured")

    _set_step(progress, "prepare", "done")
    progress["phase"] = "searching"
    save_progress()

    raw_rows: list[dict[str, Any]] = []
    current = 0
    for search in campaign.searches:
        if cancelled():
            raise JobCancelled("Campaign cancelled")
        _set_step(progress, str(search.id), "running", "Searching...")
        save_progress()
        query = f"{search.category} {search.city} {campaign.country}"
        search.query_text = query
        try:
            rows = search_places(api_key, query=query, limit=search.result_limit, region=region_for(campaign.country))
        except Exception as exc:
            search.status = "failed"
            search.results_count = 0
            _set_step(progress, str(search.id), "failed", str(exc))
            append_job_log(db, job, f"Outscraper failed for {query}: {exc}", "error")
            save_progress()
            continue
        search.status = "completed"
        search.results_count = len(rows)
        raw_rows.extend(rows)
        current += search.result_limit
        progress["progress_current"] = current
        progress["raw_results"] = len(raw_rows)
        _set_step(progress, str(search.id), "done", f"{len(rows)} results")
        db.add(search)
        save_progress()

    append_job_log(db, job, f"Outscraper completed with {len(raw_rows)} raw results")
    log_event(db, type="outscraper", action="completed", message=f"Outscraper completed ({len(raw_rows)} raw results)", campaign_id=campaign.id, job_id=job.id, status="success")

    seen: set[str] = set()
    unique_rows: list[dict[str, Any]] = []
    for row in raw_rows:
        key = row.get("place_id") or row.get("normalized_website") or row.get("normalized_name_city")
        if not key or key in seen:
            continue
        seen.add(key)
        unique_rows.append(row)

    existing_count = 0
    new_leads: list[Lead] = []
    index = load_index(db)
    for row in unique_rows:
        if cancelled():
            raise JobCancelled("Campaign cancelled")
        lead, kind = upsert_discovered(db, row, campaign.id, index=index)
        if kind == "existing":
            existing_count += 1
        else:
            new_leads.append(lead)
    db.commit()

    progress["unique_results"] = len(unique_rows)
    progress["existing_leads"] = existing_count
    progress["new_leads"] = len(new_leads)
    progress["phase"] = "qualifying"
    save_progress()
    append_job_log(db, job, f"New leads discovered: {len(new_leads)} (existing {existing_count})")
    log_event(db, type="leads", action="discovered", message=f"{len(new_leads)} new leads discovered", campaign_id=campaign.id, job_id=job.id)

    to_qualify = [lead for lead in new_leads if not lead.priority]
    progress["qualification"]["total"] = len(to_qualify)
    _set_step(progress, "qualify", "running", f"0 / {len(to_qualify)}")
    save_progress()

    if to_qualify:
        anthropic_key = get_anthropic_key(db)
        if not anthropic_key:
            raise RuntimeError("Claude API key is not configured")
        model = get_claude_model(db)
        cfg = get_value(db, "qualification") or {}
        append_job_log(db, job, "Claude qualification started")
        log_event(db, type="claude", action="started", message="Claude qualification started", campaign_id=campaign.id, job_id=job.id)

        def on_progress(counts: dict[str, int]) -> None:
            progress["qualification"] = {
                "current": counts["total"],
                "total": len(to_qualify),
                "a_plus": counts.get("a_plus", 0),
                "a": counts["a"],
                "b": counts["b"],
                "c": counts["c"],
            }
            _set_step(progress, "qualify", "running", f"{counts['total']} / {len(to_qualify)}")
            job.progress = dict(progress)
            db.add(job)
            db.commit()

        try:
            counts = qualify_leads(
                db,
                to_qualify,
                api_key=anthropic_key,
                model=model,
                market=campaign.market,
                batch_size=int(cfg.get("batch_size", 10)),
                delay_seconds=float(cfg.get("batch_delay_seconds", 0.2)),
                campaign_id=campaign.id,
                job_id=job.id,
                should_cancel=cancelled,
                on_progress=on_progress,
            )
        except QualificationError as exc:
            append_job_log(db, job, f"Claude retry failed: {exc}", "error")
            log_event(db, type="claude", action="retry_failed", message=str(exc), status="error", campaign_id=campaign.id, job_id=job.id)
            raise
        progress["qualification"].update({
            "a_plus": counts.get("a_plus", 0),
            "a": counts["a"],
            "b": counts["b"],
            "c": counts["c"],
            "current": counts["total"],
        })
        _set_step(progress, "qualify", "done", f"{counts['total']} / {counts['total']}")
        append_job_log(db, job, f"Claude qualification completed A+={counts.get('a_plus', 0)} A={counts['a']} B={counts['b']} C={counts['c']}")
        group_companies(db)
        for lead in to_qualify:
            apply_derived_fields(lead, overwrite_scores=True, allow_priority_promote=False)
            db.add(lead)
        db.commit()
        research_promising(db, to_qualify)
        _refresh_search_quality(db, campaign)
    else:
        _set_step(progress, "qualify", "done", "No new unqualified leads")
        append_job_log(db, job, "No new leads required Claude qualification")
        group_companies(db)
        _refresh_search_quality(db, campaign)

    refresh_directory(db)
    progress["phase"] = "completed"
    job.progress = progress
    job.result = {
        "raw_results": progress["raw_results"],
        "unique_results": progress["unique_results"],
        "existing_leads": existing_count,
        "new_leads": len(new_leads),
        "qualification": progress["qualification"],
    }
    job.status = "completed"
    job.finished_at = datetime.now(timezone.utc)
    campaign.status = "completed"
    db.add(job)
    db.add(campaign)
    db.commit()
    log_event(db, type="campaign", action="completed", message=f"Campaign completed: {campaign.name}", status="success", campaign_id=campaign.id, job_id=job.id)
    append_job_log(db, job, "Campaign completed")
