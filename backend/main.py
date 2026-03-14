import logging
import sys
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import ensure_dirs, settings
from app.database import engine
from app.models import Base
from app.routes import analysis, health, images, search
from app.services.fts import init_fts

# ── Structured logging ─────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger("lens")


async def _add_column_if_missing(conn, table: str, column: str, col_type: str) -> None:
    """Add a column to a table if it doesn't exist yet (SQLite migration)."""
    result = await conn.execute(text(f"PRAGMA table_info({table})"))
    columns = [row[1] for row in result.fetchall()]
    if column not in columns:
        await conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_dirs()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Migrate new columns onto existing tables
        await _add_column_if_missing(conn, "images", "phash", "VARCHAR")
        await _add_column_if_missing(conn, "images", "exif_data", "TEXT")
        await _add_column_if_missing(conn, "image_analyses", "embedding", "TEXT")
        await _add_column_if_missing(conn, "image_analyses", "search_text", "TEXT")
        # Init FTS5 virtual table and triggers
        await init_fts(conn)
    yield


app = FastAPI(
    title="Lens – Image Intelligence API",
    version="0.2.0",
    lifespan=lifespan,
)


# ── Request ID middleware ───────────────────────────────
class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        req_id = request.headers.get("X-Request-ID", uuid.uuid4().hex[:12])
        request.state.request_id = req_id
        response: Response = await call_next(request)
        response.headers["X-Request-ID"] = req_id
        return response


app.add_middleware(RequestIDMiddleware)


# ── API key auth middleware ─────────────────────────────
if settings.api_key:
    class APIKeyMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next):
            # Allow health and static without auth
            if request.url.path in ("/health", "/docs", "/openapi.json", "/redoc") or request.url.path.startswith("/static/"):
                return await call_next(request)
            key = request.headers.get("X-API-Key", "")
            if key != settings.api_key:
                return JSONResponse(status_code=401, content={"detail": "Invalid or missing API key"})
            return await call_next(request)

    app.add_middleware(APIKeyMiddleware)
    logger.info("API key auth enabled")

# Serve uploaded images as static files
upload_path = Path(settings.upload_dir)
upload_path.mkdir(parents=True, exist_ok=True)
app.mount("/static/uploads",
          StaticFiles(directory=str(upload_path)), name="uploads")

app.include_router(images.router)
app.include_router(analysis.router)
app.include_router(search.router)
app.include_router(health.router)


if __name__ == "__main__":
    main()
