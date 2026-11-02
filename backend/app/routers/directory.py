from __future__ import annotations

import csv
from io import StringIO

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import User
from ..services.directory import query_directory, refresh_directory

router = APIRouter(prefix="/api/directory", tags=["directory"])


def _filters(country, city, type, gender, tier, contact, search) -> dict:
    return {"country": country, "city": city, "type": type, "gender": gender, "tier": tier, "contact": contact, "search": search}


@router.get("")
def list_directory(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    country: str | None = None,
    city: str | None = None,
    type: str | None = None,
    gender: str | None = None,
    tier: str | None = None,
    contact: str | None = None,
    search: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=200),
):
    data = query_directory(db, _filters(country, city, type, gender, tier, contact, search))
    operators = data["operators"]
    start = (page - 1) * page_size
    return {
        "items": operators[start : start + page_size],
        "total_operators": len(operators),
        "total_properties": sum(len(op["matched_ids"]) for op in operators),
        "page": page,
        "page_size": page_size,
        "facets": data["facets"],
    }


@router.get("/export")
def export_directory(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    country: str | None = None,
    city: str | None = None,
    type: str | None = None,
    gender: str | None = None,
    tier: str | None = None,
    contact: str | None = None,
    search: str | None = None,
):
    operators = query_directory(db, _filters(country, city, type, gender, tier, contact, search))["operators"]
    buffer = StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["Operator", "Properties", "Size", "Type", "Gender", "Cities", "Country", "Mobile", "Email", "Phone", "Website", "Rating", "Reviews", "Listings found"])
    for op in operators:
        writer.writerow([
            op["name"], op["property_count"], op["tier"], ", ".join(op["types"]), ", ".join(op["genders"]),
            ", ".join(op["cities"]), op["country"], op["mobile"], op["email"], op["phone"], op["website"],
            op["rating"] if op["rating"] is not None else "", op["reviews"], op["listings_found"],
        ])
    return Response(
        content="﻿" + buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="leads.csv"'},
    )


@router.post("/refresh")
def refresh(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return refresh_directory(db)
