"""Text embedding service for semantic search via OpenRouter."""
import logging

from openai import AsyncOpenAI

from app.config import settings

logger = logging.getLogger(__name__)

_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(
            api_key=settings.openrouter_api_key,
            base_url=settings.openrouter_base_url,
        )
    return _client


async def get_embedding(text: str) -> list[float]:
    """Get a text embedding vector from the embedding model."""
    client = _get_client()
    response = await client.embeddings.create(
        model=settings.embedding_model,
        input=text,
    )
    return response.data[0].embedding


# ── Gender / person synonym groups ────────────────────
# Each group maps a canonical gender to all search terms that should match.
GENDER_SYNONYMS: dict[str, list[str]] = {
    "male":   ["man", "men", "boy", "guy", "gentleman"],
    "female": ["woman", "women", "girl", "lady"],
}

# Reverse lookup: any synonym word → set of all related words
_SYNONYM_EXPAND: dict[str, set[str]] = {}
for _gender, _words in GENDER_SYNONYMS.items():
    _all = {_gender} | set(_words)
    for _w in _all:
        _SYNONYM_EXPAND[_w] = _all


def expand_query(query: str) -> str:
    """Expand a search query with gender/person synonyms.

    Example: 'girl with hat' → 'girl woman women female lady with hat'
    """
    words = query.lower().split()
    expanded: list[str] = []
    seen: set[str] = set()
    for w in words:
        if w not in seen:
            expanded.append(w)
            seen.add(w)
        synonyms = _SYNONYM_EXPAND.get(w, set())
        for s in synonyms:
            if s not in seen:
                expanded.append(s)
                seen.add(s)
    return " ".join(expanded)


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(x * x for x in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def build_embedding_text(analysis_data: dict) -> str:
    """Build a single text string from analysis data for embedding."""
    import json

    parts: list[str] = []

    # Detected objects
    objects = analysis_data.get("detected_objects", [])
    if isinstance(objects, str):
        try:
            objects = json.loads(objects)
        except json.JSONDecodeError:
            objects = []
    if objects:
        parts.append("Objects: " + ", ".join(objects))

    # Attributes
    attrs = analysis_data.get("attributes", {})
    if isinstance(attrs, str):
        try:
            attrs = json.loads(attrs)
        except json.JSONDecodeError:
            attrs = {}

    if isinstance(attrs, dict):
        scene = attrs.get("scene", "")
        if scene:
            parts.append(f"Scene: {scene}")

        colors = attrs.get("colors", [])
        if colors:
            parts.append(f"Colors: {', '.join(colors)}")

        tags = attrs.get("tags", [])
        if tags:
            parts.append(f"Tags: {', '.join(tags)}")

        description = attrs.get("description", "")
        if description:
            parts.append(f"Description: {description}")

        spatial = attrs.get("spatial", "")
        if spatial:
            parts.append(f"Spatial: {spatial}")

        materials = attrs.get("materials", [])
        if materials:
            parts.append(f"Materials: {', '.join(materials)}")

        # Classification
        classification = attrs.get("classification", {})
        if isinstance(classification, dict):
            for cat, data in classification.items():
                items = data if isinstance(data, list) else [data]
                for item in items:
                    if isinstance(item, dict):
                        flat = ", ".join(f"{k}: {v}" for k, v in item.items()
                                         if k != "confidence")
                        parts.append(f"{cat}: {flat}")

    return "\n".join(parts)


def build_search_text(analysis_data: dict) -> str:
    """Build clean plaintext for FTS indexing. No JSON syntax, just words."""
    import json

    tokens: list[str] = []

    # Detected objects — each one is a descriptive phrase
    objects = analysis_data.get("detected_objects", [])
    if isinstance(objects, str):
        try:
            objects = json.loads(objects)
        except json.JSONDecodeError:
            objects = []
    for obj in objects:
        tokens.append(str(obj))

    # Attributes
    attrs = analysis_data.get("attributes", {})
    if isinstance(attrs, str):
        try:
            attrs = json.loads(attrs)
        except json.JSONDecodeError:
            attrs = {}

    if isinstance(attrs, dict):
        for key in ("scene", "description", "spatial"):
            val = attrs.get(key, "")
            if val:
                tokens.append(str(val))

        for key in ("colors", "tags", "materials"):
            val = attrs.get(key, [])
            if isinstance(val, list):
                tokens.extend(str(v) for v in val)

        # Classification — flatten all values into words
        classification = attrs.get("classification", {})
        if isinstance(classification, dict):
            for cat, data in classification.items():
                tokens.append(cat.replace("_", " "))
                items = data if isinstance(data, list) else [data]
                for item in items:
                    if isinstance(item, dict):
                        for k, v in item.items():
                            if k == "confidence":
                                continue
                            if isinstance(v, list):
                                tokens.extend(str(x) for x in v)
                            else:
                                tokens.append(str(v))
                            # Add gender synonyms for searchability
                            if k == "gender":
                                g = str(v).lower()
                                if g in GENDER_SYNONYMS:
                                    tokens.extend(GENDER_SYNONYMS[g])

    return " ".join(tokens)
