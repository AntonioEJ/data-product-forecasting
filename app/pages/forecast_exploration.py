"""Forecast exploration view.

Allows users to filter and visualize demand forecasts.
"""

import pandas as pd
import streamlit as st

from utils.logging import get_logger


def render():
    """Render the forecast exploration page."""
    logger = get_logger(__name__)
    st.title("🔎 Forecast Exploration")

    st.sidebar.header("Filters")
    store = st.sidebar.selectbox("Store", ["Store A", "Store B"])
    category = st.sidebar.selectbox("Category", ["Category 1", "Category 2"])

    logger.info(f"Filters selected: store={store}, category={category}")

    with st.spinner("Loading forecast data..."):
        # TODO: reemplazar por query real a RDS
        data = pd.DataFrame(
            {
                "date": pd.date_range(start="2024-01-01", periods=30),
                "sales": range(30),
            }
        )

    st.subheader("Forecast Data")
    st.dataframe(data)

    st.subheader("Forecast Trend")
    st.line_chart(data.set_index("date"))
