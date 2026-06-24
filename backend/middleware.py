# backend/middleware.py
import logging
import time
from datetime import datetime
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("api_access")


def _get_client_ip(request: Request) -> str:
    # 优先从代理头取真实 IP, fallback 到直连 client
    for h in ("x-forwarded-for", "x-real-ip"):
        v = request.headers.get(h)
        if v:
            return v.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


class AccessLogMiddleware(BaseHTTPMiddleware):
    """记录每个 API 请求的方法/路径/IP/状态码/耗时(毫秒)。"""

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        # 只记录 /api 开头的请求,跳过静态资源
        if not path.startswith("/api"):
            return await call_next(request)

        start = time.perf_counter()
        method = request.method
        ip = _get_client_ip(request)

        try:
            response = await call_next(request)
            cost_ms = int((time.perf_counter() - start) * 1000)
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            logger.info(
                "%s | %s %s | IP=%s | status=%s | %dms",
                ts, method, path, ip, response.status_code, cost_ms,
            )
            return response
        except Exception as e:
            cost_ms = int((time.perf_counter() - start) * 1000)
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            logger.info(
                "%s | %s %s | IP=%s | ERROR | %dms | %s",
                ts, method, path, ip, cost_ms, e,
            )
            raise
