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
    port = 1332
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
        # 必须绑 0.0.0.0:钉钉消息里的图表是每个查看者的客户端自己去拉
        # PUBLIC_BASE_URL 的,只绑 127.0.0.1 的话内网设备也拉不到,图会全裂。
        host="0.0.0.0",
        port=port,
        reload=reload,
        # 同时监听 backend/ 和 config/,改配置文件也能自动重载
        reload_dirs=[os.path.join(REPO_ROOT, "backend"),
                     os.path.join(REPO_ROOT, "config")] if reload else None,
        log_config=log_config,
    )

