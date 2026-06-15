"""导入型号数据到 brand_models 表。

解析 amazon_final_models.txt，把 / 分隔的复合型号拆分。
例: 'BV9200 / BV9300' -> ['BV9200', 'BV9300']
    'Tab 16 / Tab 16 Pro' -> ['Tab 16', 'Tab 16 Pro']
    'Wave 6C / 7C / 8C / 9C' -> ['Wave 6C', 'Wave 7C', 'Wave 8C', 'Wave 9C']
"""
import os
import sys
import re

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sqlalchemy import text
from backend.database import engine

TXT_PATH = os.path.join(
    os.path.dirname(__file__), "..", "brand_model_data_example", "amazon_final_models.txt"
)


def expand_model(raw: str) -> list[str]:
    """拆分 / 分隔的复合型号。

    保留前缀逻辑：'Wave 6C / 7C / 8C' -> ['Wave 6C', 'Wave 7C', 'Wave 8C']
    无前缀逻辑：'BV9200 / BV9300' -> ['BV9200', 'BV9300']
    """
    raw = raw.strip()
    if "/" not in raw:
        return [raw]

    parts = [p.strip() for p in raw.split("/")]
    if not parts:
        return [raw]

    # 检测第一段的前缀（最后一个空格之前的内容）
    first = parts[0]
    if " " in first:
        prefix = first.rsplit(" ", 1)[0]
        # 检查后续段是否是裸数字/短编号（如 7C, 8C），如是则补前缀
        result = [first]
        for p in parts[1:]:
            if not p:
                continue
            # 已经带前缀的不动；裸编号补前缀
            if p.split(" ")[0] == prefix:
                result.append(p)
            elif " " not in p and len(p) < 10:  # 短编号，补前缀
                result.append(f"{prefix} {p}")
            else:
                result.append(p)
        return result
    return parts


def main():
    rows = []
    with open(TXT_PATH, encoding="utf-8") as f:
        next(f)  # skip header
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 3:
                continue
            brand, model_raw, type_ = parts[0].strip(), parts[1].strip(), parts[2].strip()
            for model in expand_model(model_raw):
                rows.append((brand, model, type_))

    print(f"解析得到 {len(rows)} 个型号")

    with engine.begin() as conn:
        conn.execute(text("TRUNCATE TABLE brand_models"))
        for brand, model, type_ in rows:
            conn.execute(text("""
                INSERT INTO brand_models (brand, model, type)
                VALUES (:b, :m, :t)
                ON DUPLICATE KEY UPDATE type = VALUES(type)
            """), {"b": brand, "m": model, "t": type_})

    print(f"导入完成，共 {len(rows)} 条")

    # 验证：按品牌+类型统计
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT brand, type, COUNT(*) AS n
            FROM brand_models GROUP BY brand, type ORDER BY brand, type
        """)).mappings().all()
        print("\n品牌-类型分布:")
        for r in result:
            print(f"  {r['brand']:12} {r['type']:6} {r['n']}")


if __name__ == "__main__":
    main()
