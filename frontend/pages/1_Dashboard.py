import json
import streamlit as st
import api_client as api


st.title("📊 Dashboard")

# ── Health check ───────────────────────────────────────
try:
    h = api.health()
    st.success(f"Backend is **{h['status']}** — v{h['version']}")
except Exception:
    st.error("Cannot reach backend at http://localhost:8000")
    st.stop()

# ── Load images ────────────────────────────────────────
images = api.list_images(limit=500)

st.metric("Total Images", len(images))

# ── Quick stats ────────────────────────────────────────
with_phash = sum(1 for img in images if img.get("phash"))
with_exif = sum(1 for img in images if img.get("exif_data"))
stat_cols = st.columns(3)
with stat_cols[0]:
    st.metric("With pHash", with_phash)
with stat_cols[1]:
    st.metric("With EXIF", with_exif)
with stat_cols[2]:
    gps_count = 0
    for img in images:
        raw = img.get("exif_data")
        if raw:
            try:
                exif = json.loads(raw)
                if "gps_lat" in exif:
                    gps_count += 1
            except json.JSONDecodeError:
                pass
    st.metric("With GPS", gps_count)

# ── Recent uploads ─────────────────────────────────────
st.subheader("Recent Uploads")
recent = images[:10]
if recent:
    cols = st.columns(min(5, len(recent)))
    for i, img in enumerate(recent):
        with cols[i % 5]:
            try:
                st.image(api.image_url(img["image_path"]), caption=img["filename"],
                         use_container_width=True)
            except Exception:
                st.caption(img["filename"])
else:
    st.info("No images uploaded yet.")

# ── Gather analysis stats ──────────────────────────────
tag_counts: dict[str, int] = {}
category_counts: dict[str, int] = {}
for img in images:
    detail = api.get_image(img["id"])
    analysis = detail.get("analysis")
    if not analysis:
        continue
    try:
        objects = json.loads(analysis.get("detected_objects") or "[]")
    except json.JSONDecodeError:
        objects = []
    for obj in objects:
        tag_counts[obj] = tag_counts.get(obj, 0) + 1
    try:
        attrs = json.loads(analysis.get("attributes") or "{}")
    except json.JSONDecodeError:
        attrs = {}
    classification = attrs.get("classification", {})
    for cat in classification:
        label = cat.replace("_", " ").title()
        category_counts[label] = category_counts.get(label, 0) + 1

# ── Classification categories ──────────────────────────
st.subheader("Classification Categories")
if category_counts:
    sorted_cats = sorted(category_counts.items(),
                         key=lambda x: x[1], reverse=True)
    cat_cols = st.columns(min(5, len(sorted_cats)))
    for i, (cat, count) in enumerate(sorted_cats):
        with cat_cols[i % 5]:
            st.metric(cat, count)
else:
    st.info("No classification data yet.")

# ── Top detected tags ─────────────────────────────────
st.subheader("Top Detected Tags")
if tag_counts:
    sorted_tags = sorted(tag_counts.items(),
                         key=lambda x: x[1], reverse=True)[:15]
    tag_cols = st.columns(min(5, len(sorted_tags)))
    for i, (tag, count) in enumerate(sorted_tags):
        with tag_cols[i % 5]:
            st.metric(tag, count)
else:
    st.info("No analysis data yet. Upload and analyze images first.")
