from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from ..models import FollowUp, Lead, SalesActivity
from .normalize import name_city_key, normalize_url, parse_bool_str, parse_float, parse_int, safe_str
from .directory import extract_emails, extract_phones
from .scoring import apply_derived_fields, is_hot
from .taxonomy import PROPERTY_TYPES, normalize_domain, normalize_phone, normalize_property_type

CONTACT_FIELDS = (
    "website",
    "phone",
    "email",
    "address",
    "city",
    "postal_code",
    "country",
    "google_maps_url",
    "linkedin",
    "facebook",
    "instagram",
)

QUALIFICATION_FIELDS = (
    "relevant",
    "priority",
    "property_type",
    "estimated_property_count",
    "independent_operator",
    "ideal_customer",
    "claude_reason",
    "qualified_at",
)


class LeadIndex:
    def __init__(self, leads: list[Lead]):
        self.by_place: dict[str, Lead] = {}
        self.by_google: dict[str, Lead] = {}
        self.by_site: dict[str, Lead] = {}
        self.by_name_city: dict[str, Lead] = {}
        for lead in leads:
            self.add(lead)

    def add(self, lead: Lead) -> None:
        if lead.place_id:
            self.by_place[lead.place_id.lower()] = lead
        if lead.google_id:
            self.by_google[lead.google_id.lower()] = lead
        if lead.normalized_domain:
            self.by_site[lead.normalized_domain] = lead
        elif lead.normalized_website:
            self.by_site[lead.normalized_website] = lead
        if lead.normalized_name_city:
            self.by_name_city[lead.normalized_name_city] = lead

    def find(self, *, place_id: str, google_id: str, website: str, name: str, city: str) -> Lead | None:
        if place_id and place_id.lower() in self.by_place:
            return self.by_place[place_id.lower()]
        if google_id and google_id.lower() in self.by_google:
            return self.by_google[google_id.lower()]
        site = normalize_domain(website) or normalize_url(website)
        if site and site in self.by_site:
            return self.by_site[site]
        name_city = name_city_key(name, city)
        if name_city and name_city in self.by_name_city:
            return self.by_name_city[name_city]
        return None


def load_index(db: Session) -> LeadIndex:
    return LeadIndex(db.query(Lead).all())


def find_existing(db: Session, *, place_id: str, google_id: str, website: str, name: str, city: str) -> Lead | None:
    if place_id:
        found = db.query(Lead).filter(func.lower(Lead.place_id) == place_id.lower()).first()
        if found:
            return found
    if google_id:
        found = db.query(Lead).filter(func.lower(Lead.google_id) == google_id.lower()).first()
        if found:
            return found
    norm_site = normalize_url(website)
    if norm_site:
        found = db.query(Lead).filter(Lead.normalized_website == norm_site).first()
        if found:
            return found
    name_city = name_city_key(name, city)
    if name_city:
        found = db.query(Lead).filter(Lead.normalized_name_city == name_city).first()
        if found:
            return found
    return None


def apply_contact_updates(existing: Lead, incoming: dict[str, Any], *, overwrite_blank_only: bool = True) -> bool:
    changed = False
    for field in CONTACT_FIELDS:
        new_value = incoming.get(field)
        if new_value in (None, ""):
            continue
        current = getattr(existing, field)
        if overwrite_blank_only and current not in (None, ""):
            continue
        if current != new_value:
            setattr(existing, field, new_value)
            changed = True
    if incoming.get("rating") is not None and existing.rating is None:
        existing.rating = incoming["rating"]
        changed = True
    if incoming.get("reviews") is not None and existing.reviews is None:
        existing.reviews = incoming["reviews"]
        changed = True
    if incoming.get("business_status") and not existing.business_status:
        existing.business_status = incoming["business_status"]
        changed = True
    if incoming.get("query"):
        if incoming["query"] not in (existing.query or ""):
            existing.query = f"{existing.query}; {incoming['query']}".strip("; ") if existing.query else incoming["query"]
            changed = True
    existing.normalized_website = normalize_url(existing.website)
    existing.normalized_domain = normalize_domain(existing.website)
    existing.normalized_phone = normalize_phone(existing.phone)
    existing.normalized_name_city = name_city_key(existing.name, existing.city)
    return changed


