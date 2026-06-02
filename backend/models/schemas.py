# backend/models/schemas.py
from pydantic import BaseModel
from typing import Any, Optional


class ApiResponse(BaseModel):
    data: Any
    error: Optional[str] = None
