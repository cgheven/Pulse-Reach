from __future__ import annotations

from collections import defaultdict

from sqlalchemy.orm import Session

from ..models import Company, Lead, PropertyLocation
from .normalize import normalize_name
from .taxonomy import normalize_domain


def group_companies(db: Session) -> int:
    leads = db.query(Lead).all()
    by_domain: dict[str, list[Lead]] = defaultdict(list)
    by_name: dict[str, list[Lead]] = defaultdict(list)
    for lead in leads:
        domain = lead.normalized_domain or normalize_domain(lead.website)
        lead.normalized_domain = domain
        if domain:
            by_domain[domain].append(lead)
        key = _name_key(lead.name)
        if key:
            by_name[key].append(lead)

    created = 0
    seen: set[str] = set()
    for domain, group in by_domain.items():
        if len(group) < 2:
            continue
        created += _assign_group(db, group, domain=domain, status="Confirmed", names=[lead.name for lead in group])
        for lead in group:
            seen.add(str(lead.id))

    for key, group in by_name.items():
        cities = {lead.city.lower() for lead in group if lead.city}
        remaining = [lead for lead in group if str(lead.id) not in seen]
        if len(remaining) < 2 or len(cities) < 2:
            continue
        created += _assign_group(db, remaining, domain=remaining[0].normalized_domain, status="Probable", names=[lead.name for lead in remaining])
    db.commit()
    return created


def _assign_group(db: Session, leads: list[Lead], *, domain: str, status: str, names: list[str]) -> int:
    company = None
    if domain:
        company = db.query(Company).filter(Company.domain == domain).first()
    label = _company_name(names)
    if not company:
        company = Company(name=label, domain=domain or "", grouping_status=status, location_count=len(leads))
        db.add(company)
        db.flush()
    elif label and (len(label) < len(company.name) or company.name.count(" ") > label.count(" ")):
        company.name = label
    company.location_count = max(company.location_count, len(leads))
    company.grouping_status = status if status == "Confirmed" else company.grouping_status or status
    for lead in leads:
        if lead.qualification_source == "manual" and lead.company_id:
            continue
        lead.company_id = company.id
        lead.company_name = company.name
        lead.company_domain = company.domain
        lead.location_count = company.location_count
        lead.grouping_status = status
        if company.location_count >= 2:
            lead.multi_property_signal = True
            lead.multi_property_confidence = "High" if status == "Confirmed" else "Medium"
            if not lead.multi_property_evidence:
                lead.multi_property_evidence = f"{company.location_count} locations grouped as {status.lower()} same operator"
        _upsert_location(db, company.id, lead)
        db.add(lead)
    return 1


def _upsert_location(db: Session, company_id, lead: Lead) -> None:
    existing = db.query(PropertyLocation).filter(PropertyLocation.lead_id == lead.id).first()
    if existing:
        existing.company_id = company_id
        existing.name = lead.name
        existing.city = lead.city
        existing.address = lead.address
        existing.google_maps_url = lead.google_maps_url
        return
    db.add(
        PropertyLocation(
            company_id=company_id,
            lead_id=lead.id,
            name=lead.name,
            city=lead.city,
            address=lead.address,
            google_maps_url=lead.google_maps_url,
        )
    )


def _name_key(name: str) -> str:
    tokens = [token for token in normalize_name(name).split() if token not in {"the", "hostel", "hotel", "house", "london", "city"}]
    return " ".join(tokens[:2])


def _company_name(names: list[str]) -> str:
    if not names:
        return ""
    if len(names) == 1:
        cleaned = names[0].split("-")[0].split("|")[0].strip()
        return cleaned or names[0]
    token_sets = [set(_name_key(name).split()) for name in names if _name_key(name)]
    if not token_sets:
        return names[0]
    shared = set.intersection(*token_sets)
    ordered = [token for token in _name_key(names[0]).split() if token in shared]
    if ordered:
        return " ".join(ordered).title()
    cleaned = names[0].split("-")[0].split("|")[0].strip()
    return cleaned or names[0]
