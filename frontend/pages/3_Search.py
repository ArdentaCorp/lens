import streamlit as st
import api_client as api
from components import render_analysis_card

st.set_page_config(layout="wide") if not hasattr(
    st, "_page_configured") else None

st.title("🔍 Search Images")

# ── Search bar ─────────────────────────────────────────
query = st.text_input(
    "Search query",
    placeholder="Describe what you're looking for — e.g. red car at night, man in blue jacket, yellow flowers",
    key="search_query",
)

# ── Filters (collapsible) ─────────────────────────────
with st.expander("Filters", expanded=False):
    col1, col2, col3 = st.columns(3)
    with col1:
        source_filter = st.text_input(
            "Source / Collection", key="source_filter")
    with col2:
        object_type = st.text_input(
            "Object type", placeholder="e.g. car, person", key="obj_type")
    with col3:
        color = st.text_input(
            "Color", placeholder="e.g. red, white", key="color")

# ── Trigger search ─────────────────────────────────────
if not query:
    st.info("Enter a search query above to find images.")
    st.stop()

# ── Execute ────────────────────────────────────────────
with st.spinner("Searching..."):
    result = api.search_images(
        query=query,
        source=source_filter or None,
        object_type=object_type or None,
        color=color or None,
    )

images = result.get("images", [])
total = result.get("total", 0)
method = result.get("search_method", "none")

# ── Results header ─────────────────────────────────────
method_labels = {
    "fts": "📄 Full-Text",
    "semantic": "🧠 Semantic",
    "keyword": "🔤 Keyword",
    "hybrid": "⚡ Hybrid (FTS + Semantic + Keyword)",
    "none": "—",
}

col_stat1, col_stat2 = st.columns([1, 2])
with col_stat1:
    st.metric("Results", total)
with col_stat2:
    st.caption(f"Search method: **{method_labels.get(method, method)}**")

if not images:
    st.info("No images matched your query. Try broader terms or check your filters.")
    st.stop()

st.divider()

# ── Results grid ───────────────────────────────────────
COLS = 3
grid_cols = st.columns(COLS)

for i, img in enumerate(images):
    with grid_cols[i % COLS]:
        # Image
        try:
            st.image(api.image_url(img["image_path"]),
                     use_container_width=True)
        except Exception:
            st.warning(f"Cannot display: {img['filename']}")

        # Filename + source badge
        source = img.get("source")
        label = f"**{img['filename']}**"
        if source:
            label += f"  `{source}`"
        st.markdown(label)

        # Analysis card
        analysis = img.get("analysis")
        render_analysis_card(analysis)

        # Expandable raw JSON
        with st.expander("Raw data"):
            st.json(img)

        st.divider()
