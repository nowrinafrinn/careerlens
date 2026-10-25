from fastapi import FastAPI

from app.api import api_router
from app.errors import register_error_handlers


def create_app() -> FastAPI:
    app = FastAPI(
        title="CareerLens API",
        version="0.1.0",
        # Under /api so the docs are also reachable through the Next.js proxy.
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        redoc_url=None,
    )
    register_error_handlers(app)
    app.include_router(api_router, prefix="/api/v1")
    return app


app = create_app()
