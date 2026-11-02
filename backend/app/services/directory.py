"""Clean lead directory: accommodation type, gender, contacts and operator size.

Everything here is deterministic and rule-based so results are explainable:
- accommodation_type: Dormitory | HMO | Hostel | PG | Guest House | Other
- gender:             Male | Female | Mixed | Unknown (listing doesn't say)
- property_count:     how many properties the operator runs (listings sharing a website domain
                      or phone number, or a larger research estimate when one exists)
- size_tier:          1 = Low, 2–3 = Medium, 4–5 = High, 6+ = Premium
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from types import SimpleNamespace
from typing import Any, Iterable

from sqlalchemy.orm import Session

from ..models import Lead
from .cache import SWRCache
from .geo import display_country, format_e164, is_mobile, to_e164_digits
from .taxonomy import normalize_domain

ACCOMMODATION_TYPES = ["Dormitory", "HMO", "Hostel", "PG", "Guest House"]
OTHER_TYPE = "Other"
GENDERS = ["Male", "Female", "Mixed"]
UNKNOWN_GENDER = "Unknown"
TIERS = ["Premium", "High", "Medium", "Low"]

_TYPE_RULES: list[tuple[str, re.Pattern[str]]] = [
    ("PG", re.compile(r"\bp\.?g\b|paying\s*guest", re.I)),
    ("HMO", re.compile(r"\bhmos?\b|multiple\s+occupation|shared\s+(house|housing|accommodation|flat)|\bco-?living\b|room\s*share", re.I)),
    ("Dormitory", re.compile(r"\bdorm(s|itory|itories)?\b|student\s+(halls?|accommodation|housing|residences?|living|lets?)|halls?\s+of\s+residence", re.I)),
    ("Hostel", re.compile(r"\bhostels?\b", re.I)),
    ("Guest House", re.compile(r"guest\s*-?\s*houses?|bed\s*(&|and)\s*breakfast|\bb\s*&\s*b\b", re.I)),
]

_FEMALE = re.compile(r"\b(girls?|ladies|women|womens|woman|females?)\b", re.I)
_MALE = re.compile(r"\b(boys?|gents|gentlemen|men|mens|males?)\b", re.I)
_MIXED = re.compile(r"\b(co-?ed|mixed|unisex)\b", re.I)

_EMAIL = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I)
_JUNK_EMAIL = ("example.com", "sentry.io", "wixpress.com", "domain.com", ".png", ".jpg", ".webp")


def tier_for(count: int) -> str:
    if count >= 6:
        return "Premium"
    if count >= 4:
        return "High"
    if count >= 2:
        return "Medium"
    return "Low"


def classify_type(name: str = "", category: str = "", subtypes: str = "") -> str:
    """Google's primary category is the strongest signal, then the business name, then secondary categories."""
    for text in (category, name, subtypes):
        if not text:
            continue
        for label, pattern in _TYPE_RULES:
            if pattern.search(text):
                return label
    return OTHER_TYPE


def classify_gender(name: str = "", category: str = "", subtypes: str = "") -> str:
    text = " ".join(part for part in (name, category, subtypes) if part)
    if _MIXED.search(text):
        return "Mixed"
    female, male = bool(_FEMALE.search(text)), bool(_MALE.search(text))
    if female and male:
        return "Mixed"
    if female:
        return "Female"
    if male:
        return "Male"
    return UNKNOWN_GENDER


def _values(raw: dict[str, Any], base: str) -> Iterable[str]:
    pattern = re.compile(rf"^{base}s?(_\d+)?$")
    for key, value in raw.items():
        if not pattern.match(str(key)) or value in (None, ""):
            continue
        items = value if isinstance(value, list) else str(value).split(",")
        for item in items:
            text = str(item).strip()
            if text:
                yield text


def extract_emails(raw: dict[str, Any] | None) -> list[str]:
    """Emails from an Outscraper row, including `domains_service` enrichment fields (email_1, email_2, …)."""
    found: list[str] = []
    for value in _values(raw or {}, "email"):
        for email in _EMAIL.findall(value):
            email = email.lower()
            if email not in found and not email.endswith(_JUNK_EMAIL):
                found.append(email)
    return found


