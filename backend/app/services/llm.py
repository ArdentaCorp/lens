import hashlib
import json
import logging

from openai import AsyncOpenAI

from app.config import settings

logger = logging.getLogger(__name__)

_client: AsyncOpenAI | None = None

# In-memory cache for keyword extraction (question hash → keywords)
_keyword_cache: dict[str, str] = {}


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(
            api_key=settings.openrouter_api_key,
            base_url=settings.openrouter_base_url,
        )
    return _client


async def extract_search_keywords(question: str) -> str:
    """Use the LLM to extract search keywords from a natural language question."""
    # Check cache first
    cache_key = hashlib.sha256(question.lower().strip().encode()).hexdigest()
    if cache_key in _keyword_cache:
        return _keyword_cache[cache_key]

    client = _get_client()
    response = await client.chat.completions.create(
        model=settings.llm_model,
        messages=[
            {"role": "system", "content": (
                "You extract search keywords from questions about images. "
                "Return ONLY the key nouns/subjects — no verbs, no filler words, no punctuation. "
                "Separate multiple keywords with spaces. Examples:\n"
                "Q: 'what happened to the red car?' → 'red car'\n"
                "Q: 'show me photos of people at the beach' → 'people beach'\n"
                "Q: 'what happen to the snowboarder' → 'snowboarder'\n"
                "Q: 'are there any flowers in the collection?' → 'flowers'\n"
                "Q: 'who is the woman in the red dress?' → 'woman red dress'"
            )},
            {"role": "user", "content": question},
        ],
        max_tokens=50,
        temperature=0.0,
    )
    keywords = (response.choices[0].message.content or question).strip()
    result = keywords if keywords else question

    # Bounded cache
    if len(_keyword_cache) >= settings.llm_cache_size:
        _keyword_cache.pop(next(iter(_keyword_cache)))
    _keyword_cache[cache_key] = result
    return result


def _parse_analysis(analysis: dict) -> tuple[list, dict]:
    """Parse objects and attributes from an analysis dict."""
    objects = analysis.get("detected_objects", "[]")
    attributes = analysis.get("attributes", "{}")
    if isinstance(objects, str):
        try:
            objects = json.loads(objects)
        except json.JSONDecodeError:
            objects = []
    if isinstance(attributes, str):
        try:
            attributes = json.loads(attributes)
        except json.JSONDecodeError:
            attributes = {}
    return objects, attributes


def _build_evidence_text(image_analyses: list[dict]) -> str:
    """Build structured evidence text from image analyses."""
    evidence_parts: list[str] = []
    for i, analysis in enumerate(image_analyses, 1):
        objects, attributes = _parse_analysis(analysis)
        filename = analysis.get("filename", f"Image {i}")

        desc = attributes.get("description", "") if isinstance(
            attributes, dict) else ""
        scene = attributes.get("scene", "") if isinstance(
            attributes, dict) else ""
        colors = attributes.get("colors", []) if isinstance(
            attributes, dict) else []
        tags = attributes.get("tags", []) if isinstance(
            attributes, dict) else []
        classification = attributes.get(
            "classification", {}) if isinstance(attributes, dict) else {}
        people = attributes.get("people", []) if isinstance(
            attributes, dict) else []

        parts = [f"Image {i} ({filename}):"]
        parts.append(
            f"  Objects: {', '.join(objects) if objects else 'none detected'}")
        parts.append(f"  Scene: {scene}")
        if desc:
            parts.append(f"  Description: {desc}")
        if colors:
            parts.append(f"  Colors: {', '.join(colors)}")
        if tags:
            parts.append(f"  Tags: {', '.join(tags)}")
        if classification:
            parts.append(f"  Classification: {json.dumps(classification)}")
        if people:
            parts.append(f"  People: {json.dumps(people)}")

        evidence_parts.append("\n".join(parts))

    return "\n\n".join(evidence_parts) if evidence_parts else "No image evidence available."


async def generate_investigation_summary(
    query: str,
    image_analyses: list[dict],
) -> tuple[str, list[int]]:
    """Given a user question and image analyses, produce a summary and list of relevant image indices (1-based)."""
    client = _get_client()

    evidence_text = _build_evidence_text(image_analyses)

    system_prompt = (
        "You are an expert image investigation assistant analyzing a collection of images.\n\n"
        "Rules:\n"
        "- Base your answer ONLY on the provided image evidence.\n"
        "- Reference images by their filename when relevant.\n"
        "- Describe what you can determine: who/what is shown, where, in what context.\n"
        "- If the question cannot be fully answered from the evidence, say what IS known and what is missing.\n"
        "- Be detailed and investigative, like writing a brief report.\n"
        "- Use bullet points or short paragraphs for clarity.\n\n"
        "IMPORTANT: You must respond in this EXACT format:\n"
        "RELEVANT_IMAGES: [comma-separated image numbers that are directly relevant to the question]\n"
        "SUMMARY:\n"
        "<your detailed summary here>\n\n"
        "Only include images that are DIRECTLY relevant to the question. "
        "If an image only tangentially relates (e.g. cars in background when asking about a specific car), exclude it."
    )

    user_prompt = f"""Investigation Question: {query}

Evidence from {len(image_analyses)} candidate image(s):

{evidence_text}

First identify which images are directly relevant to the question, then provide a detailed investigative summary."""

    response = await client.chat.completions.create(
        model=settings.llm_model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        max_tokens=1500,
        temperature=0.2,
    )

    raw = response.choices[0].message.content or ""

    # Parse RELEVANT_IMAGES and SUMMARY from the response
    relevant_indices: list[int] = []
    summary = raw

    if "RELEVANT_IMAGES:" in raw and "SUMMARY:" in raw:
        parts = raw.split("SUMMARY:", 1)
        header = parts[0]
        summary = parts[1].strip() if len(parts) > 1 else raw

        # Extract image numbers from header
        for line in header.splitlines():
            if "RELEVANT_IMAGES:" in line:
                nums_str = line.split("RELEVANT_IMAGES:", 1)[
                    1].strip().strip("[]")
                for token in nums_str.split(","):
                    token = token.strip()
                    if token.isdigit():
                        relevant_indices.append(int(token))

    # If parsing failed, assume all images are relevant
    if not relevant_indices:
        relevant_indices = list(range(1, len(image_analyses) + 1))

    return summary, relevant_indices
