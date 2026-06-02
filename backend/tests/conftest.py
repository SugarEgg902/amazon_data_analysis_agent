# backend/tests/conftest.py
import sys
import os
import pytest
from fastapi.testclient import TestClient

# 让 `import backend.*` 可用（仓库根加入 path）
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from backend.main import app  # noqa: E402


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c
