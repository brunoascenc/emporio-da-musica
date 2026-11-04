from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: Literal["healthy", "unhealthy"]
    database: Literal["up", "down"]
    pgvector: bool
