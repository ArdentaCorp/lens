import json
import logging
import re

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import engine, get_db
from app.models.image import Image
from app.models.investigation import InvestigationRecord
from app.schemas.schemas import (
    DuplicateGroup,
    DuplicatesResponse,
    ImageDetailOut,
    ImageOut,
    InvestigateRequest,
    InvestigateResponse,
    SearchRequest,
    SearchResult,
)
from app.services.embeddings import cosine_similarity, expand_query, get_embedding
from app.services.fts import fts_search
from app.services.hashing import are_duplicates
from app.services.llm import extract_search_keywords, generate_investigation_summary

logger = logging.getLogger(__name__)

router = APIRouter(tags=["search"])

# ── Scoring weights ────────────────────────────────────
FTS_AND_WEIGHT = 1.5   # Strict FTS match (all words)
FTS_OR_WEIGHT = 0.6    # Relaxed FTS match (any word)
SEMANTIC_WEIGHT = 1.0  # Embedding cosine similarity
KEYWORD_WEIGHT = 0.4   # Simple keyword/substring match
PRIMARY_BONUS = 0.6    # Bonus when query matches primary detected_objects
SEMANTIC_THRESHOLD = 0.40  # Minimum cosine similarity to count
MIN_SCORE = 0.25       # Minimum combined score to include in results


# ── Keyword scoring ────────────────────────────────────

def _keyword_score(query_lower: str, objects_str: str, attrs_str: str) -> float:
    """Score how well the query matches via whole-word matching.
    Returns 0.0 (no match) to 1.0 (all words match).
    """
    if not query_lower:
        return 1.0
    words = query_lower.split()
    combined = objects_str + " " + attrs_str
    matched = sum(1 for w in words if re.search(
        r'\b' + re.escape(w) + r'\b', combined))
    if matched == 0:
        return 0.0
    return matched / len(words)


# ── Hybrid search ──────────────────────────────────────

@router.post("/search/images", response_model=SearchResult)
async def search_images(body: SearchRequest, db: AsyncSession = Depends(get_db)):
    query_lower = body.query.lower().strip()
    expanded_query = expand_query(query_lower)
    scores: dict[int, float] = {}  # image_id -> combined relevance score
    methods_used: set[str] = set()

    # ── 1) FTS5 full-text search (strict AND) ──────────
    try:
        async with engine.connect() as conn:
            fts_and_results = await fts_search(conn, expanded_query, use_or=False)
            for img_id, bm25 in fts_and_results:
                # bm25 scores are negative (more negative = better match)
                normalized = min(1.0, abs(bm25) / 10.0)
                scores[img_id] = scores.get(
                    img_id, 0) + normalized * FTS_AND_WEIGHT
            if fts_and_results:
                methods_used.add("fts")

            # ── 1b) FTS5 relaxed OR (broaden results) ─
            fts_or_results = await fts_search(conn, expanded_query, use_or=True)
            for img_id, bm25 in fts_or_results:
                if img_id not in scores:  # Only add new ones
                    normalized = min(1.0, abs(bm25) / 10.0)
                    scores[img_id] = scores.get(
                        img_id, 0) + normalized * FTS_OR_WEIGHT
                    methods_used.add("fts")
    except Exception as e:
        logger.warning("FTS search failed: %s", e)

    # ── Load all images ONCE for semantic + keyword scoring ──
    stmt = select(Image).options(selectinload(Image.analysis))
    if body.source:
        stmt = stmt.where(Image.source == body.source)
    result = await db.execute(stmt)
    all_imgs = {img.id: img for img in result.scalars().all()}

    # ── 2) Semantic (embedding) search ─────────────────
    if body.semantic:
        try:
            query_vec = await get_embedding(expanded_query)
            for img in all_imgs.values():
                if img.analysis and img.analysis.embedding:
                    try:
                        doc_vec = json.loads(img.analysis.embedding)
                        sim = cosine_similarity(query_vec, doc_vec)
                        if sim >= SEMANTIC_THRESHOLD:
                            scores[img.id] = scores.get(
                                img.id, 0) + sim * SEMANTIC_WEIGHT
                            methods_used.add("semantic")
                    except (json.JSONDecodeError, TypeError):
                        pass
        except Exception as e:
            logger.warning("Semantic search failed: %s", e)

    # ── 3) Keyword boost + primary subject bonus ─────

    for img_id, img in all_imgs.items():
        if not img.analysis:
            continue
        search_text = (img.analysis.search_text or "").lower()
        objects_str = (img.analysis.detected_objects or "").lower()
        attrs_str = (img.analysis.attributes or "").lower()
        # Use search_text if available, else fall back to raw fields
        text_to_search = search_text if search_text else (
            objects_str + " " + attrs_str)
        kw_score = _keyword_score(expanded_query, text_to_search, "")
        if kw_score > 0:
            scores[img_id] = scores.get(img_id, 0) + kw_score * KEYWORD_WEIGHT
            methods_used.add("keyword")

        # Primary subject bonus: query words in detected_objects rank higher
        primary_score = _keyword_score(expanded_query, objects_str, "")
        if primary_score > 0:
            scores[img_id] = scores.get(
                img_id, 0) + primary_score * PRIMARY_BONUS

    # ── 4) Rank and load ──────────────────────────────
    if not scores:
        return SearchResult(images=[], total=0, search_method="none")

    # Filter out weak matches (background objects, incidental mentions)
    scores = {k: v for k, v in scores.items() if v >= MIN_SCORE}
    if not scores:
        return SearchResult(images=[], total=0, search_method="none")

    ranked_ids = sorted(scores, key=lambda x: scores[x], reverse=True)

    # ── 5) Apply filters ──────────────────────────────
    final: list[Image] = []
    for img_id in ranked_ids:
        img = all_imgs.get(img_id)
        if not img or not img.analysis:
            continue
        if body.source and img.source != body.source:
            continue
        if body.object_type:
            try:
                objs = json.loads(img.analysis.detected_objects or "[]")
            except json.JSONDecodeError:
                objs = []
            if not any(body.object_type.lower() in o.lower() for o in objs):
                continue
        if body.color:
            search_text = (
                img.analysis.search_text or img.analysis.attributes or "").lower()
            if body.color.lower() not in search_text:
                continue
        final.append(img)

    # Determine method label
    if len(methods_used) > 1:
        method = "hybrid"
    elif methods_used:
        method = methods_used.pop()
    else:
        method = "none"

    return SearchResult(
        images=[ImageDetailOut.model_validate(m) for m in final],
        total=len(final),
        search_method=method,
    )


