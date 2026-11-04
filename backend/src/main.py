from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.api.router import router
from src.core.config import Settings
from src.core.database import create_database_engine


def create_app(settings: Settings | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        configuration = settings if settings is not None else Settings()
        engine = create_database_engine(configuration)
        app.state.database_engine = engine
        app.title = configuration.app_name
        try:
            yield
        finally:
            engine.dispose()

    application = FastAPI(title="Emporio da Musica API", lifespan=lifespan)
    application.include_router(router)
    return application


app = create_app()
