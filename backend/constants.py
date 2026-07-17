# backend/constants.py
import re
# 储能电源赛道:OUKITEL 为自有品牌(排第一),其余为竞品。
# 注意:本数据集(amazon_sellersprite)中 OUKITEL 实为手机品类、无储能数据,
# 保留在名单中,Overview 仅统计储能口径时其指标自然为 ~0。
FOCUS_BRANDS = ["oukitel", "ef ecoflow", "bluetti", "jackery", "vtoman", "anker"]

# 给前端展示用的规范名称与配色
FOCUS_BRAND_DISPLAY = {
    "oukitel": "OUKITEL",
    "ef ecoflow": "EcoFlow",
    "bluetti": "Bluetti",
    "jackery": "Jackery",
    "vtoman": "VTOMAN",
    "anker": "Anker",
}


def focus_brand_sql_list() -> str:
    """返回可直接拼进 IN(...) 的小写品牌字符串(已加引号)。"""
    return ", ".join(f"'{b}'" for b in FOCUS_BRANDS)


def canonical_brand(brand: str) -> str:
    """把数据库里大小写不一的品牌名归一到规范展示名。"""
    if not brand:
        return brand
    return FOCUS_BRAND_DISPLAY.get(brand.lower(), brand)


# 品牌校正:上游爬虫会把 OUKITEL 官方储能商品的 brand 字段标成第三方店铺名
# (VoelyXcurae/OKITECH/Voltark/EcoVolt/Raikon/Keenergy/YOYOSCX/GridCharge/Solstark
#  /Storbeaonbk/ZanPaun/ROTKUSZ 等),但 product_title 一律以 OUKITEL 开头/包含。
# 判定规则:title 含 OUKITEL 且 sub_category 属于储能/光伏(排除手机壳、贴膜、维修配件),
# 则视为 brand='OUKITEL'。副作用可控:标题带 "for OUKITEL WPxx" 的贴膜/手机壳因类目
# 不匹配自然不会被误归。
def corrected_brand_sql(brand_col: str = "brand",
                        title_col: str = "product_title",
                        sub_cat_col: str = "sub_category") -> str:
    """返回一段 SQL 表达式,把标题含 OUKITEL 且属于储能/光伏类目的行的品牌统一为 'oukitel'。
    调用方直接把 LOWER({brand}) 替换成 {corrected_brand_sql()}。返回值已 LOWER。"""
    storage_pattern = f"({STORAGE_LEAF_REGEX})"
    solar_pattern = f"({SOLAR_LEAF_REGEX})"
    return (
        f"CASE WHEN {title_col} LIKE '%OUKITEL%' "
        f"      AND LOWER({sub_cat_col}) COLLATE utf8mb4_unicode_ci "
        f"          REGEXP '{storage_pattern}|{solar_pattern}' "
        f"     THEN 'oukitel' ELSE LOWER({brand_col}) END"
    )


# 展示名(小写)-> FOCUS_BRANDS key 的反查表,如 "ecoflow" -> "ef ecoflow"。
_DISPLAY_TO_KEY = {disp.lower(): key for key, disp in FOCUS_BRAND_DISPLAY.items()}


def resolve_focus_brand(brand: str):
    """把前端传入的品牌名归一到 FOCUS_BRANDS 里的小写 key。
    兼容原始 key("ef ecoflow")与 canonical 展示名("EcoFlow");
    非聚焦品牌返回 None,供调用方判 404。"""
    if not brand:
        return None
    b = brand.lower()
    if b in FOCUS_BRANDS:
        return b
    return _DISPLAY_TO_KEY.get(b)


