# backend/database.py
from sqlalchemy import create_engine
from sqlalchemy.pool import QueuePool
from config.config import DB_HOST, DB_USER, DB_PASS, DB_NAME

# 原始 amazon 表与所有派生表同在 amazon_db，无需跨库访问。
DB_URL = f"mysql+pymysql://{DB_USER}:{DB_PASS}@{DB_HOST}/{DB_NAME}?charset=utf8mb4"

engine = create_engine(
    DB_URL,
    poolclass=QueuePool,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
)


def get_connection():
    return engine.connect()
