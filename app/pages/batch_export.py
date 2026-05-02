"""Vista de exportación batch.

Genera archivos de pronóstico descargables directamente desde RDS.
"""

import io

import pandas as pd
import streamlit as st

from data.rds import fetch_query, execute_query
from utils.logging import get_logger


@st.cache_data(ttl=300, show_spinner=False)
def _load_shop_options() -> dict[str, int]:
    rows = fetch_query("SELECT shop_id, shop_name FROM shops ORDER BY shop_name")
    return {r["shop_name"]: r["shop_id"] for r in rows}


@st.cache_data(ttl=300, show_spinner=False)
def _load_category_options() -> list[str]:
    rows = fetch_query("SELECT DISTINCT category_name FROM products ORDER BY category_name")
    return [r["category_name"] for r in rows]


def _query_forecasts(scope: str, filter_value: str | int) -> pd.DataFrame:
    if scope == "Store":
        sql = """
            SELECT s.shop_name, pr.item_name, pr.category_name,
                   p.forecast_date, p.predicted_units, p.actual_units
            FROM predictions p
            JOIN shops s    ON s.shop_id  = p.shop_id
            JOIN products pr ON pr.item_id = p.item_id
            WHERE p.shop_id = :val
            ORDER BY p.forecast_date, pr.category_name, pr.item_name
        """
    elif scope == "Category":
        sql = """
            SELECT s.shop_name, pr.item_name, pr.category_name,
                   p.forecast_date, p.predicted_units, p.actual_units
            FROM predictions p
            JOIN shops s    ON s.shop_id  = p.shop_id
            JOIN products pr ON pr.item_id = p.item_id
            WHERE pr.category_name = :val
            ORDER BY p.forecast_date, s.shop_name, pr.item_name
        """
    else:  # Full Catalog
        sql = """
            SELECT s.shop_name, pr.item_name, pr.category_name,
                   p.forecast_date, p.predicted_units, p.actual_units
            FROM predictions p
            JOIN shops s    ON s.shop_id  = p.shop_id
            JOIN products pr ON pr.item_id = p.item_id
            ORDER BY p.forecast_date, s.shop_name, pr.category_name
        """
        rows = fetch_query(sql)
        return pd.DataFrame(rows) if rows else pd.DataFrame()

    rows = fetch_query(sql, {"val": filter_value})
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def _register_batch_job(scope: str, filter_value: str) -> None:
    execute_query(
        """
        INSERT INTO batch_jobs (filter_type, filter_value, status, created_at)
        VALUES (:filter_type, :filter_value, 'completed', NOW())
        """,
        {"filter_type": scope, "filter_value": str(filter_value)},
    )


def render():
    """Renderiza la página de exportación batch."""
    logger = get_logger(__name__)
    st.title("📦 Batch Export")

    scope = st.selectbox("Export scope", ["Store", "Category", "Full Catalog"])

    filter_value: str | int = ""
    try:
        if scope == "Store":
            shop_options = _load_shop_options()
            if not shop_options:
                st.warning("No hay tiendas disponibles.")
                return
            selected_name = st.selectbox("Select Store", list(shop_options.keys()))
            filter_value = shop_options[selected_name]

        elif scope == "Category":
            categories = _load_category_options()
            if not categories:
                st.warning("No hay categorías disponibles.")
                return
            filter_value = st.selectbox("Select Category", categories)

    except Exception as exc:
        st.error("Error cargando opciones de filtro.")
        logger.exception("Error cargando filtros batch: %s", exc)
        return

    if st.button("Generate Export"):
        logger.info("Batch export triggered: scope=%s, filter=%s", scope, filter_value)

        with st.spinner("Querying data..."):
            try:
                df = _query_forecasts(scope, filter_value)
            except Exception as exc:
                st.error("Error generando el reporte. Intenta nuevamente.")
                logger.exception("Error en batch export: %s", exc)
                return

        if df.empty:
            st.warning("No hay datos para los filtros seleccionados.")
            return

        # ── Generar CSV en memoria ───────────────────────────────────────────
        buffer = io.BytesIO()
        df.to_csv(buffer, index=False, encoding="utf-8-sig")
        buffer.seek(0)

        filename = f"forecast_{scope.lower().replace(' ', '_')}_{filter_value}.csv"

        st.success(f"Reporte listo — {len(df):,} filas")
        st.download_button(
            label="⬇️ Download CSV",
            data=buffer,
            file_name=filename,
            mime="text/csv",
        )

        # Registrar job en RDS para trazabilidad
        try:
            _register_batch_job(scope, str(filter_value))
            logger.info("Batch job registrado en RDS: scope=%s, filter=%s", scope, filter_value)
        except Exception as exc:
            logger.warning("No se pudo registrar batch_job en RDS: %s", exc)
