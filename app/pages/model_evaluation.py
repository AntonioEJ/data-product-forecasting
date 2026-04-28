"""Vista de evaluación de modelo.

Muestra métricas de rendimiento del modelo y comparación vs baseline naive.
"""

import pandas as pd
import streamlit as st

from utils.logging import get_logger


def render():
    """Renderiza la página de evaluación de modelo."""
    logger = get_logger(__name__)
    st.title("📊 Model Evaluation")

    logger.info("Rendering model evaluation page")

    metrics = pd.DataFrame(
        {
            "metric": ["MAE", "RMSE"],
            "model": [10, 15],
            "naive": [15, 20],
        }
    )

    st.subheader("Metrics Comparison")
    st.dataframe(metrics)

    data = pd.DataFrame(
        {
            "date": pd.date_range("2024-01-01", periods=30),
            "actual": range(30),
            "predicted": [x + 2 for x in range(30)],
        }
    )

    st.subheader("Model vs Actual")
    st.line_chart(data.set_index("date"))
