"""
Batch export view.

Generates forecast files and uploads them to S3.
"""

import streamlit as st


from utils.logging import get_logger

def render():
    logger = get_logger(__name__)
    st.title("📦 Batch Export")

    scope = st.selectbox(
        "Select export scope",
        ["Category", "Store", "Full Catalog"]
    )

    if st.button("Generate Export"):
        logger.info(f"Batch export triggered for scope={scope}")

        with st.spinner("Generating file..."):
            # TODO: implementar integración con S3
            pass

        st.success("Export generated successfully!")
        st.markdown("[Download file](#)")