"""FastAPI 应用入口 + 托管前端。"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from . import config
from .api import init as init_api
from .api import router
from .converter import MinerUConverter
from .jobs import JobManager


def create_app() -> FastAPI:
    config.ensure_dirs()
    app = FastAPI(title="any2md", version="1.0.0")

    init_api(JobManager(MinerUConverter()))

    # /api 与 /health 先注册
    app.include_router(router)

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    # 最后再把前端挂到 "/"，作为兜底静态服务（不会遮挡 /api）
    app.mount("/", StaticFiles(directory=config.FRONTEND_DIR, html=True), name="frontend")
    return app


app = create_app()
