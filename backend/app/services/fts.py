"""FTS5 full-text search helpers for SQLite."""
import logging
import re

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

logger = logging.getLogger(__name__)

# FTS5 virtual table that indexes the clean search_text column
CREATE_FTS_TABLE = """
CREATE VIRTUAL TABLE IF NOT EXISTS image_analyses_fts
USING fts5(
    image_id UNINDEXED,
    content,
    tokenize='porter unicode61'
);
"""

# Triggers to keep FTS in sync — use search_text if available, else fallback
CREATE_FTS_INSERT_TRIGGER = """
CREATE TRIGGER IF NOT EXISTS fts_ai_insert AFTER INSERT ON image_analyses
BEGIN
    INSERT INTO image_analyses_fts(image_id, content)
    VALUES (NEW.image_id, COALESCE(NEW.search_text, COALESCE(NEW.detected_objects, '') || ' ' || COALESCE(NEW.attributes, '')));
END;
"""

CREATE_FTS_UPDATE_TRIGGER = """
CREATE TRIGGER IF NOT EXISTS fts_ai_update AFTER UPDATE ON image_analyses
BEGIN
    DELETE FROM image_analyses_fts WHERE image_id = OLD.image_id;
    INSERT INTO image_analyses_fts(image_id, content)
    VALUES (NEW.image_id, COALESCE(NEW.search_text, COALESCE(NEW.detected_objects, '') || ' ' || COALESCE(NEW.attributes, '')));
END;
"""

CREATE_FTS_DELETE_TRIGGER = """
CREATE TRIGGER IF NOT EXISTS fts_ai_delete AFTER DELETE ON image_analyses
BEGIN
    DELETE FROM image_analyses_fts WHERE image_id = OLD.image_id;
END;
"""


async def init_fts(conn: AsyncConnection) -> None:
    """Create FTS5 virtual table and sync triggers. Safe to call repeatedly."""
    # Drop old triggers so they get recreated with new logic
    await conn.execute(text("DROP TRIGGER IF EXISTS fts_ai_insert;"))
    await conn.execute(text("DROP TRIGGER IF EXISTS fts_ai_update;"))
    await conn.execute(text("DROP TRIGGER IF EXISTS fts_ai_delete;"))
    for sql in [
        CREATE_FTS_TABLE,
        CREATE_FTS_INSERT_TRIGGER,
        CREATE_FTS_UPDATE_TRIGGER,
        CREATE_FTS_DELETE_TRIGGER,
    ]:
        await conn.execute(text(sql))
    logger.info("FTS5 index initialized")


async def rebuild_fts(conn: AsyncConnection) -> None:
    """Rebuild FTS index from existing data."""
    await conn.execute(text("DELETE FROM image_analyses_fts;"))
    await conn.execute(text("""
        INSERT INTO image_analyses_fts(image_id, content)
        SELECT image_id,
               COALESCE(search_text, COALESCE(detected_objects, '') || ' ' || COALESCE(attributes, ''))
        FROM image_analyses;
    """))
    logger.info("FTS5 index rebuilt")


def _sanitize_fts_query(query: str) -> str:
    """Sanitize a user query for safe use in FTS5 MATCH."""
    # Remove characters that have special meaning in FTS5
    cleaned = re.sub(r'[^\w\s]', ' ', query)
    return cleaned.strip()


async def fts_search(conn: AsyncConnection, query: str, use_or: bool = False) -> list[tuple[int, float]]:
    """Search FTS index. Returns list of (image_id, bm25_score) ranked by relevance.

    use_or: if True, words are joined with OR (any word matches).
            if False, words are joined with AND (all words must match).
    """
    cleaned = _sanitize_fts_query(query)
    words = cleaned.split()
    if not words:
        return []

    joiner = " OR " if use_or else " AND "

    # Build FTS query: exact word match (no prefix) to avoid
    # "car" matching "cartoon", "card", etc.
    fts_query = joiner.join(f'"{w}"' for w in words)

    try:
        result = await conn.execute(
            text("""
                SELECT image_id, bm25(image_analyses_fts) as score
                FROM image_analyses_fts
                WHERE image_analyses_fts MATCH :query
                ORDER BY score
                LIMIT 100
            """),
            {"query": fts_query},
        )
        return [(row[0], row[1]) for row in result.fetchall()]
    except Exception as e:
        logger.warning("FTS query failed for '%s': %s", fts_query, e)
        return []