# 储能赛道的品类叶子(category_path 末段)跨语言关键词。
# Overview headline 与品牌详情 summary 只统计"储能"品类(类比手机项目的仅手机口径)。
# 品牌详情 category_cards 用 STORAGE/SOLAR/ACCESSORY 三桶 + "其他" 残差。
# 注意:CASE 求值顺序为 储能→光伏→配件→其他,前桶优先(如 "power station" 命中储能而非配件的 station)。
STORAGE_LEAF_REGEX = (  # 储能:发电机/便携电源/移动电源/汽车启动电源/UPS
    "generat"                                  # Generators/Generatoren/Generador/Generatori/Power Take Off Generators
    "|groupes"                                 # Groupes électrogènes (FR)
    "|g[eé]n[eé]rateur"                        # générateur(s) (FR)
    "|発電機|ポータブル電源|蓄電池|モバイルバッテリー"      # JP
    "|power station|portable power|tragbare stromversorgung|centrali elettriche portatili"
    "|power bank|external battery|externe akkus|batteries externes"
    "|cargadores port[aá]tiles|caricabatterie portatile|packs de batterie"
    "|jump|avviatori|d[eé]marreur|arrancador|starthilfe"   # 汽车启动电源
    "|uninterruptible|alimentaci[oó]n ininterrumpida|fuentes de alimentaci"  # UPS
    "|unterbrechungsfreie stromversorgung"
)

SOLAR_LEAF_REGEX = (  # 光伏:太阳能板/光伏系统/逆变器/离并网系统
    "solar"
    "|solarmodule|solarmodul"                  # Monokristalline Solarmodule (DE)
    "|panneaux solaires|pannelli solari|paneles solares|太陽光パネル"
    "|photovoltaik|fotovolt"                   # Photovoltaikanlagen
    "|microinver|mikrowechselrichter|micro inverter|inverter di rete|netzwechselrichter"
    "|off.grid|inselsysteme|syst[eè]mes hors r[eé]seau|sistemas sin conexi[oó]n"
    "|grid.tie|grid.tied|sistemas con conexi[oó]n|syst[eè]mes connect[eé]s|netzgebundene|sistemi di rete"
    "|solar power systems|solaranlagen|energ[ií]a solar"
)

ACCESSORY_LEAF_REGEX = (  # 配件:充电器/线材/适配器/插座/扩展坞/外壳/支架
    "charger|ladeger[aä]t|caricabatterie|cargador|chargeur|充電器"
    "|cable|kabel|cavi|cord|adapter|adattatore|adapt|ケーブル"
    "|plug|stecker|presa|ソケット"
    "|power strip|regleta|mehrfachsteckdosen|multiprese|multi.outlet|電源タップ"
    "|dock|hub|cradle|クレードル"
    "|cover|case|tasche|custodia|houss|abdeckung|ケース"
    "|mount|halterung|スタンド|stand"
    "|accessor|zubeh[oö]r|accessori|accesorios"
    "|remote control|controle"
    "|cigarette|zigarette|lighter"
)

# 各站点 sub_category 本地化名称 → 统一中文标签
# overview 品类营收饼图用:把同一品类的各语言写法合并显示
SUB_CATEGORY_ZH = {
    "cell phones": "智能手机",
    "cellulari e smartphone": "智能手机",
    "smartphones et téléphones portables débloqués": "智能手机",
    "sim-free & unlocked mobile phones": "智能手机",
    "renewed mobile phones & smartphones sim-free & unlocked mobile phones": "智能手机",
    "senior mobile phones": "智能手机",
    "simlockfreie handys": "智能手机",
    "móviles y smartphones libres": "智能手机",
    "celulares y smartphones desbloqueados": "智能手机",
    "unlocked cell phones & smartphones": "智能手机",
    "mobile phones & smartphones": "智能手机",
    "handys & smartphones": "智能手机",
    "携帯電話・スマートフォン本体": "智能手机",
    "スマートフォン本体": "智能手机",
    "smartwatches": "智能手表",
    "montres connectées": "智能手表",
    "smartwatch": "智能手表",
    "wearable tech glasses": "智能眼镜",
    "glasses": "智能眼镜",
    "スマートグラス": "智能眼镜",
    "tablets": "平板电脑",
    "tablet pcs": "平板电脑",
    "tablettes tactiles": "平板电脑",
    "tablet pc": "平板电脑",
    "tablet-pcs": "平板电脑",
    "タブレット": "平板电脑",
    "computer tablets": "平板电脑",
    "graphic tablets": "平板电脑",
    "tabletas gráficas": "平板电脑",
    "computer graphics tablets": "平板电脑",
    "portable tvs": "便携电视",
    "monitors": "显示器",
    "computer monitors": "显示器",
    "monitore": "显示器",
    "monitor": "显示器",
    "écrans pc": "显示器",
    "monitores": "显示器",
    "ordenadores de sobremesa": "台式电脑",
    "desktops": "台式电脑",
    "desktop pcs": "台式电脑",
    "minis": "迷你电脑",
    "mini-pcs": "迷你电脑",
    "mini pc": "迷你电脑",
    "traditional laptops": "笔记本电脑",
    "laptops": "笔记本电脑",
    "earbud headphones": "耳机",
    "screen protectors": "屏幕保护膜",
    "wireless chargers": "无线充电器",
    "cradles": "车载支架",
    "holsters": "手机套",
    "stands": "支架",
    "borescopes": "内窥镜",
    "motorcycle mounts": "摩托车支架",
    "laptop screen filters": "笔记本屏幕膜",
    "screen filters": "笔记本屏幕膜",
    "deadbolts": "智能门锁",
    "携帯電話本体": "智能手机",
    "generadores": "发电机",
    "generatoren": "发电机",
    "generatori": "发电机",
    "generators": "发电机",
    "groupes éléctrogènes": "发电机",
    "solar panels": "太阳能板",
    "paneles solares monocristalinos": "太阳能板",
    "panneaux solaires monocristallins": "太阳能板",
    "monokristalline solarmodule": "太阳能板",
    "太陽光パネル": "太阳能板",
    "ポータブル電源・蓄電池": "便携电源",
    "open-ear headphones": "开放式耳机",
    "open-ear-kopfhörer": "开放式耳机",
    "outdoor speakers": "户外音响",
    "desktops": "台式电脑",
    "traditional laptops": "笔记本电脑",
    "normale laptops": "笔记本电脑",
}


