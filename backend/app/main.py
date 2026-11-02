from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .database import SessionLocal, init_db, warm_pool
from .migrate import migrate_schema
from .routers import auth, campaigns, dashboard, directory, exports, followups, imports, jobs, leads, logs, pipeline
from .routers import settings as settings_router
from .seed import bootstrap
from .worker import start_worker, stop_worker


@asynccontextmanager
async def lifespan(_app: FastAPI):
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=2) as pool:
        warming = pool.submit(warm_pool, 4)  # open pooled connections while the schema/bootstrap work runs
        init_db()
        migrate_schema()
        db = SessionLocal()
        try:
            bootstrap(db)
        finally:
            db.close()
        warming.result()
    start_worker()
    # Fill the read caches in the background so the first page loads are instant too.
    import threading

    from .routers.dashboard import warm_dashboard_cache
    from .services.directory import warm_directory_cache

    for warm in (warm_directory_cache, warm_dashboard_cache):
        threading.Thread(target=lambda fn=warm: _quietly(fn), daemon=True).start()
    yield
    stop_worker()


config = get_settings()
app = FastAPI(title="PulseHub Lead Engine", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(campaigns.router)
app.include_router(imports.router)
app.include_router(exports.router)
app.include_router(leads.router)
app.include_router(followups.router)
app.include_router(jobs.router)
app.include_router(settings_router.router)
app.include_router(logs.router)
app.include_router(pipeline.router)
app.include_router(directory.router)


@app.get("/api/health")
def health():
    return {"ok": True, "name": "PulseHub Lead Engine"}


def _quietly(fn) -> None:
    try:
        fn()
    except Exception:
        pass
