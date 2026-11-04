import logging

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import Engine, text
from sqlalchemy.exc import SQLAlchemyError

from src.api.schemas import HealthResponse
from src.core.database import get_database_engine

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/health", response_model=HealthResponse, responses={503: {"model": HealthResponse}})
def health(
    response: Response,
    engine: Engine = Depends(get_database_engine),
) -> HealthResponse:
    try:
        with engine.connect() as connection:
            vector_version = connection.execute(
                text("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
            ).scalar_one_or_none()
    except SQLAlchemyError:
        logger.warning("Database health check failed")
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return HealthResponse(status="unhealthy", database="down", pgvector=False)

    if vector_version is None:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return HealthResponse(status="unhealthy", database="up", pgvector=False)

    return HealthResponse(status="healthy", database="up", pgvector=True)