def extract_phones(raw: dict[str, Any] | None) -> list[str]:
    seen: list[str] = []
    for value in _values(raw or {}, "phone"):
        if value not in seen:
            seen.append(value)
    return seen


def pick_mobile(phones: Iterable[str], country: str | None) -> str:
    for phone in phones:
        digits = to_e164_digits(phone, country)
        if digits and is_mobile(digits):
            return format_e164(digits)
    return ""


def _clean_name(name: str) -> str:
    text = re.split(r"\s+[-–|]\s+|\s*\(|,", name or "", maxsplit=1)[0].strip()
    return text or (name or "").strip()


_TRIVIAL = {"the", "a", "an", "hostel", "hostels", "hotel", "house", "guest", "student", "students", "accommodation", "hmo", "hmos", "pg", "dorm", "london", "city", "boys", "girls"}


def _operator_name(names: list[str], domain: str = "") -> str:
    """Brand shared by an operator's listings: common leading words, else a shared '- Brand' / '(Brand)' part, else the domain."""
    names = [name.strip() for name in names if name and name.strip()]
    if not names:
        return ""
    if len(names) == 1:
        return _clean_name(names[0])
    words = [name.split() for name in names]
    prefix: list[str] = []
    for column in zip(*words):
        if len({word.lower() for word in column}) != 1:
            break
        prefix.append(column[0])
    if any(word.lower().strip("'’s") not in _TRIVIAL for word in prefix):
        return " ".join(prefix).strip(" -–|,")
    parts = Counter()
    for name in names:
        for part in re.split(r"\s+[-–|]\s+|\(|\)", name)[1:]:
            part = part.strip(" ,")
            if part:
                parts[part] += 1
    if parts:
        part, hits = parts.most_common(1)[0]
        if hits >= 2:
            return part.upper() if part.isupper() else part
    if domain:
        label = domain.split(".")[0] if not domain.startswith(("uk.", "en.")) else domain.split(".")[1]
        return label.capitalize()
    counts = Counter(_clean_name(name) for name in names)
    return sorted(counts, key=lambda n: (-counts[n], len(n)))[0]


def classify_lead(lead: Lead) -> None:
    raw = lead.raw_json if isinstance(lead.raw_json, dict) else {}
    category = lead.source_category or lead.category or ""
    subtypes = lead.source_subtypes or lead.subtypes or ""
    lead.accommodation_type = classify_type(lead.name or "", category, subtypes)
    lead.gender = classify_gender(lead.name or "", category, subtypes)
    if not lead.email:
        emails = extract_emails(raw)
        if emails:
            lead.email = emails[0]
    phones = [lead.phone] + extract_phones(raw) if lead.phone else extract_phones(raw)
    lead.mobile = pick_mobile(phones, lead.country) or lead.mobile or ""


