from fastapi import APIRouter

from src.api.endpoints import router as health_router

router = APIRouter(prefix="/api")
router.include_router(health_router, tags=["health"])
