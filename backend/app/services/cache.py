"""Tiny stale-while-revalidate cache.

The database is remote and its latency swings a lot, so read-heavy pages shouldn't wait on it. After the first
load, `get()` returns the cached value immediately; once it's older than `max_age` a background thread reloads it
for the next caller. `invalidate()` forces the next `get()` to load fresh data synchronously (use after writes).
"""
from __future__ import annotations

import threading
import time
from typing import Callable, Generic, TypeVar

from ..database import SessionLocal

T = TypeVar("T")


class SWRCache(Generic[T]):
    def __init__(self, name: str, loader: Callable[..., T], max_age: float = 30.0):
        self.name = name
        self._loader = loader
        self._max_age = max_age
        self._lock = threading.Lock()
        self._value: T | None = None
        self._loaded_at = 0.0
        self._version = 0
        self._refreshing = False

    def _load(self) -> T:
        db = SessionLocal()
        try:
            return self._loader(db)
        finally:
            db.close()

    def get(self) -> T:
        with self._lock:
            value, loaded_at, version = self._value, self._loaded_at, self._version
            stale = value is not None and time.monotonic() - loaded_at > self._max_age
            start_refresh = stale and not self._refreshing
            if start_refresh:
                self._refreshing = True
        if value is None:
            fresh = self._load()
            self._store(fresh, version)
            return fresh
        if start_refresh:
            threading.Thread(target=self._refresh, args=(version,), name=f"swr-{self.name}", daemon=True).start()
        return value

    def _refresh(self, version: int) -> None:
        try:
            self._store(self._load(), version)
        except Exception:
            pass  # keep serving the old value; the next stale read retries
        finally:
            with self._lock:
                self._refreshing = False

    def _store(self, value: T, version: int) -> None:
        with self._lock:
            if version == self._version:  # ignore loads that started before an invalidate()
                self._value, self._loaded_at = value, time.monotonic()

    def invalidate(self) -> None:
        with self._lock:
            self._value, self._loaded_at = None, 0.0
            self._version += 1
