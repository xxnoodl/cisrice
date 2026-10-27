import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from redis import Redis
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.core.config import Settings
from app.core.database import make_engine
from app.core.http import BodyLimitMiddleware
from app.modules.identity.routes import router as identity_router
from app.modules.operations.repository import HealthRepository
from app.modules.operations.service import check_dependencies

logger = logging.getLogger("cisrice")


def create_app(settings: Settings | None = None) -> FastAPI:
    config = settings or Settings()
    engine = make_engine(config)
    redis = Redis.from_url(
        config.redis_url,
        socket_connect_timeout=config.dependency_timeout,
        socket_timeout=config.dependency_timeout,
    )
    repository = HealthRepository(engine)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        yield
        redis.close()
        engine.dispose()

    app = FastAPI(title="Cisrice", version="0.1.0", lifespan=lifespan)
    app.state.engine = engine
    app.state.redis = redis
    app.state.settings = config
    app.add_middleware(BodyLimitMiddleware)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=config.allowed_hosts)
    app.include_router(identity_router)
    app.state.checks = {
        "postgresql": repository.ping,
        "redis": redis.ping,
        "schema": repository.schema_ready,
    }

    @app.middleware("http")
    async def correlation(request: Request, call_next: Any) -> Any:
        correlation_id = str(uuid4())
        request.state.correlation_id = correlation_id
        response = await call_next(request)
        response.headers["X-Correlation-ID"] = correlation_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Cache-Control"] = "no-store"
        logger.info("request id=%s status=%s", correlation_id, response.status_code)
        return response

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, error: RequestValidationError) -> JSONResponse:
        # Pydantic's default error payload includes input values, including passwords.
        errors = [
            {"loc": item["loc"], "msg": item["msg"], "type": item["type"]}
            for item in error.errors()
        ]
        return JSONResponse({"detail": errors}, status_code=422)

    @app.exception_handler(IntegrityError)
    async def conflict(request: Request, error: IntegrityError) -> JSONResponse:
        return JSONResponse(
            {"detail": "A record with those details already exists"}, status_code=409
        )

    @app.exception_handler(SQLAlchemyError)
    async def database_error(request: Request, error: SQLAlchemyError) -> JSONResponse:
        return JSONResponse({"detail": "Database temporarily unavailable"}, status_code=503)

    @app.get("/api/health/live")
    def live() -> dict[str, str]:
        return {"status": "ok", "version": "0.1.0"}

    @app.get("/api/health/ready")
    def ready() -> JSONResponse:
        dependencies = check_dependencies(app.state.checks)
        healthy = all(value == "ok" for value in dependencies.values())
        return JSONResponse(
            {"status": "ok" if healthy else "degraded", "dependencies": dependencies},
            status_code=200 if healthy else 503,
        )

    return app


app = create_app()
