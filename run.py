#!/usr/bin/env python
"""CWD-independent launcher. Run from anywhere:

    backend/venv/bin/python run.py            # production (serves built frontend + API)
    backend/venv/bin/python run.py --reload   # dev (auto-reload backend)

Inserts the repo root onto sys.path so `import backend.*` always resolves,
regardless of the directory you launch from or which uvicorn is on PATH.
"""
import os
import sys
import logging

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, REPO_ROOT)

if __name__ == "__main__":
    import uvicorn

    reload = "--reload" in sys.argv
    port = 8001
    for i, a in enumerate(sys.argv):
        if a == "--port" and i + 1 < len(sys.argv):
            port = int(sys.argv[i + 1])

    # 配置 uvicorn access log 格式: 时间 | 方法 路径 | IP:端口 | 状态码 | 协议
    log_config = uvicorn.config.LOGGING_CONFIG
    log_config["formatters"]["access"]["fmt"] = (
        "%(asctime)s | %(client_addr)s | \"%(request_line)s\" | %(status_code)s | %(msecs)dms"
    )
    log_config["formatters"]["access"]["datefmt"] = "%Y-%m-%d %H:%M:%S"

    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=port,
        reload=reload,
        reload_dirs=[os.path.join(REPO_ROOT, "backend")] if reload else None,
        log_config=log_config,
    )

