"""型号销量聚合 - 每天按品牌×型号×站点聚合销量数据。

匹配规则: product_title LIKE '%model%'
去重: 按 (parent_asin, market) family,销量/营收 MAX
金额: 折算 USD
"""
from datetime import date
from sqlalchemy import text
from backend.database import engine
from backend.constants import fx_case_sql

_FX = fx_case_sql("market")


def run_model_summary(target_date: date) -> None:
    with engine.begin() as conn:
        # 取所有型号
        models = conn.execute(text("""
            SELECT brand, model, type FROM brand_models
        """)).mappings().all()
        if not models:
            return

        # 清除当日旧数据
        conn.execute(text("""
            DELETE FROM daily_model_summary WHERE data_date = :d
        """), {"d": target_date})

        # 每个型号聚合
        for m in models:
            brand_lower = m["brand"].lower()
            model = m["model"]
            type_ = m["type"]

            conn.execute(text(f"""
                INSERT INTO daily_model_summary
                    (data_date, brand, model, type, market, total_sales, total_revenue, sku_count, avg_price)
                WITH per_asin AS (
                    SELECT COALESCE(NULLIF(parent_asin,''), asin) AS pkey, market, asin,
                           MAX(CAST(NULLIF(REGEXP_REPLACE(monthly_sales,'[^0-9.]',''),'') AS UNSIGNED)) AS sales,
                           MAX(CAST(NULLIF(REGEXP_REPLACE(monthly_revenue,'[^0-9.]',''),'') AS DECIMAL(18,2))) AS rev,
                           MAX(CAST(NULLIF(REGEXP_REPLACE(price,'[^0-9.]',''),'') AS DECIMAL(10,2))) AS price
                    FROM amazon
                    WHERE crawl_date = :d
                      AND LOWER(brand) = :brand
                      AND product_title LIKE :model_pattern
                    GROUP BY pkey, market, asin
                ),
                family AS (
                    SELECT pkey, market,
                           MAX(sales) AS sales, MAX(rev) AS rev, AVG(price) AS price
                    FROM per_asin GROUP BY pkey, market
                )
                SELECT :d, :brand_canonical, :model, :type, market,
                       SUM(sales) AS total_sales,
                       SUM(rev * {_FX}) AS total_revenue,
                       COUNT(*) AS sku_count,
                       AVG(price * {_FX}) AS avg_price
                FROM family
                WHERE sales > 0
                GROUP BY market
            """), {
                "d": target_date,
                "brand": brand_lower,
                "brand_canonical": m["brand"],
                "model": model,
                "type": type_,
                "model_pattern": f"%{model}%",
            })


if __name__ == "__main__":
    from datetime import date
    run_model_summary(date.today())
    print("done")
