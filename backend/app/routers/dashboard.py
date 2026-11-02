from __future__ import annotations

from fastapi import APIRouter, Depends

from ..deps import get_current_user
from ..models import User
from ..services.cache import SWRCache
from ..services.dashboard import dashboard_payload

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

# Served from memory; refreshed in the background at most every 30 seconds.
_dashboard = SWRCache("dashboard", dashboard_payload, max_age=30)


@router.get("")
def get_dashboard(_: User = Depends(get_current_user)):
    return _dashboard.get()


def warm_dashboard_cache() -> None:
    _dashboard.get()
