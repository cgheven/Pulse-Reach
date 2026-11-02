from __future__ import annotations

import time
from threading import Lock

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from .config import get_settings
from .database import get_db
from .models import User
from .security import decode_token

# Every request is authenticated; caching the user for a short while saves a remote DB round trip per request.
_USER_TTL_SECONDS = 120
_user_cache: dict[str, tuple[float, User]] = {}
_lock = Lock()


def forget_user(user_id: str) -> None:
    with _lock:
        _user_cache.pop(str(user_id), None)


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    settings = get_settings()
    token = request.cookies.get(settings.cookie_name)
    if not token:
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:]
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = decode_token(token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid session")
    user_id = str(payload.get("sub") or "")
    now = time.monotonic()
    with _lock:
        cached = _user_cache.get(user_id)
    if cached and now - cached[0] < _USER_TTL_SECONDS:
        return cached[1]
    user = db.query(User).filter(User.id == user_id, User.is_active.is_(True)).first()
    if not user:
        forget_user(user_id)
        raise HTTPException(status_code=401, detail="User not found")
    db.expunge(user)
    with _lock:
        _user_cache[user_id] = (now, user)
    return user
