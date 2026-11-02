from __future__ import annotations

import re
import time
from html import unescape
from urllib.error import URLError
from urllib.request import Request, urlopen

from sqlalchemy.orm import Session

from ..models import Lead, LeadEvidence

SOFTWARE_HINTS = (
    ("Cloudbeds", "cloudbeds"),
    ("Mews", "mews"),
    ("Guesty", "guesty"),
    ("Opera PMS", "opera pms"),
    ("Hostelworld booking", "hostelworld"),
    ("Booking.com", "booking.com"),
    ("Resident portal", "resident portal"),
    ("Tenant portal", "tenant portal"),
    ("Online application", "apply now"),
    ("PMS", " property management software"),
)

MULTI_HINTS = (
    "our properties",
    "our locations",
    "our houses",
    "our buildings",
    "portfolio",
    "multiple locations",
    "our sites",
)


def research_lead(db: Session, lead: Lead) -> None:
    if not lead.website:
        lead.website_research_status = "skipped"
        return
    if lead.website_research_status == "completed":
        return
    pages = _candidate_pages(lead.website)
    combined = ""
    used_url = pages[0] if pages else lead.website
    fetched = 0
    for url in pages:
        text = _fetch(url)
        fetched += 1
        if text:
            combined += " " + text
            used_url = url
            if len(combined) > 5000:
                break
        time.sleep(0.15)
    if not combined:
        lead.website_research_status = "failed"
        return
    lower = combined.lower()
    payload = lead.website_research_json or {}
    if any(term in lower for term in MULTI_HINTS):
        lead.multi_property_signal = True
        lead.multi_property_confidence = lead.multi_property_confidence or "Medium"
        lead.multi_property_evidence = lead.multi_property_evidence or "Website uses portfolio / multiple-location language"
        _add_evidence(db, lead, "multi_property", "website", "Website refers to multiple properties or locations.", used_url)
        payload["portfolio_language"] = True
    location_hits = len(re.findall(r"\b(london|manchester|leeds|birmingham|bristol|liverpool|edinburgh|glasgow)\b", lower))
    if location_hits >= 3 and not lead.multi_property_signal:
        lead.multi_property_signal = True
        lead.multi_property_confidence = "Low"
        lead.multi_property_evidence = lead.multi_property_evidence or "Website mentions several UK cities"
        _add_evidence(db, lead, "multi_property", "website", "Public pages mention several cities.", used_url)
    for label, hint in SOFTWARE_HINTS:
        if hint in lower and not lead.current_software:
            lead.current_software = label
            lead.current_software_confidence = "low"
            lead.software_evidence = f"Public page mentions '{hint.strip()}'"
            _add_evidence(db, lead, "software", "website", lead.software_evidence, used_url)
            payload["booking_system"] = label
            break
    if "apply now" in lower or "application" in lower:
        payload["direct_application"] = True
    emails = re.findall(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", combined, flags=re.I)
    public = [item for item in emails if not item.lower().endswith(("example.com", "sentry.io", "wixpress.com"))]
    if public and not lead.email:
        lead.email = public[0]
        _add_evidence(db, lead, "contact", "website", f"Public email found: {public[0]}", used_url)
    lead.website_research_status = "completed"
    payload.update({"pages": pages[:fetched], "chars": len(combined)})
    lead.website_research_json = payload
    db.add(lead)


def research_promising(db: Session, leads: list[Lead]) -> None:
    for lead in leads:
        grade = lead.priority
        score = lead.overall_score or 0
        if grade in {"A+", "A"} or (grade == "B" and score >= 55):
            try:
                research_lead(db, lead)
            except Exception:
                lead.website_research_status = "failed"
                db.add(lead)
    db.commit()


def _candidate_pages(website: str) -> list[str]:
    url = website if website.startswith("http") else f"https://{website}"
    url = url.rstrip("/")
    return [url, f"{url}/about", f"{url}/properties", f"{url}/locations", f"{url}/accommodation", f"{url}/contact"]


def _fetch(url: str) -> str:
    try:
        request = Request(url, headers={"User-Agent": "PulseHubLeadEngine/1.0"})
        with urlopen(request, timeout=8) as response:
            raw = response.read(120_000)
        html = raw.decode("utf-8", errors="ignore")
        text = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.I)
        text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.I)
        text = re.sub(r"<[^>]+>", " ", text)
        return unescape(re.sub(r"\s+", " ", text))[:8000]
    except (URLError, TimeoutError, ValueError, OSError):
        return ""


def _add_evidence(db: Session, lead: Lead, evidence_type: str, source: str, text: str, url: str) -> None:
    db.add(
        LeadEvidence(
            lead_id=lead.id,
            evidence_type=evidence_type,
            evidence_source=source,
            evidence_text=text,
            evidence_url=url,
        )
    )
