# backend/aggregation/category_summary.py
from datetime import date
from sqlalchemy import text
from backend.database import engine
from backend.constants import fx_case_sql

_FX = fx_case_sql("market")

# 金额(revenue/price)折算成 USD 存储,以便跨站点汇总;sales 是计数不折算。
_SQL = text(f"""
    INSERT INTO daily_category_summary
        (data_date, market, main_category, sub_category, brand,
         product_count, total_revenue, total_monthly_sales, avg_price)
    SELECT
        :d, market, MAX(main_category), sub_category, brand,
        COUNT(*), SUM(revenue_c) * {_FX}, SUM(sales_c), AVG(price_c) * {_FX}
    FROM (
        SELECT market, main_category, sub_category, brand,
            MAX(CAST(NULLIF(REGEXP_REPLACE(monthly_revenue,'[^0-9.]',''),'') AS DECIMAL(18,2))) AS revenue_c,
            MAX(CAST(NULLIF(REGEXP_REPLACE(monthly_sales,'[^0-9.]',''),'') AS UNSIGNED)) AS sales_c,
            MAX(CAST(NULLIF(REGEXP_REPLACE(price,'[^0-9.]',''),'') AS DECIMAL(10,2))) AS price_c
        FROM amazon
        WHERE crawl_date = :d AND brand IS NOT NULL AND sub_category IS NOT NULL
              AND market IS NOT NULL
        GROUP BY asin, market, main_category, sub_category, brand
    ) dedup
    GROUP BY market, sub_category, brand
    ON DUPLICATE KEY UPDATE
        main_category = VALUES(main_category),
        product_count = VALUES(product_count),
        total_revenue = VALUES(total_revenue),
        total_monthly_sales = VALUES(total_monthly_sales),
        avg_price = VALUES(avg_price)
""")


def run_category_summary(target_date: date) -> None:
    with engine.begin() as conn:
        conn.execute(_SQL, {"d": target_date})
