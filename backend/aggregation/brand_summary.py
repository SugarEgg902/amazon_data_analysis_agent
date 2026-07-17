# backend/aggregation/brand_summary.py
from datetime import date
from sqlalchemy import text
from backend.database import engine
from backend.constants import fx_case_sql, corrected_brand_sql

_FX = fx_case_sql("market")
_CB = corrected_brand_sql()  # OUKITEL 官方储能商品的店铺名归回 oukitel

# 两级去重:
#  1. 按 (asin, market) 折叠原始重复行 -> 每变体一行
#  2. 按 (parent_asin, market) 聚合家族 -> 销量/营收取 MAX(计一次),价格/评分取均值
# 金额(revenue/price)折算成 USD 存储。
_SQL = text(f"""
    INSERT INTO daily_brand_summary
        (data_date, market, brand, product_count, total_revenue,
         total_monthly_sales, avg_price, avg_rating, avg_growth_rate,
         avg_gross_margin, fba_ratio)
    SELECT
        :d, market, brand,
        COUNT(*),
        SUM(rev) * {_FX}, SUM(sales), AVG(price) * {_FX},
        AVG(rating), AVG(growth), AVG(margin), AVG(is_fba)
    FROM (
        SELECT market, brand,
            MAX(sales_c) AS sales,
            MAX(rev_c) AS rev,
            AVG(price_c) AS price,
            AVG(rating_c) AS rating,
            AVG(growth_c) AS growth,
            AVG(margin_c) AS margin,
            MAX(is_fba) AS is_fba
        FROM (
            SELECT COALESCE(NULLIF(parent_asin,''), asin) AS pkey, market,
                MAX({_CB}) AS brand,
                MAX(CAST(NULLIF(REGEXP_REPLACE(monthly_revenue,'[^0-9.]',''),'') AS DECIMAL(18,2))) AS rev_c,
                MAX(CAST(NULLIF(REGEXP_REPLACE(monthly_sales,'[^0-9.]',''),'') AS UNSIGNED)) AS sales_c,
                MAX(CAST(NULLIF(REGEXP_REPLACE(price,'[^0-9.]',''),'') AS DECIMAL(10,2))) AS price_c,
                MAX(CAST(NULLIF(rating,'') AS DECIMAL(3,2))) AS rating_c,
                MAX(CAST(NULLIF(monthly_sales_growth_rate,'') AS DECIMAL(10,4))) AS growth_c,
                MAX(CAST(NULLIF(gross_margin,'') AS DECIMAL(6,4))) AS margin_c,
                MAX(fulfillment_method = 'FBA') AS is_fba
            FROM amazon
            WHERE crawl_date = :d AND brand IS NOT NULL AND market IS NOT NULL
            GROUP BY pkey, market, asin
        ) per_asin
        GROUP BY pkey, market, brand
    ) family
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