# 精确字典未命中时的跨语言关键词兜底,把各站点本地化品类名归并到中文大类。
# 顺序即优先级:空调→光伏→UPS→发电机→便携电源→配件,先命中者胜
# (如 "solar charger" 应归光伏而非配件,"outdoor generator covers" 应归发电机)。
_SUB_CATEGORY_FALLBACK = [
    ("便携空调", r"air conditioner|klimager[aä]t|climatiseur|aire acondicionado|condizionator|エアコン"),
    ("太阳能板", SOLAR_LEAF_REGEX),
    ("UPS电源",  r"uninterruptible|unterbrechungsfreie|alimentaci[oó]n ininterrumpida|fuentes de alimentaci|gruppo di continuit"),
    ("发电机",   r"generat|genera(d|t)or|groupes|g[eé]n[eé]rateur|発電機"),
    ("便携电源", r"power bank|portable power|power station|external battery|externe.{0,12}akku|batteries externes|"
                 r"cargadores port[aá]tiles|caricabatterie portatile|packs de batterie|"
                 r"ポータブル電源|蓄電池|モバイルバッテリー|jump|avviatori|d[eé]marreur|arrancador|starthilfe"),
    ("配件",     ACCESSORY_LEAF_REGEX),
]
_SUB_CATEGORY_FALLBACK = [(zh, re.compile(rx, re.IGNORECASE)) for zh, rx in _SUB_CATEGORY_FALLBACK]

# 所有可能的中文输出(字典值 + 兜底大类),用于「已归一标签直通」判断。
_ZH_LABELS = set(SUB_CATEGORY_ZH.values()) | {zh for zh, _ in _SUB_CATEGORY_FALLBACK}


def normalize_sub_category(name: str) -> str:
    """把各站点本地化 sub_category 归一为中文标签:
    精确字典优先,未命中则用跨语言关键词归并到储能大类,再兜底"其他"。"""
    if not name:
        return "其他"
    key = name.lower().strip()
    if key in SUB_CATEGORY_ZH:
        return SUB_CATEGORY_ZH[key]
    if name in _ZH_LABELS:          # 已是归一后的中文标签,直通避免被二次归并
        return name
    for zh, pat in _SUB_CATEGORY_FALLBACK:
        if pat.search(key):
            return zh
    return "其他"


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
    "IN": 0.012,   # INR(数据集含印度站)
}


def fx_case_sql(market_col: str = "market") -> str:
    """生成把指定 market 列折算成 USD 的 SQL 乘数表达式 CASE ... END。"""
    whens = " ".join(
        f"WHEN '{m}' THEN {rate}" for m, rate in FX_TO_USD.items()
    )
    return f"(CASE {market_col} {whens} ELSE 1.0 END)"


