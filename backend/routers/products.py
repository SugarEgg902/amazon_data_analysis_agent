# backend/routers/products.py
from fastapi import APIRouter, Query, HTTPException
from sqlalchemy import text
from typing import Optional, List
from backend.database import engine
from backend.models.schemas import ApiResponse

router = APIRouter()

_SORT_COLS = {
    "monthly_sales": "monthly_sales",
    "price": "price",
    "main_bsr": "main_bsr",
    "sub_bsr": "sub_bsr",
    "rating": "rating",
    "growth_rate": "growth_rate",
    "monthly_revenue": "monthly_revenue",
}


@router.get("/products", response_model=ApiResponse)
def list_products(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    market: Optional[str] = None,
    brand: Optional[str] = None,
    category: Optional[List[str]] = Query(default=None),
    q: Optional[str] = Query(default=None, description="按品牌/商品名/ASIN模糊搜索"),
    date: Optional[str] = Query(default=None, description="快照日期,默认最新"),
    sort: str = Query(default="monthly_sales"),
    order: str = Query(default="desc", pattern="^(asc|desc)$"),
):
    sort_col = _SORT_COLS.get(sort, "monthly_sales")
    order_sql = "DESC" if order == "desc" else "ASC"
    params: dict = {"limit": page_size, "offset": (page - 1) * page_size}

    with engine.connect() as conn:
        target = date or conn.execute(
            text("SELECT MAX(snapshot_date) FROM product_daily_snapshot")
        ).scalar()
        if target is None:
            return ApiResponse(data={"items": [], "total": 0, "page": page,
                                     "page_size": page_size, "date": None, "summary": None})
        params["d"] = target

        filters = ["s.snapshot_date = :d"]
        if market:
            filters.append("s.market = :market"); params["market"] = market
        if brand:
            filters.append("LOWER(s.brand) = LOWER(:brand)"); params["brand"] = brand
        if category:
            placeholders = ", ".join(f":cat_{i}" for i in range(len(category)))
            filters.append(f"s.sub_category IN ({placeholders})")
            for i, c in enumerate(category):
                params[f"cat_{i}"] = c
        if q:
            filters.append("(s.brand LIKE :q OR s.asin LIKE :q OR m.product_title LIKE :q)")
            params["q"] = f"%{q}%"
        where = " AND ".join(filters)

        base = f"""
            FROM product_daily_snapshot s
            LEFT JOIN (
                SELECT asin, market,
                       MAX(product_title) AS product_title,
                       MAX(main_image) AS main_image,
                       MAX(product_url) AS product_url,
                       MAX(fulfillment_method) AS fulfillment_method
                FROM amazon WHERE crawl_date = :d
                GROUP BY asin, market
            ) m ON m.asin = s.asin AND m.market = s.market
            WHERE {where}
        """

        total = conn.execute(text(f"SELECT COUNT(*) {base}"), params).scalar()
        summary = conn.execute(text(f"""
            SELECT SUM(s.monthly_sales) AS total_sales,
                   SUM(s.monthly_revenue) AS total_revenue,
                   COUNT(*) AS product_count,
                   AVG(s.price) AS avg_price
            {base}
        """), params).mappings().first()
        rows = conn.execute(text(f"""
            SELECT s.asin, s.market, s.brand, s.sub_category, s.price,
                   s.monthly_sales, s.monthly_revenue, s.main_bsr, s.sub_bsr,
                   s.rating, s.rating_count, s.gross_margin, s.growth_rate,
                   m.product_title, m.main_image, m.product_url, m.fulfillment_method
            {base}
            ORDER BY s.{sort_col} {order_sql}
            LIMIT :limit OFFSET :offset
        """), params).mappings().all()

    return ApiResponse(data={
        "items": [dict(r) for r in rows], "total": total,
        "page": page, "page_size": page_size, "date": str(target),
        "summary": dict(summary) if summary else None,
    })


@router.get("/products/{asin}", response_model=ApiResponse)
def get_product(asin: str, market: Optional[str] = None):
    params: dict = {"asin": asin}
    market_clause = ""
    if market:
        market_clause = " AND market = :market"
        params["market"] = market
    with engine.connect() as conn:
        rows = conn.execute(text(f"""
            SELECT * FROM product_daily_snapshot
            WHERE asin = :asin {market_clause}
            ORDER BY snapshot_date DESC
        """), params).mappings().all()
        if not rows:
            raise HTTPException(status_code=404, detail="Product not found")
        latest = dict(rows[0])
        meta = conn.execute(text("""
            SELECT product_title, main_image, product_url, parent_asin, sku,
                   main_category, fulfillment_method, seller_location, buybox_seller,
                   product_weight, product_dimensions, launch_date, days_on_market
            FROM amazon WHERE asin = :asin
            ORDER BY crawl_date DESC LIMIT 1
        """), {"asin": asin}).mappings().first()

    history = [{
        "snapshot_date": str(r["snapshot_date"]), "price": r["price"],
        "monthly_sales": r["monthly_sales"], "monthly_revenue": r["monthly_revenue"],
        "main_bsr": r["main_bsr"], "sub_bsr": r["sub_bsr"], "rating": r["rating"],
    } for r in reversed(rows)]

    return ApiResponse(data={**latest, **(dict(meta) if meta else {}), "history": history})
