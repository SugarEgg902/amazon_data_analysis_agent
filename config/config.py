# config/config.py
import os

LLM_BASE_URL = os.environ.get("ANALYSIS_LLM_BASE_URL", "http://10.0.0.22:8005/v1")
LLM_MODEL = os.environ.get("ANALYSIS_LLM_MODEL", "gemma-4-31b-it-fp8")

ASIN_LIST_XLSX_PATH = os.environ.get("ASIN_LIST_XLSX_PATH", "/tmp/asin_list.xlsx")
ALL_REVIEWS_XLSX_PATH = os.environ.get("ALL_REVIEWS_XLSX_PATH", "/tmp/all_reviews.xlsx")
XLSX_POLL_INTERVAL_SEC = float(os.environ.get("XLSX_POLL_INTERVAL_SEC", "5"))
XLSX_POLL_TIMEOUT_SEC = float(os.environ.get("XLSX_POLL_TIMEOUT_SEC", "300"))

# 卖家精灵登录 cookie（自动刷新,无需手动维护）
SELLERSPRITE_COOKIE = ''
