"""Shared UI helpers for rendering image analysis data."""
import json
import streamlit as st


def render_analysis_card(analysis: dict | None) -> None:
    """Render the full analysis metadata for an image in a clean UI."""
    if not analysis:
        st.caption("_not analyzed_")
        return

    # ── Description ────────────────────────────────────
    try:
        attrs = json.loads(analysis.get("attributes") or "{}")
    except json.JSONDecodeError:
        attrs = {}

    description = attrs.get("description", "")
    if description:
        st.markdown(f"*{description}*")

    # ── Detected objects as tags ───────────────────────
    try:
        tags = json.loads(analysis.get("detected_objects") or "[]")
    except json.JSONDecodeError:
        tags = []
    if tags:
        st.write(" ".join(f"`{t}`" for t in tags))

    # ── Scene & Colors ─────────────────────────────────
    scene = attrs.get("scene", "")
    colors = attrs.get("colors", [])
    if scene:
        st.caption(f"**Scene:** {scene}")
    if colors:
        st.caption(f"**Colors:** {', '.join(colors)}")

    # ── Tags ───────────────────────────────────────────
    attr_tags = attrs.get("tags", [])
    if attr_tags:
        st.caption(f"**Tags:** {', '.join(attr_tags)}")

    # ── Materials ──────────────────────────────────────
    materials = attrs.get("materials", [])
    if materials:
        st.caption(f"**Materials:** {', '.join(materials)}")

    # ── Classification ─────────────────────────────────
    classification = attrs.get("classification", {})
    if classification:
        for category, data in classification.items():
            _render_classification(category, data)


def _render_classification(category: str, data) -> None:
    """Render a single classification category."""
    label = category.replace("_", " ").title()

    # Handle list (e.g. multiple persons)
    items = data if isinstance(data, list) else [data]

    for item in items:
        if not isinstance(item, dict):
            continue

        confidence = item.get("confidence")
        conf_str = f" ({confidence:.0%})" if confidence is not None else ""

        if category == "person":
            gender = item.get("gender", "unknown")
            ethnicity = item.get("ethnicity", "unknown")
            age = item.get("age_range", "?")
            build = item.get("build", "")
            hair = item.get("hair", "")
            clothing = item.get("clothing", "")
            features = item.get("features", "")
            accessories = item.get("accessories", [])
            action = item.get("action", "")

            parts = []
            if gender and gender != "unknown":
                parts.append(gender)
            if ethnicity and ethnicity != "unknown":
                parts.append(ethnicity)
            if age:
                parts.append(f"age {age}")
            if build:
                parts.append(build)

            headline = ", ".join(parts) if parts else "Person"
            st.markdown(f"**🧑 {headline}**{conf_str}")

            details = []
            if hair:
                details.append(f"Hair: {hair}")
            if clothing:
                details.append(f"Clothing: {clothing}")
            if features:
                details.append(f"Features: {features}")
            if accessories:
                acc = accessories if isinstance(
                    accessories, list) else [accessories]
                details.append(f"Accessories: {', '.join(acc)}")
            if action:
                details.append(f"Action: {action}")
            if details:
                st.caption(" · ".join(details))

        elif category == "vehicle":
            make = item.get("make", "?")
            model = item.get("model", "?")
            color = item.get("color", "")
            year = item.get("year_range", "")
            plate = item.get("plate", "")
            condition = item.get("condition", "")

            headline = f"{color} {make} {model}".strip()
            if year:
                headline += f" ({year})"
            st.markdown(f"**🚗 {headline}**{conf_str}")
            extras = []
            if plate:
                extras.append(f"Plate: {plate}")
            if condition:
                extras.append(f"Condition: {condition}")
            if extras:
                st.caption(" · ".join(extras))

        elif category == "plant":
            common = item.get("common_name", "")
            species = item.get("species", "")
            ptype = item.get("type", "")
            color = item.get("color", "")
            health = item.get("health", "")

            headline = common or species or "Plant"
            if species and common:
                headline += f" (*{species}*)"
            st.markdown(f"**🌿 {headline}**{conf_str}")
            extras = []
            if ptype:
                extras.append(f"Type: {ptype}")
            if color:
                extras.append(f"Color: {color}")
            if health:
                extras.append(f"Health: {health}")
            if extras:
                st.caption(" · ".join(extras))

        elif category == "animal":
            species = item.get("species", "?")
            breed = item.get("breed", "")
            color = item.get("color", "")
            behavior = item.get("behavior", "")

            headline = f"{breed} {species}".strip() if breed else species
            st.markdown(f"**🐾 {headline}**{conf_str}")
            extras = []
            if color:
                extras.append(f"Color: {color}")
            if behavior:
                extras.append(f"Behavior: {behavior}")
            if extras:
                st.caption(" · ".join(extras))

        elif category == "brand_or_logo":
            brand = item.get("brand", "?")
            product = item.get("product", "")
            st.markdown(f"**🏷️ {brand}**{conf_str}")
            if product:
                st.caption(f"Product: {product}")

        elif category == "building":
            btype = item.get("type", "Building")
            style = item.get("style", "")
            era = item.get("era", "")
            condition = item.get("condition", "")
            headline = btype
            if style:
                headline += f", {style}"
            st.markdown(f"**🏢 {headline}**{conf_str}")
            extras = []
            if era:
                extras.append(f"Era: {era}")
            if condition:
                extras.append(f"Condition: {condition}")
            if extras:
                st.caption(" · ".join(extras))

        elif category == "food":
            dish = item.get("dish", "?")
            cuisine = item.get("cuisine", "")
            ingredients = item.get("visible_ingredients", [])
            headline = f"{dish} ({cuisine})" if cuisine else dish
            st.markdown(f"**🍽️ {headline}**{conf_str}")
            if ingredients:
                st.caption(f"Ingredients: {', '.join(ingredients)}")

        elif category == "document_or_text":
            dtype = item.get("type", "Text")
            text = item.get("text", "")
            lang = item.get("language", "")
            st.markdown(f"**📄 {dtype}**{conf_str}")
            extras = []
            if text:
                extras.append(f'"{text}"')
            if lang:
                extras.append(f"Language: {lang}")
            if extras:
                st.caption(" · ".join(extras))

        elif category == "electronics":
            brand = item.get("brand", "?")
            etype = item.get("type", "")
            model = item.get("model", "")
            headline = f"{brand} {etype}".strip()
            if model:
                headline += f" {model}"
            st.markdown(f"**📱 {headline}**{conf_str}")

        else:
            st.markdown(f"**{label}**{conf_str}")
            st.json(item)
