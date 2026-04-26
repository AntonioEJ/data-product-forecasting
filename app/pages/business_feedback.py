"""
Business feedback view.

Allows users to submit feedback on forecasts.
"""

import streamlit as st

st.subheader("Reported Issues")
st.table(mock_data)

from utils.logging import get_logger

def render():
    logger = get_logger(__name__)
    st.title("💬 Business Feedback")

    product = st.text_input("Product ID")
    comment = st.text_area("Comment")

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