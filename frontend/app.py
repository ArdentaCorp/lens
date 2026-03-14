import streamlit as st

st.set_page_config(
    page_title="Ardenta Image Library",
    page_icon="🔍",
    layout="wide",
)

dashboard = st.Page("pages/1_Dashboard.py",
                    title="Dashboard", icon="📊", default=True)
library = st.Page("pages/2_Library.py", title="Library", icon="🖼️")
search = st.Page("pages/3_Search.py", title="Search", icon="🔍")
investigation = st.Page("pages/4_Investigation.py",
                        title="Investigation", icon="🧠")

pg = st.navigation([dashboard, library, search, investigation])
pg.run()
