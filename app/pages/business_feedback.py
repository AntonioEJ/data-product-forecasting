"""Vista de feedback de negocio.

Permite a los usuarios enviar retroalimentación sobre los pronósticos.
"""

import streamlit as st

from utils.logging import get_logger


def render():
    """Renderiza la página de feedback de negocio."""
    logger = get_logger(__name__)
    st.title("💬 Business Feedback")

    product = st.text_input("Product ID")

    if st.button("Submit Feedback"):
        logger.info(f"Feedback submitted for product={product}")
        # TODO: guardar en RDS
        st.success("Feedback submitted successfully!")

    st.subheader("Reported Issues")

    mock_data = [
        {"product": "A", "comment": "Bad forecast"},
        {"product": "B", "comment": "Seasonality issue"},
    ]

    st.table(mock_data)
