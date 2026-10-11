"""FastAPI application factory: API routers plus SPA static serving."""
import logging
import re
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.sessions import SessionMiddleware

from .api import api_router
from .config import OIDC_FLOW_COOKIE, get_settings
from .db import dispose_engine, session_factory
from .error_pages import render_error_page
from .log import setup_logging
from .migrate import run_migrations
from .ratelimit import limiter
from .seed import run_seed

logger = logging.getLogger(__name__)

# Paths the SPA router renders (see frontend/src/lib/stores/router.svelte.ts).
CLIENT_ROUTE = re.compile(r"(?:(?:list|stock)/[^/]+/?)?")


def _is_api(request: Request) -> bool:
    return request.url.path == "/api" or request.url.path.startswith("/api/")


@asynccontextmanager
async def lifespan(app: FastAPI):
    run_migrations()
    with session_factory()() as session:
        run_seed(session)
    yield
    dispose_engine()


def create_app() -> FastAPI:
    setup_logging()
    settings = get_settings()
    app = FastAPI(lifespan=lifespan)
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.oidc_state_secret.get_secret_value(),
        session_cookie=OIDC_FLOW_COOKIE,
        max_age=600,
        same_site="lax",
        https_only=settings.secure_cookies,
    )
    app.state.limiter = limiter

    @app.exception_handler(RateLimitExceeded)
    async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
        logger.warning(
            "rate limit exceeded: ip=%s endpoint=%s", get_remote_address(request), request.url.path
        )
        return JSONResponse(
            status_code=429,
            content={"detail": "Too many requests. Try again later."},
            headers={"Retry-After": "60"},
        )

    # API clients keep FastAPI's JSON errors; browser navigations get an HTML page.
    @app.exception_handler(StarletteHTTPException)
    async def http_error_handler(request: Request, exc: StarletteHTTPException):
        if _is_api(request):
            return await http_exception_handler(request, exc)
        return HTMLResponse(
            render_error_page(exc.status_code), status_code=exc.status_code, headers=exc.headers
        )

    @app.exception_handler(Exception)
    async def server_error_handler(request: Request, exc: Exception):
        if _is_api(request):
            return JSONResponse(status_code=500, content={"detail": "Internal Server Error"})
        return HTMLResponse(render_error_page(500), status_code=500)

    app.include_router(api_router)

    static_dir: Path = settings.static_dir.resolve()

    @app.get("/{path:path}")
    def serve_static(path: str):
        if CLIENT_ROUTE.fullmatch(path):
            return FileResponse(static_dir / "index.html")

        try:
            file_path = (static_dir / path).resolve(strict=False)
            file_path.relative_to(static_dir)
        except ValueError:
            raise HTTPException(404, "Not found") from None

        if file_path.is_file():
            return FileResponse(file_path)
        raise HTTPException(404, "Not found")

    return app


app = create_app()