def apply_qualification(existing: Lead, incoming: dict[str, Any], *, only_if_empty: bool = True) -> bool:
    if only_if_empty and existing.priority:
        return False
    changed = False
    for field in QUALIFICATION_FIELDS:
        if field == "qualified_at":
            continue
        new_value = incoming.get(field)
        if new_value in (None, ""):
            continue
        if getattr(existing, field) != new_value:
            setattr(existing, field, new_value)
            changed = True
    if incoming.get("priority") and not existing.qualified_at:
        existing.qualified_at = incoming.get("qualified_at") or datetime.now(timezone.utc)
        if existing.sales_status == "new":
            existing.sales_status = "qualified"
        changed = True
    return changed


def row_from_raw(raw: dict[str, Any], query: str = "") -> dict[str, Any]:
    place_id = safe_str(raw.get("place_id") or raw.get("google_id"))
    website = safe_str(raw.get("site") or raw.get("website"))
    name = safe_str(raw.get("name"))
    city = safe_str(raw.get("city"))
    return {
        "place_id": place_id,
        "google_id": safe_str(raw.get("google_id")),
        "name": name,
        "category": safe_str(raw.get("type") or raw.get("category")),
        "subtypes": safe_str(raw.get("subtypes")),
        "website": website,
        "phone": safe_str(raw.get("phone")) or next(iter(extract_phones(raw)), ""),
        "email": next(iter(extract_emails(raw)), ""),
        "address": safe_str(raw.get("full_address") or raw.get("address")),
        "city": city,
        "postal_code": safe_str(raw.get("postal_code")),
        "country": safe_str(raw.get("country")),
        "rating": parse_float(raw.get("rating")),
        "reviews": parse_int(raw.get("reviews")),
        "business_status": safe_str(raw.get("business_status")),
        "google_maps_url": safe_str(raw.get("location_link") or raw.get("google_maps_url")),
        "query": query or safe_str(raw.get("query")),
        "linkedin": safe_str(raw.get("linkedin")),
        "facebook": safe_str(raw.get("facebook")),
        "instagram": safe_str(raw.get("instagram")),
        "relevant": parse_bool_str(raw.get("relevant")),
        "priority": safe_str(raw.get("priority")).upper(),
        "property_type": safe_str(raw.get("property_type")),
        "estimated_property_count": safe_str(raw.get("estimated_property_count")),
        "independent_operator": parse_bool_str(raw.get("independent_operator")),
        "ideal_customer": parse_bool_str(raw.get("ideal_customer")),
        "claude_reason": safe_str(raw.get("claude_reason") or raw.get("reason")),
        "normalized_website": normalize_url(website),
        "normalized_domain": normalize_domain(website),
        "normalized_phone": normalize_phone(safe_str(raw.get("phone"))),
        "normalized_name_city": name_city_key(name, city),
        "source_category": safe_str(raw.get("type") or raw.get("category")),
        "source_subtypes": safe_str(raw.get("subtypes")),
        "raw_json": raw if isinstance(raw, dict) else None,
    }


def upsert_discovered(
    db: Session,
    payload: dict[str, Any],
    campaign_id: UUID | None = None,
    index: LeadIndex | None = None,
) -> tuple[Lead, str]:
    finder = index.find if index else None
    existing = (
        finder(
            place_id=payload.get("place_id", ""),
            google_id=payload.get("google_id", ""),
            website=payload.get("website", ""),
            name=payload.get("name", ""),
            city=payload.get("city", ""),
        )
        if finder
        else find_existing(
            db,
            place_id=payload.get("place_id", ""),
            google_id=payload.get("google_id", ""),
            website=payload.get("website", ""),
            name=payload.get("name", ""),
            city=payload.get("city", ""),
        )
    )
    if existing:
        apply_contact_updates(existing, payload, overwrite_blank_only=True)
        if campaign_id and not existing.campaign_id:
            existing.campaign_id = campaign_id
        db.add(existing)
        return existing, "existing"
    lead = Lead(
        **{k: v for k, v in payload.items() if hasattr(Lead, k)},
        campaign_id=campaign_id,
        sales_status="qualified" if payload.get("priority") else "new",
        qualified_at=datetime.now(timezone.utc) if payload.get("priority") else None,
    )
    if not lead.source_category:
        lead.source_category = lead.category
    apply_derived_fields(lead, overwrite_scores=True)
    db.add(lead)
    if index:
        index.add(lead)
    return lead, "new"


def record_activity(
    db: Session,
    lead: Lead,
    *,
    action: str,
    user_id: UUID | None,
    from_status: str = "",
    to_status: str = "",
    note: str = "",
) -> None:
    db.add(
        SalesActivity(
            lead_id=lead.id,
            user_id=user_id,
            action=action,
            from_status=from_status,
            to_status=to_status,
            note=note,
        )
    )