# ── Duplicates endpoint ───────────────────────────────

@router.get("/duplicates", response_model=DuplicatesResponse)
async def find_duplicates(
    threshold: int = 10,
    db: AsyncSession = Depends(get_db),
):
    """Find groups of visually similar images using perceptual hashing."""
    stmt = select(Image).where(Image.phash.is_not(None))
    result = await db.execute(stmt)
    images = result.scalars().all()

    # Group by near-duplicate clusters (simple quadratic for POC)
    visited: set[int] = set()
    groups: list[DuplicateGroup] = []

    for i, img_a in enumerate(images):
        if img_a.id in visited:
            continue
        cluster = [img_a]
        for img_b in images[i + 1:]:
            if img_b.id in visited:
                continue
            if are_duplicates(img_a.phash, img_b.phash, threshold):
                cluster.append(img_b)
                visited.add(img_b.id)
        if len(cluster) > 1:
            visited.add(img_a.id)
            groups.append(DuplicateGroup(
                images=[ImageOut.model_validate(m) for m in cluster],
                phash=img_a.phash,
                distance=0,
            ))

    return DuplicatesResponse(
        groups=groups,
        total_duplicates=sum(len(g.images) for g in groups),
    )


# ── Investigation ─────────────────────────────────────

@router.post("/investigate", response_model=InvestigateResponse)
async def investigate(body: InvestigateRequest, db: AsyncSession = Depends(get_db)):
    # Step 1: Extract search keywords from the natural language question
    try:
        keywords = await extract_search_keywords(body.query)
        logger.info("Investigation: '%s' → keywords: '%s'",
                    body.query, keywords)
    except Exception as e:
        logger.warning("Keyword extraction failed, using raw query: %s", e)
        keywords = body.query

    # Step 2: Search with extracted keywords
    search_req = SearchRequest(query=keywords)
    search_result = await search_images(search_req, db)

    matched_ids = [img.id for img in search_result.images]

    # Step 3: Build rich analysis data for the LLM (include filenames)
    analyses = []
    for img in search_result.images:
        if img.analysis:
            analyses.append({
                "filename": img.filename,
                "detected_objects": img.analysis.detected_objects,
                "attributes": img.analysis.attributes,
            })

    # Step 4: Generate investigative summary + relevance filtering
    try:
        summary, relevant_indices = await generate_investigation_summary(
            body.query, analyses)
        # Filter matched_ids to only LLM-relevant images (indices are 1-based)
        filtered_ids = [
            matched_ids[i - 1]
            for i in relevant_indices
            if 1 <= i <= len(matched_ids)
        ]
        if filtered_ids:
            matched_ids = filtered_ids
    except Exception as e:
        logger.error("LLM summary failed: %s", e)
        summary = (
            f"Found {len(matched_ids)} image(s) matching '{body.query}'. "
            f"AI summary unavailable: {e}"
        )

    record = InvestigationRecord(
        query=body.query,
        matched_image_ids=json.dumps(matched_ids),
        summary=summary,
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)

    return record
