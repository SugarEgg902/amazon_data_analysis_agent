# backend/main.py
import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from backend.scheduler import start_scheduler
from backend.routers import (meta, overview, brands, products, compare, trends,
                             anomalies, reports, sales_analysis, search)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
scheduler = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global scheduler
    scheduler = start_scheduler()
    yield
    if scheduler:
        scheduler.shutdown()


app = FastAPI(title="Amazon Analytics", lifespan=lifespan)

for r in (meta, overview, brands, products, compare, trends,
          anomalies, reports, sales_analysis, search):
    app.include_router(r.router, prefix="/api")

STATIC_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
if os.path.exists(STATIC_DIR):
    app.mount("/assets", StaticFiles(directory=os.path.join(STATIC_DIR, "assets")), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        return FileResponse(os.path.join(STATIC_DIR, "index.html"))