def apply_status_change(db: Session, lead: Lead, status: str, user_id: UUID | None, note: str = "") -> Lead:
    previous = lead.sales_status
    lead.sales_status = status
    if status in {"contacted", "replied", "trial", "customer"}:
        lead.last_contacted_at = datetime.now(timezone.utc)
    record_activity(db, lead, action=f"status:{status}", user_id=user_id, from_status=previous, to_status=status, note=note)
    db.add(lead)
    db.commit()
    db.refresh(lead)
    return lead


def lead_to_dict(lead: Lead) -> dict[str, Any]:
    return {
        "id": str(lead.id),
        "place_id": lead.place_id,
        "google_id": lead.google_id,
        "name": lead.name,
        "category": lead.category,
        "subtypes": lead.subtypes,
        "source_category": lead.source_category,
        "source_subtypes": lead.source_subtypes,
        "website": lead.website,
        "phone": lead.phone,
        "email": lead.email,
        "address": lead.address,
        "city": lead.city,
        "postal_code": lead.postal_code,
        "country": lead.country,
        "rating": lead.rating,
        "reviews": lead.reviews,
        "business_status": lead.business_status,
        "google_maps_url": lead.google_maps_url,
        "query": lead.query,
        "linkedin": lead.linkedin,
        "facebook": lead.facebook,
        "instagram": lead.instagram,
        "relevant": lead.relevant,
        "priority": lead.priority,
        "property_type": lead.property_type,
        "estimated_property_count": lead.estimated_property_count,
        "estimated_property_count_min": lead.estimated_property_count_min,
        "estimated_property_count_max": lead.estimated_property_count_max,
        "estimated_bed_count": lead.estimated_bed_count,
        "scale_confidence": lead.scale_confidence,
        "independent_operator": lead.independent_operator,
        "ideal_customer": lead.ideal_customer,
        "claude_reason": lead.claude_reason,
        "fit_summary": lead.fit_summary,
        "confidence": lead.confidence,
        "overall_score": lead.overall_score,
        "icp_score": lead.icp_score,
        "opportunity_score": lead.opportunity_score,
        "contactability_score": lead.contactability_score,
        "data_quality_score": lead.data_quality_score,
        "sales_priority": lead.sales_priority,
        "recommended_next_action": lead.recommended_next_action,
        "research_status": lead.research_status,
        "score_breakdown": lead.score_breakdown,
        "multi_property_signal": lead.multi_property_signal,
        "multi_property_confidence": lead.multi_property_confidence,
        "multi_property_evidence": lead.multi_property_evidence,
        "current_software": lead.current_software,
        "current_software_confidence": lead.current_software_confidence,
        "software_evidence": lead.software_evidence,
        "decision_maker_name": lead.decision_maker_name,
        "decision_maker_role": lead.decision_maker_role,
        "decision_maker_email": lead.decision_maker_email,
        "decision_maker_phone": lead.decision_maker_phone,
        "decision_maker_linkedin": lead.decision_maker_linkedin,
        "decision_maker_confidence": lead.decision_maker_confidence,
        "company_id": str(lead.company_id) if lead.company_id else None,
        "company_name": lead.company_name,
        "company_domain": lead.company_domain,
        "location_count": lead.location_count,
        "grouping_status": lead.grouping_status,
        "qualification_source": lead.qualification_source,
        "priority_source": lead.priority_source,
        "property_type_source": lead.property_type_source,
        "needs_review": lead.needs_review,
        "review_reason": lead.review_reason,
        "hot": is_hot(lead),
        "qualified_at": lead.qualified_at.isoformat() if lead.qualified_at else None,
        "sales_status": lead.sales_status,
        "assigned_to": str(lead.assigned_to) if lead.assigned_to else None,
        "last_contacted_at": lead.last_contacted_at.isoformat() if lead.last_contacted_at else None,
        "next_followup_at": lead.next_followup_at.isoformat() if lead.next_followup_at else None,
        "notes": lead.notes,
        "campaign_id": str(lead.campaign_id) if lead.campaign_id else None,
        "created_at": lead.created_at.isoformat() if lead.created_at else None,
        "updated_at": lead.updated_at.isoformat() if lead.updated_at else None,
    }


