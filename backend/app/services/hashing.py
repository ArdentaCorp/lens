"""Perceptual hashing for duplicate/near-duplicate image detection."""
import logging
from pathlib import Path

import imagehash
from PIL import Image

logger = logging.getLogger(__name__)


def compute_phash(image_path: str) -> str | None:
    """Compute a perceptual hash string for an image."""
    path = Path(image_path)
    if not path.exists():
        return None
    try:
        img = Image.open(path)
        h = imagehash.phash(img)
        img.close()
        return str(h)
    except Exception as e:
        logger.debug("Cannot compute phash: %s", e)
        return None


def hamming_distance(hash1: str, hash2: str) -> int:
    """Compute hamming distance between two hex hash strings."""
    h1 = imagehash.hex_to_hash(hash1)
    h2 = imagehash.hex_to_hash(hash2)
    return h1 - h2


def are_duplicates(hash1: str, hash2: str, threshold: int = 10) -> bool:
    """Check if two images are near-duplicates based on hash distance."""
    return hamming_distance(hash1, hash2) <= threshold
