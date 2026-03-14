import json
import streamlit as st
import api_client as api
from components import render_analysis_card


st.title("🖼️ Image Library")

# ── Upload ─────────────────────────────────────────────
with st.expander("Upload Images", expanded=False):
    uploaded_files = st.file_uploader(
        "Choose images",
        type=["jpg", "jpeg", "png", "gif", "bmp", "webp", "tiff"],
        accept_multiple_files=True,
    )
    upload_source = st.text_input(
        "Source / Collection name (optional)", key="upload_src")
    if st.button("Upload", disabled=not uploaded_files):
        files = [("files", (f.name, f.getvalue(), f.type))
                 for f in uploaded_files]
        with st.spinner("Uploading..."):
            result = api.upload_images(files, source=upload_source or None)
        st.success(f"Uploaded {len(result)} image(s)")
        st.rerun()

# ── Import folder ──────────────────────────────────────
with st.expander("Import Folder", expanded=False):
    folder_path = st.text_input("Absolute folder path on server")
    import_source = st.text_input(
        "Source / Collection name (optional)", key="import_src")
    if st.button("Import", disabled=not folder_path):
        with st.spinner("Importing..."):
            result = api.import_folder(
                folder_path, source=import_source or None)
        st.success(f"Imported {result['imported']} image(s)")
        st.rerun()

# ── Bulk actions ───────────────────────────────────────
col_a, col_b = st.columns(2)
with col_a:
    if st.button("🔄 Re-analyze All Images"):
        with st.spinner("Reindexing..."):
            result = api.reindex_all()
        st.success(f"Reindexed {result['reindexed']} image(s)")
        st.rerun()

st.divider()

# ── Image grid ─────────────────────────────────────────
images = api.list_images(limit=200)
if not images:
    st.info("No images in the library. Upload or import some above.")
    st.stop()

st.caption(f"Showing {len(images)} image(s)")

COLS = 4
grid_cols = st.columns(COLS)

for i, img in enumerate(images):
    with grid_cols[i % COLS]:
        try:
            st.image(api.image_url(img["image_path"]),
                     use_container_width=True)
        except Exception:
            st.warning(f"Cannot display: {img['filename']}")

        st.caption(img["filename"])

        # Show analysis details
        detail = api.get_image(img["id"])
        analysis = detail.get("analysis")
        render_analysis_card(analysis)

        # EXIF & phash
        exif_raw = detail.get("exif_data")
        phash = detail.get("phash")
        if exif_raw or phash:
            with st.expander("📷 Metadata", expanded=False):
                if phash:
                    st.caption(f"**pHash:** `{phash}`")
                if exif_raw:
                    try:
                        exif = json.loads(exif_raw)
                        for k, v in exif.items():
                            st.caption(f"**{k}:** {v}")
                    except json.JSONDecodeError:
                        pass

        # Actions
        btn_col1, btn_col2 = st.columns(2)
        with btn_col1:
            if st.button("Analyze", key=f"analyze_{img['id']}"):
                with st.spinner("..."):
                    api.analyze_image(img["id"])
                st.rerun()
        with btn_col2:
            if st.button("Delete", key=f"del_{img['id']}"):
                api.delete_image(img["id"])
                st.rerun()
