from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.config import ensure_dirs, settings
from app.database import engine
from app.models import Base
from app.routes import analysis, health, images, search
from app.services.fts import init_fts


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
    title="Ardenta Image Library",
    version="0.1.0",
    lifespan=lifespan,
)

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
