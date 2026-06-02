# backend/constants.py
# 核心关注品牌(数据库中大小写不一,统一用小写比较)。
# 注意:OUKITEL 当前数据库无数据,保留在名单中,有数据时自动显示。
FOCUS_BRANDS = ["blackview", "ulefone", "cubot", "oukitel", "doogee"]

# 给前端展示用的规范名称与配色
FOCUS_BRAND_DISPLAY = {
    "blackview": "Blackview",
    "ulefone": "Ulefone",
    "cubot": "CUBOT",
    "oukitel": "OUKITEL",
    "doogee": "DOOGEE",
}


def focus_brand_sql_list() -> str:
    """返回可直接拼进 IN(...) 的小写品牌字符串(已加引号)。"""
    return ", ".join(f"'{b}'" for b in FOCUS_BRANDS)


def canonical_brand(brand: str) -> str:
    """把数据库里大小写不一的品牌名归一到规范展示名。"""
    if not brand:
        return brand
    return FOCUS_BRAND_DISPLAY.get(brand.lower(), brand)


# 各站点对"手机"品类的本地化叶子名(category_path 末段)关键词。
# 用于跨语言把所有站点的手机品类放一起比较,且只匹配叶子段,
# 避免误收"手机配件"(配件路径含 Cell Phones & Accessories 但叶子是 Holsters 等)。
PHONE_LEAF_REGEX = (
    "smartphone|cell phone|mobile phone|handys|m[oó]vil|"
    "celular|cellulari|t[eé]l[eé]phone"
)


# 各站点本地货币 -> USD 的静态近似汇率(原始表只有本地货币价格,无货币字段)。
# 跨站点汇总金额前必须先折算成 USD,否则等于把 JPY/EUR/GBP 直接相加。
# 这是静态近似值,需要精确口径时应接入实时汇率。
FX_TO_USD = {
    "US": 1.0,
    "CA": 0.73,    # CAD
    "UK": 1.27,    # GBP
    "DE": 1.08,    # EUR
    "ES": 1.08,    # EUR
    "FR": 1.08,    # EUR
    "IT": 1.08,    # EUR
    "JP": 0.0067,  # JPY
    "MX": 0.058,   # MXN
}


def fx_case_sql(market_col: str = "market") -> str:
    """生成把指定 market 列折算成 USD 的 SQL 乘数表达式 CASE ... END。"""
    whens = " ".join(
        f"WHEN '{m}' THEN {rate}" for m, rate in FX_TO_USD.items()
    )
    return f"(CASE {market_col} {whens} ELSE 1.0 END)"


