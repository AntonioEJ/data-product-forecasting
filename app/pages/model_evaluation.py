"""Vista de evaluación de modelo.

Muestra métricas de rendimiento del modelo y comparación vs baseline naive.
"""

import streamlit as st

from app.components.db_helpers import (
    get_categories_list,
    get_metrics_by_category,
    get_predictions_with_actuals,
    get_shops_list,
)
from utils.logging import get_logger


def render():
    """Renderiza la página de evaluación de modelo."""
    logger = get_logger(__name__)
    st.title("Evaluación de Modelo")
    logger.info("Renderizando vista de evaluación de modelo")

    # ── Métricas globales ─────────────────────────────────────────────────────
    st.subheader("Métricas Globales")
    try:
        df_metrics = get_metrics_by_category()

        if df_metrics.empty:
            st.info("No hay métricas calculadas todavía.")
        else:
            total_obs = df_metrics["n_obs"].sum()
            mae_global = (df_metrics["mae"] * df_metrics["n_obs"]).sum() / total_obs
            rmse_global = (df_metrics["rmse"] * df_metrics["n_obs"]).sum() / total_obs
            mae_naive_global = (
                df_metrics["mae_naive"] * df_metrics["n_obs"]
            ).sum() / total_obs
            rmse_naive_global = (
                df_metrics["rmse_naive"] * df_metrics["n_obs"]
            ).sum() / total_obs

            col1, col2, col3, col4 = st.columns(4)
            col1.metric("MAE Modelo", f"{mae_global:.2f}")
            col2.metric("RMSE Modelo", f"{rmse_global:.2f}")
            col3.metric("MAE Naive", f"{mae_naive_global:.2f}")
            col4.metric("RMSE Naive", f"{rmse_naive_global:.2f}")

            n_mejor = int((df_metrics["mae"] < df_metrics["mae_naive"]).sum())
            n_total = len(df_metrics)
            st.caption(
                f"El modelo le gana al naive en {n_mejor} de {n_total} categorías."
            )

    except Exception as exc:
        st.error(f"Error al cargar métricas globales: {exc}\n\nVerifica conectividad a RDS.")
        logger.error("Error en métricas globales: %s", exc)

    # ── Métricas por categoría ────────────────────────────────────────────────
    st.subheader("Métricas por Categoría")
    try:
        df_metrics_cat = get_metrics_by_category()

        if df_metrics_cat.empty:
            st.info("No hay métricas por categoría.")
        else:
            st.dataframe(df_metrics_cat, use_container_width=True)

    except Exception as exc:
        st.error(f"Error al cargar métricas por categoría: {exc}\n\nVerifica conectividad a RDS.")
        logger.error("Error en métricas por categoría: %s", exc)

    # ── Filtros en sidebar ────────────────────────────────────────────────────
    st.sidebar.header("Filtros — Predicted vs Actual")

    try:
        categories = ["Todas"] + get_categories_list()
    except Exception as exc:
        st.sidebar.error(f"Error al cargar categorías: {exc}")
        logger.error("Error al cargar categorías: %s", exc)
        categories = ["Todas"]

    selected_cat = st.sidebar.selectbox("Categoría", categories)

    try:
        df_shops = get_shops_list()
        shop_options = {"Todas": None}
        for _, row in df_shops.iterrows():
            shop_options[row["shop_name"]] = int(row["shop_id"])
        selected_shop_name = st.sidebar.selectbox("Tienda", list(shop_options.keys()))
        selected_shop_id = shop_options[selected_shop_name]
    except Exception as exc:
        st.sidebar.error(f"Error al cargar tiendas: {exc}")
        logger.error("Error al cargar tiendas: %s", exc)
        selected_shop_id = None

    limit = st.sidebar.slider(
        "Número de filas a mostrar", min_value=100, max_value=5000, value=1000, step=100
    )

    # ── Predicted vs Actual ───────────────────────────────────────────────────
    st.subheader("Predicted vs Actual")
    try:
        cat_param = None if selected_cat == "Todas" else selected_cat

        df_pred = get_predictions_with_actuals(
            category_name=cat_param,
            shop_id=selected_shop_id,
            limit=limit,
        )

        if df_pred.empty:
            st.info("No hay datos para los filtros seleccionados.")
        else:
            cols_mostrar = [
                "forecast_date",
                "shop_name",
                "item_name",
                "category_name",
                "predicted_units",
                "actual_units",
            ]
            st.dataframe(df_pred[cols_mostrar], use_container_width=True)

            st.caption("Si los puntos están sobre la diagonal, el modelo predice perfecto.")
            st.scatter_chart(
                df_pred.rename(
                    columns={"actual_units": "actual", "predicted_units": "predicted"}
                )[["actual", "predicted"]],
                x="actual",
                y="predicted",
            )

    except Exception as exc:
        st.error(
            f"Error al cargar predicciones: {exc}\n\nVerifica conectividad a RDS."
        )
        logger.error("Error en predicted vs actual: %s", exc)
