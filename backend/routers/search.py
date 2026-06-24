# backend/routers/search.py
import asyncio
import importlib
import json
import logging
import os
import re
import sys
import httpx
from fastapi import APIRouter, Query, HTTPException
from backend.models.schemas import ApiResponse
from backend.routers.amazon import scrape_amazon_products

router = APIRouter()

logger = logging.getLogger(__name__)

# 搜索队列:同一时间只允许一个 Playwright 搜索请求执行
_search_lock = asyncio.Semaphore(1)

_SELLERSPRITE_URL = "https://www.sellersprite.com/v3/api/competing-lookup"
_LOGIN_URL = "https://www.sellersprite.com/v2/login"
_DASHBOARD_URL = "https://www.sellersprite.com/v2/welcome"
_CONFIG_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "config", "config.py"
)


def _get_cookie() -> str:
    from config.config import SELLERSPRITE_COOKIE
    return SELLERSPRITE_COOKIE


async def _auto_refresh_cookie() -> str:
    """通过 HTTP POST 登录卖家精灵,获取新 cookie 并写回 config.py。"""
    logger.info("正在自动刷新卖家精灵 cookie ...")

    login_url = "https://www.sellersprite.com/w/user/signin"
    login_page = "https://www.sellersprite.com/v2/login"
    form_data = {
        "noNeedAutoLogin": "1",
        "password": "",
        "email": "",
        "autoLogin": "Y",
        "salt": "",
    }
    ua = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/148.0.0.0 Safari/537.36"
    )

    async with httpx.AsyncClient(follow_redirects=True, timeout=30) as client:
        # 先访问登录页收集初始 cookie
        await client.get(login_page, headers={"User-Agent": ua})
        # POST 登录
        await client.post(login_url, data=form_data, headers={
            "User-Agent": ua,
            "Content-Type": "application/x-www-form-urlencoded",
            "Origin": "https://www.sellersprite.com",
            "Referer": login_page,
        })
        all_cookies = dict(client.cookies)

    if not all_cookies.get("Sprite-X-Token") and not all_cookies.get("rank-login-user"):
        raise RuntimeError(f"登录失败, cookies={list(all_cookies.keys())}")

    cookie_str = "; ".join(f"{k}={v}" for k, v in all_cookies.items())
    logger.info(f"✓ 登录成功, 获取到 {len(all_cookies)} 个 cookie")

    # 写回 config.py
    with open(_CONFIG_PATH, "r") as f:
        content = f.read()
    escaped = cookie_str.replace("\\", "\\\\").replace("'", "\\'")
    new_content = re.sub(
        r"SELLERSPRITE_COOKIE\s*=\s*(?:\([\s\S]*?\)|\"[^\"]*\"|'[^']*')",
        f"SELLERSPRITE_COOKIE = '{escaped}'",
        content,
    )
    with open(_CONFIG_PATH, "w") as f:
        f.write(new_content)

    import config.config as cfg
    importlib.reload(cfg)
    logger.info("cookie 已更新到 config/config.py")

    return cookie_str


async def _request_sellersprite(keyword: str, market: str, cookie: str) -> dict:
    body = {
        "market": market,
        "monthName": "bsr_sales_nearly",
        "asins": [],
        "keywords": keyword,
        "page": 1,
        "nodeIdPaths": [],
        "symbolFlag": True,
        "size": 60,
        "order": {"field": "total_units", "desc": True},
        "lowPrice": "N",
    }
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/148.0.0.0 Safari/537.36"
        ),
        "Referer": "https://www.sellersprite.com/",
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json;charset=UTF-8",
        "Origin": "https://www.sellersprite.com",
        "Cookie": cookie,
    }
    for part in cookie.split("; "):
        if part.startswith("Sprite-X-Token="):
            headers["Sprite-X-Token"] = part[len("Sprite-X-Token="):]
            break
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        resp = await client.post(_SELLERSPRITE_URL, json=body, headers=headers)
        text = resp.text.strip()
        if resp.status_code == 200 and (text.startswith("{") or text.startswith("[")):
            data = json.loads(text)
            # 检测 session 过期
            if isinstance(data, dict) and data.get("code") in (
                "ERR_GLOBAL_SESSION_EXPIRED", "ERR_SESSION_EXPIRED",
                "ERR_NOT_LOGIN",
            ):
                raise ValueError(f"session expired: {data.get('code')}")
            return data
        raise ValueError(
            f"response is not JSON, status={resp.status_code}, "
            f"content_type={resp.headers.get('content-type')}"
        )


async def _query_sellersprite(keyword: str, market: str) -> dict:
    cookie = _get_cookie()
    for attempt in range(2):
        try:
            return await _request_sellersprite(keyword, market, cookie)
        except ValueError:
            if attempt == 0:
                logger.warning("cookie 已过期,自动刷新中...")
                cookie = await _auto_refresh_cookie()
            else:
                raise HTTPException(
                    status_code=401,
                    detail="卖家精灵 cookie 自动刷新失败,请手动运行: "
                           "backend/venv/bin/python scripts/refresh_sellersprite_cookie.py"
                )


@router.get("/search", response_model=ApiResponse)
async def search(keyword: str = Query(..., min_length=1),
                 max_pages: int = Query(default=2, ge=1, le=5),
                 max_valid: int = Query(default=5, ge=1, le=20)):
    if _search_lock.locked():
        raise HTTPException(status_code=429, detail="当前有搜索任务正在执行，请稍后再试")
    async with _search_lock:
        results = await scrape_amazon_products(
            keyword=keyword,
            max_pages=max_pages,
            max_valid=max_valid,
            headless=True,
        )
    return ApiResponse(data={"keyword": keyword, "products": results})


@router.get("/sellersprite", response_model=ApiResponse)
async def sellersprite_search(keyword: str = Query(..., min_length=1),
                               market: str = Query(default="US")):
    try:
        data = await _query_sellersprite(keyword, market)
        return ApiResponse(data=data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
