# backend/analysis/report_charts.py
# 服务端渲染报告图表(PNG),供钉钉推送嵌入。
# 图片写入 backend/static/report_charts/,由 main.py 挂载为
# /static/report-charts/ 静态目录对外提供。
import os
import time
import logging

# matplotlib 惰性导入:未安装时不影响后端启动,仅在渲染图表时报错
# (推送逻辑会捕获并退化为纯文字消息)
try:
    import matplotlib
    matplotlib.use("Agg")  # 无界面后端,必须在 pyplot 之前设置
    from matplotlib import pyplot as plt, font_manager
    from matplotlib.ticker import FuncFormatter
    _MPL_ERROR = None
except ImportError as _e:  # noqa
    plt = font_manager = FuncFormatter = None
    _MPL_ERROR = str(_e)


def _money_fmt(v, _pos=None):
    """金额轴人类可读格式: $52M / $1.2M / $500K / $80"""
    if abs(v) >= 1e6:
        return f"${v / 1e6:.1f}M".replace(".0M", "M")
    if abs(v) >= 1e3:
        return f"${v / 1e3:.0f}K"
    return f"${v:.0f}"

logger = logging.getLogger(__name__)

CHART_DIR = os.path.abspath(os.path.join(
    os.path.dirname(__file__), "..", "static", "report_charts"))

# 与 frontend/src/theme/brands.ts 保持一致的品牌配色/展示名
_BRAND_COLORS = {"oukitel": "#f5222d", "ecoflow": "#13c2c2", "bluetti": "#1677ff",
                 "jackery": "#fa8c16", "vtoman": "#52c41a", "anker": "#722ed1"}
_DISPLAY = {"oukitel": "OUKITEL", "ecoflow": "EcoFlow", "bluetti": "Bluetti",
            "jackery": "Jackery", "vtoman": "VTOMAN", "anker": "Anker"}
_ALIASES = {"ef ecoflow": "ecoflow"}


def _norm(brand: str) -> str:
    k = (brand or "").lower()
    return _ALIASES.get(k, k)


def _color(brand: str) -> str:
    return _BRAND_COLORS.get(_norm(brand), "#8c8c8c")


def _name(brand: str) -> str:
    return _DISPLAY.get(_norm(brand), brand)


_font_ready = False


def _setup_font():
    """选一个系统里存在的中文字体,避免图上中文变方块。"""
    global _font_ready
    if _font_ready:
        return
    for name in ("PingFang SC", "Hiragino Sans GB", "Arial Unicode MS",
                 "Heiti SC", "STHeiti", "Microsoft YaHei", "SimHei",
                 "Noto Sans CJK SC", "WenQuanYi Zen Hei"):
        try:
            font_manager.findfont(font_manager.FontProperties(family=name),
                                  fallback_to_default=False)
            plt.rcParams["font.sans-serif"] = [name]
            logger.info("report charts font: %s", name)
            break
        except Exception:
            continue
    else:
        logger.warning("未找到中文字体,图表中文可能显示为方块")
    plt.rcParams["axes.unicode_minus"] = False
    _font_ready = True


def _prune(days: int = 60):
    """清理过期图片,防止目录无限膨胀。"""
    cutoff = time.time() - days * 86400
    try:
        for f in os.listdir(CHART_DIR):
            p = os.path.join(CHART_DIR, f)
            if os.path.isfile(p) and os.path.getmtime(p) < cutoff:
                os.remove(p)
    except OSError:
        pass


def _save(fig, filename: str) -> None:
    fig.savefig(os.path.join(CHART_DIR, filename), bbox_inches="tight")
    plt.close(fig)


def render_report_charts(summary: dict) -> list:
    """按 build_summary 的结果渲染图表,返回 [{title, file}, ...]。"""
    if _MPL_ERROR:
        raise RuntimeError(
            f"matplotlib 不可用({_MPL_ERROR}),请: backend/venv/bin/pip install matplotlib")
    _setup_font()
    os.makedirs(CHART_DIR, exist_ok=True)
    _prune()

    period, end = summary["period"], summary["end_date"]
    tag = f"{period}_{end}"
    brands, dates = summary["brands"], summary["dates"]
    out = []

    # 1. 品牌对比:营收/销量双轴柱状图
    names = [_name(b["brand"]) for b in brands]
    colors = [_color(b["brand"]) for b in brands]
    fig, ax1 = plt.subplots(figsize=(8, 4.2), dpi=130)
    x = list(range(len(brands)))
    ax1.bar([i - 0.2 for i in x], [b["avg_revenue"] for b in brands],
            width=0.4, color=colors)
    ax1.set_ylabel("营收")
    ax1.yaxis.set_major_formatter(FuncFormatter(_money_fmt))
    ax2 = ax1.twinx()
    ax2.bar([i + 0.2 for i in x], [b["avg_sales"] for b in brands],
            width=0.4, color="#bfbfbf")
    ax2.set_ylabel("销量")
    ax1.set_xticks(x)
    ax1.set_xticklabels(names, rotation=20, ha="right")
    ax1.set_title(f"品牌对比·期间日均  {summary['start_date']} ~ {end}")
    fig.tight_layout()
    fn = f"{tag}_brands.png"
    _save(fig, fn)
    out.append({"title": "品牌对比", "file": fn})

    # 2. 品牌营收走势(多日周期才有)
    if len(dates) > 1:
        fig, ax = plt.subplots(figsize=(8, 4.2), dpi=130)
        for b in brands:
            ys = [v if v is not None else float("nan") for v in b["revenue"]]
            ax.plot(dates, ys, label=_name(b["brand"]), color=_color(b["brand"]),
                    marker="o", markersize=3, linewidth=1.5)
        ax.set_title("品牌营收走势")
        ax.yaxis.set_major_formatter(FuncFormatter(_money_fmt))
        ax.legend(fontsize=8, ncol=3)
        step = max(1, len(dates) // 10)
        ax.set_xticks(dates[::step])
        plt.setp(ax.get_xticklabels(), rotation=30, ha="right", fontsize=8)
        ax.grid(alpha=0.25)
        fig.tight_layout()
        fn = f"{tag}_trend.png"
        _save(fig, fn)
        out.append({"title": "品牌营收走势", "file": fn})

    # 3. 品类营收分布饼图(Top8)
    cats = summary["categories"][:8]
    if cats:
        fig, ax = plt.subplots(figsize=(6.5, 4.5), dpi=130)
        ax.pie([c["revenue"] for c in cats],
               labels=[c["sub_category"] for c in cats],
               autopct="%1.0f%%", textprops={"fontsize": 8},
               startangle=90, counterclock=False)
        ax.set_title("品类营收分布·期间日均")
        fig.tight_layout()
        fn = f"{tag}_category.png"
        _save(fig, fn)
        out.append({"title": "品类营收分布", "file": fn})

    return out
