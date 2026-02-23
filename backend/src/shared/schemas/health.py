from __future__ import annotations

from pydantic import BaseModel


class HealthCheckResponse(BaseModel):
    status: str
    database: bool
    version: str
