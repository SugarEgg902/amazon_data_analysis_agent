# backend/routers/sales_analysis.py
from fastapi import APIRouter, UploadFile, File, HTTPException, Query
from sqlalchemy import text
from backend.database import engine
from backend.models.schemas import ApiResponse
from backend.analysis.sales_analyzer import run_sales_analysis

router = APIRouter()

_MAX_BYTES = 20 * 1024 * 1024


@router.post("/sales-analysis/upload", response_model=ApiResponse)
async def upload(file: UploadFile = File(...)):
    name = file.filename or ""
    if not name.lower().endswith((".csv", ".xlsx", ".xls")):
        raise HTTPException(status_code=400, detail="仅支持 .csv/.xlsx/.xls 文件")
    data = await file.read()
    if len(data) > _MAX_BYTES:
        raise HTTPException(status_code=413, detail="文件超过 20MB 限制")
    try:
        result = run_sales_analysis(data, name)
    except ValueError as e:
        if str(e) == "no_numeric_columns":
            raise HTTPException(status_code=422, detail="未检测到数值列，无法生成分析")
        raise HTTPException(status_code=400, detail=str(e))
    return ApiResponse(data={**result, "filename": name})


@router.get("/sales-analysis/history", response_model=ApiResponse)
def history(page: int = Query(default=1, ge=1), size: int = Query(default=20, ge=1, le=100)):
    offset = (page - 1) * size
    with engine.connect() as conn:
        total = conn.execute(text("SELECT COUNT(*) FROM sales_analysis_reports")).scalar()
        rows = conn.execute(text("""
            SELECT id, filename, row_count, report_date, status
            FROM sales_analysis_reports ORDER BY created_at DESC
            LIMIT :limit OFFSET :offset
        """), {"limit": size, "offset": offset}).mappings().all()
    items = [{**dict(r), "report_date": str(r["report_date"])} for r in rows]
    return ApiResponse(data={"items": items, "total": total})


@router.get("/sales-analysis/reports/{report_id}", response_model=ApiResponse)
def get_report(report_id: int):
    with engine.connect() as conn:
        r = conn.execute(text("""
            SELECT id, filename, row_count, report_date, content, model, status, error_message
            FROM sales_analysis_reports WHERE id = :id
        """), {"id": report_id}).mappings().first()
    if not r:
        raise HTTPException(status_code=404, detail="报告不存在")
    return ApiResponse(data={**dict(r), "report_date": str(r["report_date"])})