def refresh_directory(db: Session) -> dict[str, int]:
    """Re-classify every lead and regroup listings into operators. Idempotent; safe to run any time."""
    leads = db.query(Lead).all()
    parent = list(range(len(leads)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    owner: dict[str, int] = {}
    keys_by_lead: list[list[str]] = []
    for i, lead in enumerate(leads):
        classify_lead(lead)
        keys: list[str] = []
        domain = normalize_domain(lead.website or "")
        if domain:
            keys.append(f"d:{domain}")
        for phone in {lead.phone, lead.mobile}:
            digits = to_e164_digits(phone, lead.country)
            if len(digits) >= 9:
                keys.append(f"p:{digits}")
        keys_by_lead.append(keys)
        for key in keys:
            if key in owner:
                parent[find(i)] = find(owner[key])
            else:
                owner[key] = i

    groups: dict[int, list[int]] = defaultdict(list)
    for i in range(len(leads)):
        groups[find(i)].append(i)

    multi = 0
    for members in groups.values():
        group_leads = [leads[i] for i in members]
        keys = sorted({key for i in members for key in keys_by_lead[i]})
        operator_key = keys[0] if keys else f"l:{group_leads[0].id}"
        estimate = max((lead.estimated_property_count_min or 0) for lead in group_leads)
        count = max(len(group_leads), estimate, 1)
        domain = next((key[2:] for key in keys if key.startswith("d:")), "")
        name = _operator_name([lead.name for lead in group_leads], domain)
        if count > 1:
            multi += 1
        for lead in group_leads:
            lead.operator_key = operator_key
            lead.operator_name = name
            lead.property_count = count
            lead.size_tier = tier_for(count)
    db.commit()
    invalidate_directory_cache()
    return {"leads": len(leads), "operators": len(groups), "multi_property_operators": multi}


def directory_needs_refresh(db: Session) -> bool:
    return db.query(Lead.id).filter(Lead.accommodation_type.is_(None)).first() is not None


# ---------------------------------------------------------------- querying

def _listing(lead: Lead) -> dict[str, Any]:
    return {
        "id": str(lead.id),
        "name": lead.name,
        "city": lead.city or "",
        "country": display_country(lead.country),
        "address": lead.address or "",
        "type": lead.accommodation_type or OTHER_TYPE,
        "gender": lead.gender or UNKNOWN_GENDER,
        "phone": lead.phone or "",
        "mobile": lead.mobile or "",
        "email": lead.email or "",
        "website": lead.website or "",
        "maps_url": lead.google_maps_url or "",
        "rating": lead.rating,
        "reviews": lead.reviews,
    }


def _first(values: Iterable[str]) -> str:
    return next((value for value in values if value), "")


def _facet(values: Iterable[str], order: list[str] | None = None) -> list[dict[str, Any]]:
    counts = Counter(value for value in values if value)
    keys = [key for key in order if key in counts] + sorted(k for k in counts if k not in order) if order else sorted(counts)
    return [{"value": key, "count": counts[key]} for key in keys]


# ---------------------------------------------------------------- snapshot cache
# The DB is remote, so loading every lead on each filter click is slow. Keep a lightweight in-memory snapshot of
# just the columns the directory needs; it's served instantly and refreshed in the background every 15 seconds,
# so leads added by the CLI or another process show up shortly after.

_SNAPSHOT_COLUMNS = (
    Lead.id, Lead.name, Lead.city, Lead.country, Lead.address, Lead.accommodation_type, Lead.gender,
    Lead.phone, Lead.mobile, Lead.email, Lead.website, Lead.google_maps_url, Lead.rating, Lead.reviews,
    Lead.operator_key, Lead.operator_name, Lead.property_count,
)


def _load_rows(db: Session) -> list[SimpleNamespace]:
    return [SimpleNamespace(**row._mapping) for row in db.query(*_SNAPSHOT_COLUMNS).all()]


_rows_cache = SWRCache("directory", _load_rows, max_age=15)


def invalidate_directory_cache() -> None:
    _rows_cache.invalidate()


def warm_directory_cache() -> None:
    _rows_cache.get()


def query_directory(db: Session, filters: dict[str, Any]) -> dict[str, Any]:
    """Filter listings (country → city → type → gender → search), group into operators, then filter by size and contact."""
    country = (filters.get("country") or "").strip()
    city = (filters.get("city") or "").strip()
    acc_type = (filters.get("type") or "").strip()
    gender = (filters.get("gender") or "").strip()
    tier = (filters.get("tier") or "").strip()
    contact = (filters.get("contact") or "").strip()
    search = (filters.get("search") or "").strip().lower()

    all_leads = _rows_cache.get()
    by_operator: dict[str, list[Lead]] = defaultdict(list)
    for lead in all_leads:
        by_operator[lead.operator_key or f"l:{lead.id}"].append(lead)

    in_scope = [lead for lead in all_leads if (lead.accommodation_type == OTHER_TYPE) == (acc_type == OTHER_TYPE)]
    countries = _facet(display_country(lead.country) or "Unknown" for lead in in_scope)
    step = [lead for lead in in_scope if not country or (display_country(lead.country) or "Unknown") == country]
    cities = _facet(lead.city or "Unknown" for lead in step)
    step = [lead for lead in step if not city or (lead.city or "Unknown") == city]
    country_city = [lead for lead in all_leads if (not country or (display_country(lead.country) or "Unknown") == country) and (not city or (lead.city or "Unknown") == city)]
    types = _facet((lead.accommodation_type or OTHER_TYPE for lead in country_city), ACCOMMODATION_TYPES + [OTHER_TYPE])
    if acc_type and acc_type != OTHER_TYPE:
        step = [lead for lead in step if lead.accommodation_type == acc_type]
    genders = _facet((lead.gender or UNKNOWN_GENDER for lead in step), GENDERS + [UNKNOWN_GENDER])
    step = [lead for lead in step if not gender or (lead.gender or UNKNOWN_GENDER) == gender]
    if search:
        step = [
            lead for lead in step
            if search in " ".join(filter(None, [lead.name, lead.operator_name, lead.website, lead.email, lead.phone, lead.mobile, lead.address])).lower()
        ]

    matched: dict[str, list[Lead]] = defaultdict(list)
    for lead in step:
        matched[lead.operator_key or f"l:{lead.id}"].append(lead)

    operators = []
    for key, hits in matched.items():
        everyone = by_operator.get(key, hits)
        mobile = _first(lead.mobile for lead in everyone)
        email = _first(lead.email for lead in everyone)
        count = max((lead.property_count or 1) for lead in everyone)
        ratings = [lead.rating for lead in everyone if lead.rating is not None]
        operators.append({
            "key": key,
            "name": hits[0].operator_name or hits[0].name,
            "property_count": count,
            "listings_found": len(everyone),
            "tier": tier_for(count),
            "types": [t for t in ACCOMMODATION_TYPES + [OTHER_TYPE] if any((lead.accommodation_type or OTHER_TYPE) == t for lead in everyone)],
            "genders": [g for g in GENDERS + [UNKNOWN_GENDER] if any((lead.gender or UNKNOWN_GENDER) == g for lead in everyone)],
            "cities": sorted({lead.city for lead in everyone if lead.city}),
            "country": _first(display_country(lead.country) for lead in everyone),
            "mobile": mobile,
            "email": email,
            "phone": _first(lead.phone for lead in everyone),
            "website": _first(lead.website for lead in everyone),
            "rating": round(sum(ratings) / len(ratings), 1) if ratings else None,
            "reviews": sum(lead.reviews or 0 for lead in everyone),
            "has_mobile": bool(mobile),
            "has_email": bool(email),
            "matched_ids": [str(lead.id) for lead in hits],
            "listings": [_listing(lead) for lead in sorted(everyone, key=lambda l: (l.city or "", l.name or ""))],
        })

    tiers = _facet((op["tier"] for op in operators), TIERS)
    if tier:
        operators = [op for op in operators if op["tier"] == tier]
    contact_counts = {
        "both": sum(1 for op in operators if op["has_mobile"] and op["has_email"]),
        "mobile": sum(1 for op in operators if op["has_mobile"]),
        "email": sum(1 for op in operators if op["has_email"]),
        "any": len(operators),
    }
    if contact == "both":
        operators = [op for op in operators if op["has_mobile"] and op["has_email"]]
    elif contact == "mobile":
        operators = [op for op in operators if op["has_mobile"]]
    elif contact == "email":
        operators = [op for op in operators if op["has_email"]]

    operators.sort(key=lambda op: (-op["property_count"], -(op["has_mobile"] + op["has_email"]), -op["reviews"], op["name"].lower()))
    return {
        "operators": operators,
        "facets": {
            "countries": countries,
            "cities": cities,
            "types": types,
            "genders": genders,
            "tiers": tiers,
            "contact": contact_counts,
        },
        "total_properties": sum(len(hits) for hits in matched.values()),
    }
