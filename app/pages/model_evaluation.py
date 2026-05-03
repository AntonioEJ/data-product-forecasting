"""Vista de evaluación de modelo.

Muestra métricas de rendimiento del modelo y comparación vs baseline naive.
"""

import pandas as pd
import streamlit as st

from data.rds import fetch_query
from utils.logging import get_logger


@st.cache_data(ttl=300, show_spinner=False)
def _load_metrics() -> pd.DataFrame:
    rows = fetch_query(
        """
        SELECT category_name, mae, rmse, mae_naive, rmse_naive, computed_at
        FROM metrics
        ORDER BY category_name
        """
    )
    return pd.DataFrame(rows) if rows else pd.DataFrame()


@st.cache_data(ttl=300, show_spinner=False)
def _load_backtest_sample() -> pd.DataFrame:
    rows = fetch_query(
        """
        SELECT forecast_date AS date, predicted_units AS predicted, actual_units AS actual
        FROM predictions
        WHERE actual_units IS NOT NULL
        ORDER BY forecast_date DESC
        LIMIT 500
        """
    )
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values("date")


def render():
    """Renderiza la página de evaluación de modelo."""
    logger = get_logger(__name__)
    st.title("Evaluación del Modelo")
    logger.info("Rendering model evaluation page")

    # ── Métricas por categoría ────────────────────────────────────────────────────────────
    st.subheader("Métricas por Categoría (Modelo vs Baseline Naive)")
    try:
        metrics = _load_metrics()
    except Exception as exc:
        st.error("No se pudieron cargar las métricas. Verifica la conexión a RDS.")
        logger.exception("Error cargando métricas: %s", exc)
        return

    if metrics.empty:
        st.info("No hay métricas disponibles todavía. Ejecuta el pipeline de evaluación primero.")
    else:
        display = metrics[["category_name", "mae", "mae_naive", "rmse", "rmse_naive", "computed_at"]].copy()
        display.columns = ["Categoría", "MAE (Modelo)", "MAE (Naive)", "RMSE (Modelo)", "RMSE (Naive)", "Calculado el"]
        st.dataframe(display, use_container_width=True)

        # Comparación visual MAE
        st.subheader("MAE: Modelo vs Naive")
        chart_data = metrics.set_index("category_name")[["mae", "mae_naive"]]
        chart_data.columns = ["MAE Modelo", "MAE Naive"]
        st.bar_chart(chart_data)

    # ── Backtest: predicho vs real ───────────────────────────────────────────
    st.subheader("Backtest: Predicted vs Actual")
    try:
        backtest = _load_backtest_sample()
    except Exception as exc:
        st.error("No se pudo cargar el backtest.")
        logger.exception("Error cargando backtest: %s", exc)
        return

    if backtest.empty:
        st.info("No hay datos de backtest disponibles (sin valores reales registrados).")
    else:
        st.line_chart(backtest.set_index("date")[["predicted", "actual"]].rename(
            columns={"predicted": "Predicho", "actual": "Real"}
        ))
