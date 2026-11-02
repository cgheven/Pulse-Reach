from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import urlparse


def safe_str(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return ", ".join(str(x) for x in value)
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False)
    return str(value).strip()


def parse_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def parse_bool_str(value: Any) -> str:
    text = safe_str(value).lower()
    if text in {"true", "1", "yes"}:
        return "true"
    if text in {"false", "0", "no"}:
        return "false"
    return text


def normalize_url(value: str) -> str:
    value = safe_str(value)
    if not value:
        return ""
    if not re.match(r"^https?://", value, re.I):
        value = "https://" + value
    try:
        parsed = urlparse(value)
        host = parsed.netloc.lower().removeprefix("www.")
        path = parsed.path.rstrip("/")
        return f"{host}{path}" if host else value.lower().rstrip("/")
    except Exception:
        return value.lower().rstrip("/")


def normalize_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", safe_str(value).lower()).strip()


def name_city_key(name: str, city: str) -> str:
    n = normalize_name(name)
    c = normalize_name(city)
    if not n:
        return ""
    return f"{n}|{c}"
