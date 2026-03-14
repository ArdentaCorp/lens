import json
import logging
import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.database import get_db
from app.models.image import Image
from app.models.image_analysis import ImageAnalysis
from app.schemas.schemas import (
    ImageDetailOut,
    ImageOut,
    ImportFolderRequest,
    ImportFolderResponse,
)
from app.services.embeddings import build_embedding_text, build_search_text, get_embedding
from app.services.exif import extract_exif
from app.services.hashing import compute_phash
from app.services.vision import analyze_image as vision_analyze

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/images", tags=["images"])

ALLOWED_EXTENSIONS = {".jpg", ".jpeg",
                      ".png", ".gif", ".bmp", ".webp", ".tiff"}


def _safe_filename(filename: str) -> str:
    stem = Path(filename).stem
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400, detail=f"File type {suffix} not allowed")
    return f"{stem}_{uuid.uuid4().hex[:8]}{suffix}"


@router.get("", response_model=list[ImageOut])
async def list_images(
    skip: int = 0,
    limit: int = 50,
    source: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Image).offset(skip).limit(
        limit).order_by(Image.created_at.desc())
    if source:
        stmt = stmt.where(Image.source == source)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/{image_id}", response_model=ImageDetailOut)
async def get_image(image_id: int, db: AsyncSession = Depends(get_db)):
    stmt = (
        select(Image)
        .options(selectinload(Image.analysis))
        .where(Image.id == image_id)
    )
    result = await db.execute(stmt)
    image = result.scalar_one_or_none()
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")
    return image


@router.post("/upload", response_model=list[ImageOut])
async def upload_images(
    files: list[UploadFile],
    source: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    uploaded: list[Image] = []
    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)

    for file in files:
        if not file.filename:
            continue
        safe_name = _safe_filename(file.filename)
        dest = upload_dir / safe_name
        with open(dest, "wb") as f:
            shutil.copyfileobj(file.file, f)

        # Extract EXIF and compute perceptual hash
        exif = extract_exif(str(dest))
        phash = compute_phash(str(dest))

        img = Image(
            filename=file.filename,
            source=source,
            image_path=str(dest),
            phash=phash,
            exif_data=json.dumps(exif) if exif else None,
        )
        db.add(img)
        uploaded.append(img)

    await db.commit()
    for img in uploaded:
        await db.refresh(img)

    # Auto-analyze uploaded images
    for img in uploaded:
        try:
            parsed = await vision_analyze(img.image_path)
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
                logger.warning("Embedding failed for image %s: %s", img.id, e)

            search_text = build_search_text(parsed)
            db.add(ImageAnalysis(
                image_id=img.id,
                detected_objects=detected_objects,
                attributes=attributes,
                embedding=embedding_json,
                search_text=search_text,
                confidence=1.0,
            ))
        except Exception as e:
            logger.error("Auto-analyze failed for image %s: %s", img.id, e)
    await db.commit()

    return uploaded


@router.post("/import-folder", response_model=ImportFolderResponse)
async def import_folder(
    body: ImportFolderRequest,
    db: AsyncSession = Depends(get_db),
):
    folder = Path(body.folder_path)
    if not folder.is_dir():
        raise HTTPException(status_code=400, detail="Folder does not exist")

    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)

    imported_names: list[str] = []
    for file_path in sorted(folder.iterdir()):
        if file_path.suffix.lower() not in ALLOWED_EXTENSIONS:
            continue
        safe_name = _safe_filename(file_path.name)
        dest = upload_dir / safe_name
        shutil.copy2(file_path, dest)

        # Extract EXIF and compute perceptual hash
        exif = extract_exif(str(dest))
        phash = compute_phash(str(dest))

        img = Image(
            filename=file_path.name,
            source=body.source,
            image_path=str(dest),
            phash=phash,
            exif_data=json.dumps(exif) if exif else None,
        )
        db.add(img)
        imported_names.append(file_path.name)

    await db.commit()

    # Auto-analyze imported images
    stmt = select(Image).where(Image.filename.in_(imported_names))
    result = await db.execute(stmt)
    new_images = result.scalars().all()
    for img in new_images:
        try:
            parsed = await vision_analyze(img.image_path)
            detected_objects = json.dumps(parsed.get("detected_objects", []))
            attrs = parsed.get("attributes", {})
            if "description" in parsed:
                attrs["description"] = parsed["description"]
            if "classification" in parsed:
                attrs["classification"] = parsed["classification"]
            attributes = json.dumps(attrs)

            embedding_json = None
            try:
                emb_text = build_embedding_text(parsed)
                emb_vec = await get_embedding(emb_text)
                embedding_json = json.dumps(emb_vec)
            except Exception as e:
                logger.warning("Embedding failed for image %s: %s", img.id, e)

            search_text = build_search_text(parsed)
            db.add(ImageAnalysis(
                image_id=img.id,
                detected_objects=detected_objects,
                attributes=attributes,
                embedding=embedding_json,
                search_text=search_text,
                confidence=1.0,
            ))
        except Exception as e:
            logger.error("Auto-analyze failed for image %s: %s", img.id, e)
    await db.commit()

    return ImportFolderResponse(imported=len(imported_names), filenames=imported_names)


@router.delete("/{image_id}", status_code=204)
async def delete_image(image_id: int, db: AsyncSession = Depends(get_db)):
    stmt = select(Image).where(Image.id == image_id)
    result = await db.execute(stmt)
    image = result.scalar_one_or_none()
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")

    # Remove file from disk
    path = Path(image.image_path)
    if path.exists():
        path.unlink()

    await db.delete(image)
    await db.commit()
