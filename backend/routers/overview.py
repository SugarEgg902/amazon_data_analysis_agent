# backend/routers/overview.py
from fastapi import APIRouter, Query
from sqlalchemy import text
from typing import Optional
from backend.database import engine
from backend.models.schemas import ApiResponse
from backend.constants import (focus_brand_sql_list, canonical_brand,
                               PHONE_LEAF_REGEX, fx_case_sql)

router = APIRouter()

_FOCUS = focus_brand_sql_list()
_FX = fx_case_sql("market")  # 把本地货币金额折算成 USD 的 CASE 乘数

# 变体聚合规则(两级粒度):
#  - 销量 monthly_sales / 营收 monthly_revenue 是"父体(listing)级"指标,会被复制到
#    每个变体行 —— 因此每个 (父ASIN, 站点) family 只计一次(取家族代表值 MAX),
#    绝不能跨变体相加(否则同一父体的销量会按变体数翻倍)。
#  - 价格/评分/增长/毛利等是变体级,family 内取变体平均;
#    SKU 数按"指标不同的变体各计一次"(完全相同的变体合并)。
# 第一步 per_asin:按 (父ASIN,站点,asin) 折叠原始重复行 -> 每变体一行。
_PER_ASIN = ("""
    SELECT COALESCE(NULLIF(parent_asin,''), asin) AS pkey, market, brand, asin,
           MAX(sub_category) AS sub_category,
           MAX(CAST(NULLIF(REGEXP_REPLACE(monthly_sales,'[^0-9.]',''),'') AS UNSIGNED)) AS sales,
           MAX(CAST(NULLIF(REGEXP_REPLACE(monthly_revenue,'[^0-9.]',''),'') AS DECIMAL(18,2))) AS rev,
           MAX(CAST(NULLIF(REGEXP_REPLACE(price,'[^0-9.]',''),'') AS DECIMAL(10,2))) AS price,
           MAX(CAST(NULLIF(rating,'') AS DECIMAL(3,2))) AS rating,
           MAX(CAST(NULLIF(monthly_sales_growth_rate,'') AS DECIMAL(10,4))) AS growth,
           MAX(CAST(NULLIF(gross_margin,'') AS DECIMAL(6,4))) AS margin,
           MAX(fulfillment_method = 'FBA') AS is_fba
    FROM amazon
    WHERE crawl_date = :d
      AND LOWER(SUBSTRING_INDEX(category_path, ':', -1)) COLLATE utf8mb4_unicode_ci REGEXP :re
      AND LOWER(brand) IN (__FOCUS__)
    GROUP BY pkey, market, brand, asin
""").replace("__FOCUS__", _FOCUS)

# 第二步 family:按 (父ASIN,站点) 聚合 -> 销量/营收计一次,其余取变体均值/计数。
_CTE = f"""
WITH per_asin AS ({_PER_ASIN}),
family AS (
    SELECT pkey, market, brand, MAX(sub_category) AS sub_category,
           MAX(sales) AS sales,            -- 家族级,计一次
           MAX(rev)   AS rev,              -- 家族级,计一次
           AVG(price) AS price, AVG(rating) AS rating,
           AVG(growth) AS growth, AVG(margin) AS margin,
           MAX(is_fba) AS is_fba,
           COUNT(DISTINCT CONCAT_WS('|', sales, rev, price, rating, growth, margin, is_fba)) AS variant_count
    FROM per_asin
    GROUP BY pkey, market, brand
)
"""

_BRANDS_SQL = _CTE + f"""
SELECT brand,
       GROUP_CONCAT(DISTINCT market ORDER BY market) AS markets,
       SUM(variant_count) AS product_count,
       SUM(rev * {_FX}) AS total_revenue,
       SUM(sales) AS total_monthly_sales,
       AVG(price * {_FX}) AS avg_price,
       AVG(rating) AS avg_rating,
       AVG(growth) AS avg_growth_rate,
       AVG(margin) AS avg_gross_margin,
       AVG(is_fba) AS fba_ratio
FROM family
GROUP BY brand
ORDER BY total_revenue DESC
"""

_CATS_SQL = _CTE + f"""
SELECT sub_category, SUM(rev * {_FX}) AS revenue
FROM family
GROUP BY sub_category ORDER BY revenue DESC LIMIT 10
"""


@router.get("/overview", response_model=ApiResponse)
def get_overview(date: Optional[str] = Query(default=None),
                 market: Optional[str] = Query(default=None)):
    # 只按品牌聚类、跨所有站点合并;只统计"手机"品类;忽略 market 开关。
    with engine.connect() as conn:
        target = date or conn.execute(
            text("SELECT MAX(crawl_date) FROM amazon")
        ).scalar()
        if target is None:
            return ApiResponse(data={"date": None, "category": "手机",
                                     "brands": [], "category_share": []})
        params = {"d": target, "re": PHONE_LEAF_REGEX}
        brands = conn.execute(text(_BRANDS_SQL), params).mappings().all()
        cats = conn.execute(text(_CATS_SQL), params).mappings().all()

    brand_rows = []
    for r in brands:
        d = dict(r)
        d["brand"] = canonical_brand(r["brand"])
        brand_rows.append(d)

    return ApiResponse(data={
        "date": str(target),
        "category": "手机（全站点合并）",
        "brands": brand_rows,
        "category_share": [dict(r) for r in cats],
    })
