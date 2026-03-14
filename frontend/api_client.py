from pathlib import PurePosixPath

import requests

API_BASE = "http://localhost:8000"


def _url(path: str) -> str:
    return f"{API_BASE}{path}"


def image_url(image_path: str) -> str:
    """Convert a local image_path to a static URL served by the backend."""
    filename = PurePosixPath(image_path.replace("\\", "/")).name
    return f"{API_BASE}/static/uploads/{filename}"


# ── Health ─────────────────────────────────────────────

def health() -> dict:
    return requests.get(_url("/health"), timeout=5).json()


# ── Images ─────────────────────────────────────────────

def list_images(skip: int = 0, limit: int = 200, source: str | None = None) -> list[dict]:
    params: dict = {"skip": skip, "limit": limit}
    if source:
        params["source"] = source
    return requests.get(_url("/images"), params=params, timeout=10).json()


def get_image(image_id: int) -> dict:
    return requests.get(_url(f"/images/{image_id}"), timeout=10).json()


def upload_images(files: list[tuple], source: str | None = None) -> list[dict]:
    params = {}
    if source:
        params["source"] = source
    resp = requests.post(_url("/images/upload"),
                         files=files, params=params, timeout=60)
    resp.raise_for_status()
    return resp.json()


def import_folder(folder_path: str, source: str | None = None) -> dict:
    body: dict = {"folder_path": folder_path}
    if source:
        body["source"] = source
    resp = requests.post(_url("/images/import-folder"), json=body, timeout=60)
    resp.raise_for_status()
    return resp.json()


def delete_image(image_id: int) -> None:
    requests.delete(_url(f"/images/{image_id}"), timeout=10).raise_for_status()


# ── Analysis ───────────────────────────────────────────

def analyze_image(image_id: int) -> dict:
    resp = requests.post(_url(f"/images/{image_id}/analyze"), timeout=30)
    resp.raise_for_status()
    return resp.json()


def reindex_all() -> dict:
    resp = requests.post(_url("/images/reindex"), timeout=120)
    resp.raise_for_status()
    return resp.json()


# ── Search ─────────────────────────────────────────────

def search_images(query: str, source: str | None = None, object_type: str | None = None, color: str | None = None) -> dict:
    body: dict = {"query": query}
    if source:
        body["source"] = source
    if object_type:
        body["object_type"] = object_type
    if color:
        body["color"] = color
    resp = requests.post(_url("/search/images"), json=body, timeout=30)
    resp.raise_for_status()
    return resp.json()


# ── Investigation ──────────────────────────────────────

def investigate(query: str) -> dict:
    resp = requests.post(_url("/investigate"),
                         json={"query": query}, timeout=60)
    resp.raise_for_status()
    return resp.json()


# ── Duplicates ─────────────────────────────────────────

def find_duplicates(threshold: int = 10) -> dict:
    resp = requests.get(_url("/duplicates"),
                        params={"threshold": threshold}, timeout=30)
    resp.raise_for_status()
    return resp.json()