def apply_lead_filters(query, params: dict[str, Any]):
    view = (params.get("view") or "").lower()
    if params.get("sales_priority"):
        query = query.filter(Lead.sales_priority == params["sales_priority"])
    if params.get("priority"):
        query = query.filter(Lead.priority == params["priority"])
    if params.get("sales_status"):
        query = query.filter(Lead.sales_status == params["sales_status"])
    if params.get("property_type"):
        query = query.filter(Lead.property_type == params["property_type"])
    if params.get("city"):
        query = query.filter(Lead.city.ilike(params["city"]))
    if params.get("country"):
        query = query.filter(Lead.country.ilike(f"%{params['country']}%"))
    if params.get("campaign_id"):
        query = query.filter(Lead.campaign_id == params["campaign_id"])
    if params.get("qualification_status") == "reviewed":
        query = query.filter(Lead.priority != "")
    elif params.get("qualification_status") == "qualified":
        query = query.filter(Lead.priority.in_(["A+", "A", "B"]))
    elif params.get("qualification_status") == "unqualified":
        query = query.filter(or_(Lead.priority.is_(None), Lead.priority == ""))
    if params.get("min_score"):
        query = query.filter(Lead.overall_score >= int(params["min_score"]))
    if params.get("max_score"):
        query = query.filter(Lead.overall_score <= int(params["max_score"]))
    if params.get("has_email") == "true":
        query = query.filter(Lead.email != "")
    if params.get("has_phone") == "true":
        query = query.filter(Lead.phone != "")
    if params.get("has_website") == "true":
        query = query.filter(Lead.website != "")
    if params.get("has_decision_maker") == "true":
        query = query.filter(Lead.decision_maker_name != "")
    if params.get("multi_property") == "true" or view == "multi_property":
        query = query.filter(Lead.multi_property_signal.is_(True))
    if params.get("estimated_properties"):
        bucket = params["estimated_properties"]
        aliases = {
            "1": ["1"],
            "2-3": ["2-3", "2–3"],
            "4-10": ["4-10", "4–10"],
            "10+": ["10+"],
            "unknown": ["unknown", ""],
        }
        query = query.filter(Lead.estimated_property_count.in_(aliases.get(bucket, [bucket])))
    if params.get("current_software"):
        query = query.filter(Lead.current_software.ilike(f"%{params['current_software']}%"))
    if params.get("research_status"):
        query = query.filter(Lead.research_status == params["research_status"])
    if params.get("min_contactability"):
        query = query.filter(Lead.contactability_score >= int(params["min_contactability"]))
    if view == "hot":
        query = query.filter(or_(Lead.sales_priority.in_(["Hot", "High"]), Lead.priority.in_(["A+", "A"])))
    elif view == "contactable":
        query = query.filter(Lead.contactability_score >= 50)
    elif view == "scale_2_10":
        query = query.filter(Lead.estimated_property_count.in_(["2-3", "2–3", "4-10", "4–10"]))
    elif view == "missing_dm":
        query = query.filter(or_(Lead.decision_maker_name.is_(None), Lead.decision_maker_name == ""))
    elif view == "needs_review":
        query = query.filter(Lead.needs_review.is_(True))
    elif view == "needs_research":
        query = query.filter(Lead.research_status.in_(["not_researched", "ai_researched"]))
    elif view == "sales_ready":
        query = query.filter(Lead.research_status == "sales_ready")
    search = (params.get("search") or "").strip()
    if search:
        like = f"%{search}%"
        query = query.filter(
            or_(
                Lead.name.ilike(like),
                Lead.website.ilike(like),
                Lead.email.ilike(like),
                Lead.phone.ilike(like),
            )
        )
    return query


SORT_MAP = {
    "priority": Lead.priority,
    "rating": Lead.rating,
    "reviews": Lead.reviews,
    "date_added": Lead.created_at,
    "created": Lead.created_at,
    "updated": Lead.updated_at,
    "name": Lead.name,
    "overall_score": Lead.overall_score,
    "contactability": Lead.contactability_score,
    "opportunity": Lead.opportunity_score,
    "estimated_properties": Lead.estimated_property_count_min,
}


def sort_leads(query, sort: str = "date_added", direction: str = "desc"):
    column = SORT_MAP.get(sort, Lead.created_at)
    if sort in {"overall_score", "hot", "best"}:
        return query.order_by(
            Lead.overall_score.desc().nullslast(),
            Lead.opportunity_score.desc().nullslast(),
            Lead.contactability_score.desc().nullslast(),
        )
    if sort == "priority":
        order = func.nullif(Lead.priority, "")
        return query.order_by(order.asc() if direction == "asc" else order.desc(), Lead.reviews.desc().nullslast())
    return query.order_by(column.asc().nullslast() if direction == "asc" else column.desc().nullslast())
