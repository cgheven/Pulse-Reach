"""Country names, Google region codes and mobile-number rules."""
from __future__ import annotations

import re

# Country name -> Google Maps region code.
REGIONS = {
    "united kingdom": "gb", "uk": "gb", "great britain": "gb", "england": "gb", "scotland": "gb", "wales": "gb",
    "ireland": "ie", "united states": "us", "usa": "us", "us": "us", "canada": "ca", "australia": "au",
    "new zealand": "nz", "germany": "de", "france": "fr", "spain": "es", "portugal": "pt", "italy": "it",
    "netherlands": "nl", "belgium": "be", "united arab emirates": "ae", "uae": "ae", "saudi arabia": "sa",
    "pakistan": "pk", "india": "in", "south africa": "za", "singapore": "sg", "malaysia": "my",
}

# Long official names (as Outscraper returns them) -> short display names.
COUNTRY_ALIASES = {
    "united kingdom of great britain and northern ireland": "United Kingdom",
    "uk": "United Kingdom", "gb": "United Kingdom", "great britain": "United Kingdom", "england": "United Kingdom",
    "united states of america": "United States", "usa": "United States", "us": "United States",
    "uae": "United Arab Emirates", "ae": "United Arab Emirates",
    "pk": "Pakistan", "in": "India", "ie": "Ireland",
}

DIAL_CODES = {
    "gb": "44", "ie": "353", "pk": "92", "in": "91", "ae": "971", "sa": "966", "my": "60", "sg": "65",
    "za": "27", "au": "61", "nz": "64", "de": "49", "fr": "33", "es": "34", "it": "39", "nl": "31",
    "pt": "351", "be": "32", "us": "1", "ca": "1",
}

# National-number prefixes that indicate a mobile line. US/Canada can't be told apart, so they're omitted.
MOBILE_PREFIXES = {
    "44": ("71", "72", "73", "74", "75", "77", "78", "79"),
    "353": ("83", "84", "85", "86", "87", "88", "89"),
    "92": ("3",),
    "91": ("6", "7", "8", "9"),
    "971": ("5",),
    "966": ("5",),
    "60": ("1",),
    "65": ("8", "9"),
    "27": ("6", "7", "8"),
    "61": ("4",),
    "64": ("2",),
    "49": ("15", "16", "17"),
    "33": ("6", "7"),
    "34": ("6", "7"),
    "39": ("3",),
    "31": ("6",),
    "351": ("9",),
    "32": ("4",),
}


def region_for(country: str | None) -> str | None:
    value = (country or "").strip().lower()
    if len(value) == 2 and value.isalpha():
        return "gb" if value == "uk" else value
    return REGIONS.get(value) or REGIONS.get(display_country(value).lower())


def display_country(value: str | None) -> str:
    text = (value or "").strip()
    if not text:
        return ""
    return COUNTRY_ALIASES.get(text.lower(), text)


def to_e164_digits(raw: str | None, country: str | None = None) -> str:
    """Return the number as international digits without '+', or '' if it can't be parsed."""
    text = (raw or "").strip()
    if not text:
        return ""
    digits = re.sub(r"\D", "", text)
    if not digits:
        return ""
    if text.startswith("+"):
        return digits
    if digits.startswith("00"):
        return digits[2:]
    code = DIAL_CODES.get(region_for(country) or "")
    if not code:
        return digits
    if digits.startswith(code) and len(digits) > 10:
        return digits
    if digits.startswith("0"):
        return code + digits[1:]
    return code + digits


def is_mobile(e164_digits: str) -> bool:
    for size in (3, 2, 1):
        code = e164_digits[:size]
        prefixes = MOBILE_PREFIXES.get(code)
        if prefixes:
            national = e164_digits[size:]
            return len(national) >= 8 and national.startswith(prefixes)
    return False


def format_e164(e164_digits: str) -> str:
    return f"+{e164_digits}" if e164_digits else ""
