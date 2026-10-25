from fastapi import FastAPI

from app.api import api_router
from app.config import get_settings
from app.errors import register_error_handlers
from app.upload_limit import UploadSizeLimit


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
    app.add_middleware(UploadSizeLimit, path_prefix="/api/v1/cv-versions", max_bytes=get_settings().cv_max_bytes)
    app.include_router(api_router, prefix="/api/v1")
    return app


app = create_app()
