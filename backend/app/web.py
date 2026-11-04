"""Serves the web copy of the side panel (built by `npm run build:web`, see backend/Dockerfile) under /app/, when it is there.

Anyone may load the page. The access token it needs for the API comes from `/app/config.js`, so no secret sits in the built
files; the API calls the page makes still carry the token (backend/app/access.py).
"""
import json
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import RedirectResponse, Response
from fastapi.staticfiles import StaticFiles

DEFAULT_DIR = Path(__file__).resolve().parent.parent / "web"


def install_web(app: FastAPI, web_dir: Path | None = None, token: str | None = None) -> bool:
    web_dir = web_dir or Path(os.getenv("WEB_DIR") or DEFAULT_DIR)
    if not (web_dir / "index.html").is_file():
        return False

    @app.get("/", include_in_schema=False)
    def web_root():
        return RedirectResponse("/app/")

    @app.get("/app/config.js", include_in_schema=False)
    def web_config():
        value = os.getenv("ACCESS_TOKEN", "") if token is None else token
        body = "window.__SCAMCOPILOT__ = " + json.dumps({"token": value}) + ";\n"
        return Response(body, media_type="text/javascript", headers={"Cache-Control": "no-store"})

    app.mount("/app", StaticFiles(directory=web_dir, html=True), name="web")  # after config.js: the first match wins
    return True
