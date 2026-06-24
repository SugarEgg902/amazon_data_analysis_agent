# backend/Dockerfile
# Build context is the repo root (see docker-compose.yml: context: .)
FROM python:3.11-slim

WORKDIR /app

# 系统依赖(部分 Python 包需要)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc default-libmysqlclient-dev pkg-config \
    && rm -rf /var/lib/apt/lists/*

# 安装后端依赖(单独一层,利用缓存)
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# 后端源码 + 启动脚本 + 配置
COPY backend ./backend
COPY run.py ./run.py
COPY config ./config

# 预构建的前端静态文件(打包前先 npm run build)
COPY frontend/dist ./frontend/dist

# 数据库迁移脚本(MySQL 容器启动时自动执行)
COPY db/migrations ./db/migrations

EXPOSE 8001
# 用 run.py 启动(含 sys.path 修正 + uvicorn access log 格式)
CMD ["python", "run.py", "--port", "8001"]
