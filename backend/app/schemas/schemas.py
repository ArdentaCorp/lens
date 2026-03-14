from datetime import datetime

from pydantic import BaseModel


# ── Image ──────────────────────────────────────────────

class ImageOut(BaseModel):
    id: int
    filename: str
    source: str | None = None
    image_path: str
    phash: str | None = None
    exif_data: str | None = None
    created_at: datetime
    ingested_at: datetime | None = None

    model_config = {"from_attributes": True}


# ── Image Analysis ─────────────────────────────────────

class ImageAnalysisOut(BaseModel):
    id: int
    image_id: int
    detected_objects: str | None = None
    attributes: str | None = None
    confidence: float | None = None
    analyzed_at: datetime

    model_config = {"from_attributes": True}


class ImageDetailOut(ImageOut):
    analysis: ImageAnalysisOut | None = None


# ── Search ─────────────────────────────────────────────

class SearchRequest(BaseModel):
    query: str
    source: str | None = None
    object_type: str | None = None
    color: str | None = None
    semantic: bool = True  # Enable semantic (embedding) search


class SearchResult(BaseModel):
    images: list[ImageDetailOut]
    total: int
    search_method: str | None = None  # "fts", "semantic", "keyword", "hybrid"


# ── Investigation ──────────────────────────────────────

class InvestigateRequest(BaseModel):
    query: str


class InvestigateResponse(BaseModel):
    id: int
    query: str
    matched_image_ids: str | None = None
    summary: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Import ─────────────────────────────────────────────

class ImportFolderRequest(BaseModel):
    folder_path: str
    source: str | None = None


class ImportFolderResponse(BaseModel):
    imported: int
    filenames: list[str]


# ── Generic ────────────────────────────────────────────

# ── Duplicates ─────────────────────────────────────────

class DuplicateGroup(BaseModel):
    images: list[ImageOut]
    phash: str
    distance: int


class DuplicatesResponse(BaseModel):
    groups: list[DuplicateGroup]
    total_duplicates: int


class HealthResponse(BaseModel):
    status: str
    version: str
