import json
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.image import Image
from app.models.image_analysis import ImageAnalysis
from app.schemas.schemas import ImageAnalysisOut
from app.services.embeddings import build_embedding_text, build_search_text, get_embedding
from app.services.exif import extract_exif
from app.services.hashing import compute_phash
from app.services.vision import analyze_image as vision_analyze

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/images", tags=["analysis"])


@router.post("/{image_id}/analyze", response_model=ImageAnalysisOut)
async def analyze_image(image_id: int, db: AsyncSession = Depends(get_db)):
    stmt = (
        select(Image)
        .options(selectinload(Image.analysis))
        .where(Image.id == image_id)
    )
    result = await db.execute(stmt)
    image = result.scalar_one_or_none()
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")

    # Call vision model
    try:
        parsed = await vision_analyze(image.image_path)
    except Exception as e:
        logger.error("Vision analysis failed for image %s: %s", image_id, e)
        raise HTTPException(
            status_code=502, detail=f"Vision analysis failed: {e}")

    detected_objects = json.dumps(parsed.get("detected_objects", []))
    attrs = parsed.get("attributes", {})
    # Fold extra top-level fields into attributes for searchability
    if "description" in parsed:
        attrs["description"] = parsed["description"]
    if "classification" in parsed:
        attrs["classification"] = parsed["classification"]
    attributes = json.dumps(attrs)

    # Compute embedding
    embedding_json = None
    try:
        emb_text = build_embedding_text(parsed)
        emb_vec = await get_embedding(emb_text)
        embedding_json = json.dumps(emb_vec)
    except Exception as e:
        logger.warning("Embedding failed for image %s: %s", image_id, e)

    # Backfill exif + phash if missing
    if not image.phash:
        image.phash = compute_phash(image.image_path)
    if not image.exif_data:
        exif = extract_exif(image.image_path)
        if exif:
            image.exif_data = json.dumps(exif)

    search_text = build_search_text(parsed)

    if image.analysis:
        image.analysis.detected_objects = detected_objects
        image.analysis.attributes = attributes
        image.analysis.embedding = embedding_json
        image.analysis.search_text = search_text
        image.analysis.confidence = 1.0
    else:
        analysis = ImageAnalysis(
            image_id=image.id,
            detected_objects=detected_objects,
            attributes=attributes,
            embedding=embedding_json,
            search_text=search_text,
            confidence=1.0,
        )
        db.add(analysis)

    await db.commit()

    # Re-fetch to return
    stmt2 = select(ImageAnalysis).where(ImageAnalysis.image_id == image_id)
    result2 = await db.execute(stmt2)
    return result2.scalar_one()


@router.post("/reindex", response_model=dict)
async def reindex_all(db: AsyncSession = Depends(get_db)):
    stmt = select(Image)
    result = await db.execute(stmt)
    images = result.scalars().all()

    count = 0
    errors = 0
    for image in images:
        try:
            parsed = await vision_analyze(image.image_path)
        except Exception as e:
            logger.error(
                "Vision analysis failed for image %s: %s", image.id, e)
            errors += 1
            continue

        detected_objects = json.dumps(parsed.get("detected_objects", []))
        attrs = parsed.get("attributes", {})
        if "description" in parsed:
            attrs["description"] = parsed["description"]
        if "classification" in parsed:
            attrs["classification"] = parsed["classification"]
        attributes = json.dumps(attrs)

        # Compute embedding
        embedding_json = None
        try:
            emb_text = build_embedding_text(parsed)
            emb_vec = await get_embedding(emb_text)
            embedding_json = json.dumps(emb_vec)
        except Exception as e:
            logger.warning("Embedding failed for image %s: %s", image.id, e)

        # Backfill exif + phash
        if not image.phash:
            image.phash = compute_phash(image.image_path)
        if not image.exif_data:
            exif = extract_exif(image.image_path)
            if exif:
                image.exif_data = json.dumps(exif)

        existing = await db.execute(
            select(ImageAnalysis).where(ImageAnalysis.image_id == image.id)
        )
        analysis = existing.scalar_one_or_none()

        search_text = build_search_text(parsed)

        if analysis:
            analysis.detected_objects = detected_objects
            analysis.attributes = attributes
            analysis.embedding = embedding_json
            analysis.search_text = search_text
            analysis.confidence = 1.0
        else:
            db.add(
                ImageAnalysis(
                    image_id=image.id,
                    detected_objects=detected_objects,
                    attributes=attributes,
                    embedding=embedding_json,
                    search_text=search_text,
                    confidence=1.0,
                )
            )
        count += 1

    await db.commit()
    return {"reindexed": count, "errors": errors}
