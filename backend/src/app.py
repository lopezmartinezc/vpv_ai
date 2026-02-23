from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.core.config import settings
from src.core.database import engine
from src.core.exceptions import (
    AuthorizationError,
    BusinessRuleError,
    NotFoundError,
    VPVError,
)
from src.core.logging import setup_logging


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    setup_logging()
    yield
    await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        docs_url="/api/docs" if settings.debug else None,
        redoc_url="/api/redoc" if settings.debug else None,
        openapi_url="/api/openapi.json" if settings.debug else None,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(VPVError)
    async def vpv_exception_handler(request: Request, exc: VPVError) -> JSONResponse:
        status_map = {
            NotFoundError: 404,
            AuthorizationError: 403,
            BusinessRuleError: 422,
        }
        status_code = status_map.get(type(exc), 500)
        return JSONResponse(
            status_code=status_code,
            content={"code": exc.code, "message": exc.message},
        )

    from src.features.health.router import router as health_router
    from src.features.seasons.router import router as seasons_router

    app.include_router(health_router, prefix="/api")
    app.include_router(seasons_router, prefix="/api")

    return app


app = create_app()
