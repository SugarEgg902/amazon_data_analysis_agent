# backend/aggregation/brand_summary.py
from datetime import date
from sqlalchemy import text
from backend.database import engine
from backend.constants import fx_case_sql

_FX = fx_case_sql("market")

# 内层按 (asin, market) 去重：原始表存在重复行，且无行级主键，
# 重复行数值一致，故用 MAX(清洗值) 取代表值，避免 SUM 重复计数。
# 金额(revenue/price)折算成 USD 存储,以便跨站点汇总;sales 是计数不折算。
_SQL = text(f"""
    INSERT INTO daily_brand_summary
        (data_date, market, brand, product_count, total_revenue,
         total_monthly_sales, avg_price, avg_rating, avg_growth_rate,
         avg_gross_margin, fba_ratio)
    SELECT
        :d, market, brand,
        COUNT(*),
        SUM(revenue_c) * {_FX}, SUM(sales_c), AVG(price_c) * {_FX},
        AVG(rating_c), AVG(growth_c), AVG(margin_c), AVG(is_fba)
    FROM (
        SELECT market, brand,
            MAX(CAST(NULLIF(REGEXP_REPLACE(monthly_revenue,'[^0-9.]',''),'') AS DECIMAL(18,2))) AS revenue_c,
            MAX(CAST(NULLIF(REGEXP_REPLACE(monthly_sales,'[^0-9.]',''),'') AS UNSIGNED)) AS sales_c,
            MAX(CAST(NULLIF(REGEXP_REPLACE(price,'[^0-9.]',''),'') AS DECIMAL(10,2))) AS price_c,
            MAX(CAST(NULLIF(rating,'') AS DECIMAL(3,2))) AS rating_c,
            MAX(CAST(NULLIF(monthly_sales_growth_rate,'') AS DECIMAL(10,4))) AS growth_c,
            MAX(CAST(NULLIF(gross_margin,'') AS DECIMAL(6,4))) AS margin_c,
            MAX(fulfillment_method = 'FBA') AS is_fba
        FROM amazon
        WHERE crawl_date = :d AND brand IS NOT NULL AND market IS NOT NULL
        GROUP BY asin, market, brand
    ) dedup
    GROUP BY market, brand
    ON DUPLICATE KEY UPDATE
        product_count = VALUES(product_count),
        total_revenue = VALUES(total_revenue),
        total_monthly_sales = VALUES(total_monthly_sales),
        avg_price = VALUES(avg_price),
        avg_rating = VALUES(avg_rating),
        avg_growth_rate = VALUES(avg_growth_rate),
        avg_gross_margin = VALUES(avg_gross_margin),
        fba_ratio = VALUES(fba_ratio)
""")


def run_brand_summary(target_date: date) -> None:
    with engine.begin() as conn:
        conn.execute(_SQL, {"d": target_date})
