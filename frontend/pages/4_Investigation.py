import json
import streamlit as st
import api_client as api
from components import render_analysis_card

st.set_page_config(page_title="Investigation", page_icon="🧠", layout="wide")

st.title("🧠 Investigation Assistant")

st.markdown(
    "Ask a question about your image collection. "
    "The system will extract key subjects, find relevant images, and generate an investigative report."
)

# ── Question input ─────────────────────────────────────
query = st.text_input(
    "Your question",
    placeholder="e.g. What happened with the snowboarder? / Show me the red car / Who are the people in my photos?",
)

if st.button("🔍 Investigate", disabled=not query, type="primary"):
    with st.spinner("Extracting keywords and searching..."):
        result = api.investigate(query)

    # ── Summary ────────────────────────────────────────
    st.divider()
    st.subheader("📋 Investigation Report")
    st.markdown(result.get("summary", "No summary available."))

    # ── Matched images ─────────────────────────────────
    matched_ids_raw = result.get("matched_image_ids")
    if matched_ids_raw:
        try:
            matched_ids = json.loads(matched_ids_raw)
        except json.JSONDecodeError:
            matched_ids = []
    else:
        matched_ids = []

    if matched_ids:
        st.divider()
        st.subheader(
            f"🖼️ Evidence ({len(matched_ids)} image{'s' if len(matched_ids) != 1 else ''})")
        COLS = 3
        grid_cols = st.columns(COLS)
        for i, img_id in enumerate(matched_ids):
            with grid_cols[i % COLS]:
                try:
                    img = api.get_image(img_id)
                    st.image(
                        api.image_url(img["image_path"]),
                        use_container_width=True,
                    )
                    st.caption(f"**{img['filename']}**")
                    analysis = img.get("analysis")
                    if analysis:
                        attrs = analysis.get("attributes", "{}")
                        if isinstance(attrs, str):
                            try:
                                attrs = json.loads(attrs)
                            except json.JSONDecodeError:
                                attrs = {}
                        desc = attrs.get("description", "") if isinstance(
                            attrs, dict) else ""
                        if desc:
                            st.markdown(f"*{desc}*")
                        with st.expander("Full Analysis"):
                            render_analysis_card(analysis)
                except Exception:
                    st.caption(f"Image #{img_id}")
    else:
        st.info("No images matched this query.")

    # ── Record metadata ────────────────────────────────
    with st.expander("🗂️ Raw Investigation Record"):
        st.json(result)
