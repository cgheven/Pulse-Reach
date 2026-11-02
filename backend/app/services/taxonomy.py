from __future__ import annotations

import re

from .normalize import normalize_name, normalize_url, safe_str

PROPERTY_TYPES = [
    "Hostel",
    "Student Accommodation",
    "Guest House",
    "Hotel",
    "Co-living",
    "HMO / Shared Accommodation",
    "Boarding House",
    "Other",
]

SEARCH_CATEGORIES = [
    "Hostel",
    "Student Accommodation",
    "HMO",
    "Co-living",
    "Guest House",
    "Boarding House",
    "Hotel",
    "Other",
]

GENERIC_DOMAINS = {
    "facebook.com",
    "instagram.com",
    "linkedin.com",
    "google.com",
    "maps.google.com",
    "booking.com",
    "airbnb.com",
    "hostelworld.com",
    "expedia.com",
    "tripadvisor.com",
    "yelp.com",
}

REJECT_HINTS = (
    "university",
    "college",
    "estate agent",
    "estate agency",
    "letting agent",
    "property consultant",
    "construction",
    "software",
    "charity",
    "council",
)


def normalize_domain(website: str) -> str:
    value = normalize_url(website)
    if not value:
        return ""
    host = value.split("/", 1)[0].lower().removeprefix("www.")
    return "" if host in GENERIC_DOMAINS else host


def normalize_phone(value: str) -> str:
    digits = re.sub(r"\D+", "", safe_str(value))
    if digits.startswith("00"):
        digits = digits[2:]
    if digits.startswith("44") and len(digits) > 10:
        digits = digits
    return digits


def normalize_email(value: str) -> str:
    return safe_str(value).lower()


def normalize_property_type(*parts: str) -> str:
    blob = " ".join(safe_str(part) for part in parts if part).lower()
    if not blob or blob in {"unknown", "other"}:
        return "Other"
    if any(term in blob for term in ("estate agent", "letting agent", "consultant", "construction", "software", "developer")):
        return "Other"
    if "hostel" in blob or "backpack" in blob:
        return "Hostel"
    if "student" in blob or "pbsa" in blob or "halls" in blob:
        return "Student Accommodation"
    if "co-living" in blob or "coliving" in blob or "co living" in blob or "serviced accommodation" in blob:
        return "Co-living"
    if "hmo" in blob or "house share" in blob or "shared accommodation" in blob or "house in multiple" in blob:
        return "HMO / Shared Accommodation"
    if "boarding" in blob:
        return "Boarding House"
    if "guest" in blob or "bed & breakfast" in blob or "bed and breakfast" in blob or "b&b" in blob:
        return "Guest House"
    if "hotel" in blob or "inn" in blob or "group accommodation" in blob:
        return "Hotel"
    if blob.title() in PROPERTY_TYPES:
        return blob.title()
    return "Other"


def property_bucket(min_count: int | None, raw: str) -> str:
    text = safe_str(raw).lower()
    if min_count and min_count >= 10:
        return "10+"
    if min_count and min_count >= 4:
        return "4–10"
    if min_count and min_count >= 2:
        return "2–3"
    if min_count == 1:
        return "1"
    if "10" in text or "portfolio" in text:
        return "10+"
    if any(token in text for token in ("4-10", "4–10", "5", "6", "7", "8", "9")):
        return "4–10"
    if any(token in text for token in ("2-3", "2–3", "2", "3")):
        return "2–3"
    if text in {"1", "one", "single"}:
        return "1"
    return "unknown"


def parse_property_bounds(raw: str) -> tuple[int | None, int | None]:
    text = safe_str(raw)
    numbers = [int(item) for item in re.findall(r"\d+", text)]
    if not numbers:
        return None, None
    if len(numbers) == 1:
        return numbers[0], numbers[0]
    return min(numbers), max(numbers)
