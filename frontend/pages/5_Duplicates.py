import streamlit as st
import api_client as api


st.title("🔁 Duplicate Detection")

st.markdown(
    "Find visually similar or duplicate images using perceptual hashing. "
    "Lower threshold = stricter matching."
)

threshold = st.slider("Similarity threshold", min_value=0,
                      max_value=30, value=10,
                      help="Max hamming distance (0 = exact, 10 = similar, 20+ = loose)")

if st.button("Find Duplicates"):
    with st.spinner("Scanning..."):
        result = api.find_duplicates(threshold=threshold)

    groups = result.get("groups", [])
    total = result.get("total_duplicates", 0)

    if not groups:
        st.success("No duplicates found!")
        st.stop()

    st.warning(
        f"Found **{len(groups)}** group(s) with **{total}** total images")

    for gi, group in enumerate(groups):
        with st.expander(f"Group {gi + 1} — {len(group['images'])} images (phash: {group['phash']})"):
            cols = st.columns(min(4, len(group["images"])))
            for i, img in enumerate(group["images"]):
                with cols[i % 4]:
                    try:
                        st.image(api.image_url(img["image_path"]),
                                 use_container_width=True)
                    except Exception:
                        pass
                    st.caption(img["filename"])
