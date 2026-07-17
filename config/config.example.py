# config/config.example.py
# 配置模板。新环境部署时:
#     cp config/config.example.py config/config.py
# 然后把下面的占位符换成真值。
#
# config/config.py 已在 .gitignore 里,不会进仓库(本仓库是公开的)。
# 每一项也都可以用同名环境变量覆盖,优先级高于这里的默认值。
import os

# ============================================================================
# 数据库
# ============================================================================
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_USER = os.environ.get("DB_USER", "root")
DB_PASS = os.environ.get("DB_PASS", "请填入数据库密码")
DB_NAME = os.environ.get("DB_NAME", "amazon_sellersprite_db")

# ============================================================================
# LLM(内网 Gemma,用于生成日报/周报/月报分析)
# ============================================================================
LLM_BASE_URL = os.environ.get("ANALYSIS_LLM_BASE_URL", "http://10.0.0.22:8005/v1")
LLM_MODEL = os.environ.get("ANALYSIS_LLM_MODEL", "gemma-4-31b-it-fp8")

# ============================================================================
# 卖家精灵(cookie 过期时用账号密码自动重登刷新)
# ============================================================================
SELLERSPRITE_COOKIE = os.environ.get("SELLERSPRITE_COOKIE", "")
SELLERSPRITE_EMAIL = os.environ.get("SELLERSPRITE_EMAIL", "请填入账号")
SELLERSPRITE_PASSWORD = os.environ.get("SELLERSPRITE_PASSWORD", "请填入密码哈希")
SELLERSPRITE_SALT = os.environ.get("SELLERSPRITE_SALT", "请填入 salt")

# ============================================================================
# 钉钉推送(自定义机器人,加签模式)
#   access_token 来自机器人 webhook 地址 ?access_token= 后面那串
#   secret 是安全设置里"加签"的 SEC 开头字符串
# ============================================================================
DINGTALK_ACCESS_TOKEN = os.environ.get("DINGTALK_ACCESS_TOKEN", "请填入 access_token")
DINGTALK_SECRET = os.environ.get("DINGTALK_SECRET", "请填入 SEC 开头的加签密钥")
# 完整 webhook 地址(推送代码用这个;timestamp/sign 由 dingtalk_push 追加)
DINGTALK_WEBHOOK = os.environ.get(
    "DINGTALK_WEBHOOK",
    f"https://oapi.dingtalk.com/robot/send?access_token={DINGTALK_ACCESS_TOKEN}")

# ============================================================================
# 阿里云 OSS:钉钉消息里的图表必须挂在公网可达的地址,内网地址钉钉拉不到。
# 强烈建议用 RAM 子账号,只授予该 bucket 的 oss:PutObject / oss:GetObject。
# ============================================================================
OSS_ACCESS_KEY_ID = os.environ.get("OSS_ACCESS_KEY_ID", "")
OSS_ACCESS_KEY_SECRET = os.environ.get("OSS_ACCESS_KEY_SECRET", "")
# 形如 oss-cn-hangzhou.aliyuncs.com(不带 bucket 前缀、不带 https://)
OSS_ENDPOINT = os.environ.get("OSS_ENDPOINT", "")
OSS_BUCKET = os.environ.get("OSS_BUCKET", "")
OSS_PREFIX = os.environ.get("OSS_PREFIX", "report-charts")
# 1=bucket 保持私有,用签名 URL(竞品数据不裸奔);0=bucket 需 public-read
OSS_USE_SIGNED_URL = os.environ.get("OSS_USE_SIGNED_URL", "1") == "1"
# 签名有效期,默认 30 天。钉钉是服务端抓图转存的,抓取时机不完全可控,别设太短。
OSS_SIGN_EXPIRE_SEC = int(os.environ.get("OSS_SIGN_EXPIRE_SEC", str(30 * 86400)))

# 是否在钉钉消息里嵌入图表。需先配好上面的 OSS,否则图必裂。
REPORT_EMBED_CHARTS = os.environ.get("REPORT_EMBED_CHARTS", "0") == "1"
# 图表图片对外可访问的基地址(未配 OSS 时的回落地址,仅本机自测有意义)
PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "http://10.0.5.134:1332")
# 报告页地址
REPORT_PAGE_URL = os.environ.get("REPORT_PAGE_URL", "http://10.0.5.134:8088/reports")

# ============================================================================
# 影刀 RPA 导出的 xlsx 路径
# ============================================================================
ASIN_LIST_XLSX_PATH = os.environ.get("ASIN_LIST_XLSX_PATH", "/tmp/asin_list.xlsx")
ALL_REVIEWS_XLSX_PATH = os.environ.get("ALL_REVIEWS_XLSX_PATH", "/tmp/all_reviews.xlsx")
XLSX_POLL_INTERVAL_SEC = float(os.environ.get("XLSX_POLL_INTERVAL_SEC", "5"))
XLSX_POLL_TIMEOUT_SEC = float(os.environ.get("XLSX_POLL_TIMEOUT_SEC", "300"))
