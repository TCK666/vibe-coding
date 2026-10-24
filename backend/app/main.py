"""应用入口。

启动: .venv/Scripts/python -m uvicorn app.main:app --app-dir backend --port 8000 --reload
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import api_router
from .core.config import get_settings
from .core.errors import BizError, biz_error_handler, unhandled_error_handler
from .db.session import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


def create_app() -> FastAPI:
    s = get_settings()
    app = FastAPI(title=s.app_name, lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[s.frontend_base_url, "http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(api_router)
    app.add_exception_handler(BizError, biz_error_handler)
    app.add_exception_handler(Exception, unhandled_error_handler)

    @app.get("/healthz", tags=["meta"], summary="健康检查")
    async def healthz():
        return {"status": "ok", "service": s.app_name}

    return app


app = create_app()
