import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.routers import physics, stars

WEB_DIR = Path(os.environ.get("WEB_DIR", Path(__file__).resolve().parent.parent / "web"))


def create_app(web_dir: Path = WEB_DIR) -> FastAPI:
    web_dir = Path(web_dir)
    app = FastAPI(title="Void Ranger API")

    origins = ["http://localhost:5173"]
    app_origin = os.environ.get("APP_ORIGIN")
    if app_origin:
        origins.append(app_origin)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(physics.router)
    app.include_router(stars.router)

    @app.get("/healthz")
    async def healthz():
        return {"status": "ok"}

    if web_dir.is_dir():
        app.mount("/", StaticFiles(directory=web_dir, html=True), name="web")

    return app


app = create_app()
