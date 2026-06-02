# backend/aggregation/product_snapshot.py
from datetime import date
from sqlalchemy import text
from backend.database import engine
from backend.constants import fx_case_sql

_FX = fx_case_sql("market")

# 每 (asin, market) 一行快照。重复行用 MAX(清洗值) 折叠。
# 金额(price / monthly_revenue)折算成 USD 后存储,以便跨站点汇总;
# monthly_sales 是销量计数,不折算。
_SQL = text(f"""
    INSERT INTO product_daily_snapshot
        (snapshot_date, asin, market, brand, sub_category, price,
         monthly_sales, monthly_revenue, main_bsr, sub_bsr,
         rating, rating_count, gross_margin, growth_rate)
    SELECT
        :d, asin, market, MAX(brand), MAX(sub_category),
        MAX(CAST(NULLIF(REGEXP_REPLACE(price,'[^0-9.]',''),'') AS DECIMAL(10,2))) * {_FX},
        MAX(CAST(NULLIF(REGEXP_REPLACE(monthly_sales,'[^0-9.]',''),'') AS UNSIGNED)),
        MAX(CAST(NULLIF(REGEXP_REPLACE(monthly_revenue,'[^0-9.]',''),'') AS DECIMAL(18,2))) * {_FX},
        MAX(CAST(NULLIF(REGEXP_REPLACE(main_bsr,'[^0-9]',''),'') AS UNSIGNED)),
        MAX(CAST(NULLIF(REGEXP_REPLACE(sub_bsr,'[^0-9]',''),'') AS UNSIGNED)),
        MAX(CAST(NULLIF(rating,'') AS DECIMAL(3,2))),
        MAX(CAST(NULLIF(REGEXP_REPLACE(rating_count,'[^0-9]',''),'') AS UNSIGNED)),
        MAX(CAST(NULLIF(gross_margin,'') AS DECIMAL(6,4))),
        MAX(CAST(NULLIF(monthly_sales_growth_rate,'') AS DECIMAL(10,4)))
    FROM amazon
    WHERE crawl_date = :d AND asin IS NOT NULL AND market IS NOT NULL
    GROUP BY asin, market
    ON DUPLICATE KEY UPDATE
        brand = VALUES(brand), sub_category = VALUES(sub_category),
        price = VALUES(price), monthly_sales = VALUES(monthly_sales),
        monthly_revenue = VALUES(monthly_revenue), main_bsr = VALUES(main_bsr),
        sub_bsr = VALUES(sub_bsr), rating = VALUES(rating),
        rating_count = VALUES(rating_count), gross_margin = VALUES(gross_margin),
        growth_rate = VALUES(growth_rate)
""")


def run_product_snapshot(target_date: date) -> None:
    with engine.begin() as conn:
        conn.execute(_SQL, {"d": target_date})
