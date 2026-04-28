"""Punto de entrada principal de la aplicación Streamlit de Forecasting.

Esta app provee una interfaz de producto de datos de pronóstico de demanda
para usuarios de negocio.
"""

import streamlit as st

from app.pages import (
    batch_export,
    business_feedback,
    forecast_exploration,
    model_evaluation,
)
from utils.logging import get_logger, setup_logging


def main() -> None:
    """Inicializa la aplicación y maneja la navegación."""
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
