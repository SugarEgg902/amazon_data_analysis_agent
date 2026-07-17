# backend/tests/conftest.py
import sys
import os
import pytest
from fastapi.testclient import TestClient

# 让 `import backend.*` 可用（仓库根加入 path）
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from backend.main import app  # noqa: E402
from backend.database import engine  # noqa: E402
from sqlalchemy import text  # noqa: E402


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def cleanup_anomaly_alerts():
    """异常检测测试会向生产的 anomaly_alerts 表 INSERT 且已 commit（app 走 engine.begin()，
    无法用事务回滚撤销）。以自增 id 为水位标记，测试结束后删除本次新插入的行，
    保证测试对生产数据零残留。"""
    with engine.connect() as conn:
        high_water = conn.execute(text("SELECT COALESCE(MAX(id), 0) FROM anomaly_alerts")).scalar()
    yield
    with engine.begin() as conn:
        conn.execute(
            text("DELETE FROM anomaly_alerts WHERE id > :hw"), {"hw": high_water}
        )
