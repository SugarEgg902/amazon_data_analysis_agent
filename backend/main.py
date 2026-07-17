# backend/main.py
import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
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

# 报告图表静态目录(钉钉推送嵌图从这里拉取)
CHART_DIR = os.path.join(os.path.dirname(__file__), "static", "report_charts")
os.makedirs(CHART_DIR, exist_ok=True)
app.mount("/static/report-charts", StaticFiles(directory=CHART_DIR), name="report_charts")

STATIC_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
if os.path.exists(STATIC_DIR):
    app.mount("/assets", StaticFiles(directory=os.path.join(STATIC_DIR, "assets")), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        # /api/* 未匹配到任何路由时返回 404 JSON,而不是 SPA 页面——
        # 否则前端拿到 HTML 会报"data is undefined",极难排查
        if full_path.startswith("api/"):
            return JSONResponse({"detail": "Not Found"}, status_code=404)
        # index.html 不缓存,避免浏览器用启发式缓存拿到旧页面
        return FileResponse(os.path.join(STATIC_DIR, "index.html"),
                            headers={"Cache-Control": "no-store"})
