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


_PAGES = {
    " Exploración de Pronósticos": forecast_exploration,
    " Exportación Masiva": batch_export,
    " Evaluación del Modelo": model_evaluation,
    " Retroalimentación del Negocio": business_feedback,
}


def main() -> None:
    """Inicializa la aplicación y maneja la navegación."""
    setup_logging()

    logger = get_logger(__name__)
    logger.info("Iniciando aplicación Streamlit")

    st.set_page_config(
        page_title="Pronóstico de Demanda",
        page_icon="📈",
        layout="wide",
    )

    st.sidebar.title("📈 Pronóstico de Demanda")

    page = st.sidebar.radio(
        "Menú",
        list(_PAGES.keys()),
    )

    logger.info("Página seleccionada: %s", page)

    _PAGES[page].render()


if __name__ == "__main__":
    main()
