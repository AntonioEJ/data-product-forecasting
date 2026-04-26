"""
Main entrypoint for the Data Product Forecasting Streamlit App.

This app provides a demand forecasting data product interface
for business users.
"""

import streamlit as st

from app.pages import (
    forecast_exploration,
    batch_export,
    model_evaluation,
    business_feedback,
)

from utils.logging import setup_logging, get_logger


def main() -> None:
    """
    Initialize application and handle navigation.
    """
    # Inicializar logging PRIMERO
    setup_logging()

    # Crear logger después
    logger = get_logger(__name__)
    logger.info("Starting Streamlit application")

    # Configurar app
    st.set_page_config(
        page_title="data-product-forecasting",
        layout="wide",
    )

    st.sidebar.title("📈 data-product-forecasting")

    page = st.sidebar.radio(
        "Navegación",
        (
            "Exploración de Pronóstico",
            "Exportación Batch",
            "Evaluación de Modelo",
            "Feedback de Negocio",
        ),
    )

    logger.info(f"User selected page: {page}")

    # Routing
    if page == "Exploración de Pronóstico":
        forecast_exploration.render()

    elif page == "Exportación Batch":
        batch_export.render()

    elif page == "Evaluación de Modelo":
        model_evaluation.render()

    elif page == "Feedback de Negocio":
        business_feedback.render()


if __name__ == "__main__":
    main()