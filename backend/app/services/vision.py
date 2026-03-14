import base64
import json
from pathlib import Path

from openai import AsyncOpenAI

from app.config import settings

_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(
            api_key=settings.openrouter_api_key,
            base_url=settings.openrouter_base_url,
        )
    return _client


def _encode_image(image_path: str) -> tuple[str, str]:
    """Read an image file and return (base64_data, media_type)."""
    path = Path(image_path)
    suffix = path.suffix.lower()
    media_types = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".bmp": "image/bmp",
        ".webp": "image/webp",
        ".tiff": "image/tiff",
    }
    media_type = media_types.get(suffix, "image/jpeg")
    data = base64.b64encode(path.read_bytes()).decode("utf-8")
    return data, media_type


ANALYSIS_PROMPT = """You are an expert image analyst and forensic classifier. Examine this image with extreme thoroughness and return a JSON object with exactly these keys:

- "detected_objects": a comprehensive list of EVERY distinct object, entity, or element visible in the image. Be exhaustive and specific:
  - Include color/size/state when visible (e.g. "large red pickup truck", "small brown dog", "tall green hedge")
  - Include people descriptions (e.g. "man in blue jacket", "woman with red hat")
  - Include text/signage if readable (e.g. "stop sign", "banner reading SALE")
  - Include background elements (e.g. "overcast sky", "chain-link fence", "dirt road")
  - Include fine details others might miss (e.g. "puddle on pavement", "shadow on wall", "rust on railing")

- "attributes": an object with these keys:
  - "colors": every prominent color visible, be thorough (e.g. ["bright yellow", "dark green", "reddish brown", "gray"])
  - "scene": a detailed scene description including setting, environment, and context (e.g. "residential garden with freshly tilled soil on a sunny afternoon")
  - "tags": an extensive list of descriptive tags covering categories like:
    - setting: indoor/outdoor, urban/rural/suburban, natural/man-made
    - time: daytime/nighttime/dawn/dusk, season if apparent
    - weather: sunny/cloudy/rainy/foggy if visible
    - activity: what is happening or implied
    - mood: calm/chaotic/busy/empty
    - domain: nature/vehicle/architecture/food/people/animal/industrial etc.
    - any other relevant categorical labels
  - "materials": list of visible materials/textures (e.g. ["metal", "concrete", "fabric", "wood", "soil"])
  - "spatial": describe layout and spatial relationships (e.g. "car parked in front of building, person standing to the left")

- "classification": classify the image into one or more of these categories and provide domain-specific detail for EACH that applies:
  - "vehicle": if any vehicle is visible — identify make, model, year range, body style, color, license plate if readable, condition, and confidence 0.0-1.0 (e.g. {"make": "Toyota", "model": "Camry", "year_range": "2018-2022", "body_style": "sedan", "color": "silver", "plate": "ABC 1234", "condition": "minor front damage", "confidence": 0.8})
  - "person": if any person is visible — return a list if multiple people. For EACH person include: estimated age range, gender, apparent ethnicity or descent (e.g. "East Asian", "South Asian", "Black/African", "White/Caucasian", "Hispanic/Latino", "Middle Eastern", "Southeast Asian", "mixed/ambiguous", "unknown"), build (slim/medium/heavy), height estimate if possible (short/average/tall), clothing with colors, distinguishing features (facial hair, glasses, tattoos, scars, hairstyle, hair color), accessories (bag, watch, hat, phone), posture/action, and a confidence level 0.0-1.0 for the overall identification.
    IMPORTANT — gender field: You MUST classify gender as strictly "male" or "female" based on visible physical appearance. This is a forensic investigation tool, not a social platform — accurate physical description is critical. Only use "unknown" when the person's appearance is completely obscured (e.g. fully masked, seen only from behind at distance). NEVER use "they", "non-binary", "unspecified", or leave blank.
    (e.g. [{"age_range": "30-40", "gender": "male", "ethnicity": "South Asian", "build": "medium", "clothing": "gray hoodie, blue jeans, white sneakers", "hair": "short black", "features": "beard, sunglasses", "accessories": ["backpack", "watch"], "action": "walking", "confidence": 0.85}])
  - "brand_or_logo": if any brand, logo, label, or trademark is visible — brand name, product type, where it appears, confidence 0.0-1.0 (e.g. {"brand": "Nike", "product": "running shoes", "location": "on shoe side", "confidence": 0.95})
  - "animal": if any animal — species, breed if identifiable, color, size, behavior, confidence 0.0-1.0 (e.g. {"species": "dog", "breed": "German Shepherd", "color": "black and tan", "behavior": "sitting", "confidence": 0.9})
  - "plant": if any plant — species/common name if identifiable, type (flower/tree/shrub/crop), color, health, confidence 0.0-1.0 (e.g. {"species": "Tagetes erecta", "common_name": "African marigold", "type": "flower", "color": "yellow", "health": "blooming", "confidence": 0.9})
  - "food": if food is visible — dish name, cuisine, ingredients if visible, confidence 0.0-1.0 (e.g. {"dish": "pizza", "cuisine": "Italian", "visible_ingredients": ["cheese", "pepperoni", "basil"], "confidence": 0.85})
  - "document_or_text": if documents/screens/text — type, readable content, language, confidence 0.0-1.0 (e.g. {"type": "street sign", "text": "Main St", "language": "English", "confidence": 0.95})
  - "building": if a building — type, architectural style, condition, estimated era, confidence 0.0-1.0 (e.g. {"type": "residential house", "style": "colonial", "condition": "well-maintained", "era": "1950s", "confidence": 0.7})
  - "electronics": if electronics/devices — brand, type, model if identifiable, confidence 0.0-1.0 (e.g. {"brand": "Apple", "type": "laptop", "model": "MacBook Pro", "confidence": 0.9})
  Only include categories that are actually present. Omit categories with nothing relevant.

- "description": a detailed 2-3 sentence description of the full scene — what is visible, what appears to be happening, and any notable details.

Be as thorough as possible. More detail is always better. Identify brands, makes, models, species, and specific names whenever you can. Return ONLY valid JSON. No markdown, no explanation, no code fences."""


async def analyze_image(image_path: str) -> dict:
    """Call vision model to analyze an image. Returns parsed JSON dict."""
    client = _get_client()
    b64_data, media_type = _encode_image(image_path)

    response = await client.chat.completions.create(
        model=settings.vision_model,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": ANALYSIS_PROMPT},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{media_type};base64,{b64_data}",
                        },
                    },
                ],
            }
        ],
        max_tokens=2000,
        temperature=0.1,
    )

    raw = response.choices[0].message.content or "{}"
    # Strip markdown code fences if the model adds them anyway
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
    if raw.endswith("```"):
        raw = raw[:-3]
    raw = raw.strip()

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        parsed = {
            "detected_objects": [],
            "attributes": {"colors": [], "scene": "unknown", "tags": []},
            "description": raw[:500],
        }

    return parsed
