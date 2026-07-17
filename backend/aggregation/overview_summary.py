# backend/aggregation/overview_summary.py
from datetime import date
from sqlalchemy import text
from backend.database import engine
from backend.constants import (
    focus_brand_sql_list, STORAGE_LEAF_REGEX, fx_case_sql,
    normalize_sub_category, corrected_brand_sql,
)

_FOCUS = focus_brand_sql_list()
_FX = fx_case_sql("market")
_CB = corrected_brand_sql()  # 把 OUKITEL 官方储能商品从店铺名(如 Solstark/OKITECH)拉回 oukitel

# 变体聚合规则(两级粒度):
#  - 销量/营收是父体(listing)级,每个 (parent,market) family 只计一次(MAX)
#  - 价格/评分等是变体级,family 内取均值
#  - 储能品类:匹配 category_path 叶子段(仅储能口径,光伏/配件不计入 Overview headline)
#  - 金额:折算 USD
_SQL = text(f"""
INSERT INTO daily_overview_summary
    (data_date, brand, markets, product_count, total_revenue,
     total_monthly_sales, avg_price, avg_rating, avg_growth_rate,
     avg_gross_margin, fba_ratio)
WITH per_asin AS (
    SELECT COALESCE(NULLIF(parent_asin,''), asin) AS pkey, market,
           MAX({_CB}) AS brand, asin,
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
      AND {_CB} IN ({_FOCUS})
    GROUP BY pkey, market, asin
),
family AS (
    SELECT pkey, market, brand,
           MAX(sales) AS sales, MAX(rev) AS rev,
           AVG(price) AS price, AVG(rating) AS rating,
           AVG(growth) AS growth, AVG(margin) AS margin,
           MAX(is_fba) AS is_fba,
           COUNT(DISTINCT CONCAT_WS('|', sales, rev, price, rating)) AS variant_count
    FROM per_asin GROUP BY pkey, market, brand
)
SELECT :d,
       brand,
       GROUP_CONCAT(DISTINCT market ORDER BY market),
       SUM(variant_count),
       SUM(rev * {_FX}),
       SUM(sales),
       AVG(price * {_FX}),
       AVG(rating),
       AVG(growth),
       AVG(margin),
       AVG(is_fba)
FROM family
GROUP BY brand
ORDER BY SUM(rev * {_FX}) DESC
ON DUPLICATE KEY UPDATE
    markets = VALUES(markets), product_count = VALUES(product_count),
    total_revenue = VALUES(total_revenue), total_monthly_sales = VALUES(total_monthly_sales),
    avg_price = VALUES(avg_price), avg_rating = VALUES(avg_rating),
    avg_growth_rate = VALUES(avg_growth_rate), avg_gross_margin = VALUES(avg_gross_margin),
    fba_ratio = VALUES(fba_ratio)
""")

# 品类营收占比(全品类、全站点、五品牌,按 sub_category 归一中文标签后汇总)
# 不限手机,统计所有品类的营收分布
_CAT_QUERY = text(f"""
WITH per_asin AS (
    SELECT COALESCE(NULLIF(parent_asin,''), asin) AS pkey, market,
           MAX({_CB}) AS brand, asin,
           MAX(sub_category) AS sub_category,
           MAX(CAST(NULLIF(REGEXP_REPLACE(monthly_revenue,'[^0-9.]',''),'') AS DECIMAL(18,2))) AS rev
    FROM amazon
    WHERE crawl_date = :d
      AND {_CB} IN ({_FOCUS})
    GROUP BY pkey, market, asin
),
family AS (
    SELECT pkey, market, brand, MAX(sub_category) AS sub_category, MAX(rev) AS rev
    FROM per_asin GROUP BY pkey, market, brand
)
SELECT sub_category, SUM(rev * {_FX}) AS revenue
FROM family
WHERE sub_category IS NOT NULL AND sub_category <> ''
GROUP BY sub_category
ORDER BY revenue DESC
""")


def run_overview_summary(target_date: date) -> None:
    with engine.begin() as conn:
        conn.execute(_SQL, {"d": target_date, "re": STORAGE_LEAF_REGEX})

        # 品类营收:全品类全站点,Python 侧归一中文标签后按标签合并写入
        rows = conn.execute(_CAT_QUERY, {"d": target_date}).mappings().all()
        merged: dict = {}
        for r in rows:
            label = normalize_sub_category(r["sub_category"])
            merged[label] = merged.get(label, 0) + float(r["revenue"] or 0)
        # 按营收降序取 Top 10 写入
        top = sorted(merged.items(), key=lambda x: -x[1])[:10]
        conn.execute(text("DELETE FROM daily_overview_category WHERE data_date = :d"),
                     {"d": target_date})
        for cat, rev in top:
            conn.execute(text("""
                INSERT INTO daily_overview_category (data_date, sub_category, revenue)
                VALUES (:d, :cat, :rev)
            """), {"d": target_date, "cat": cat, "rev": rev})
