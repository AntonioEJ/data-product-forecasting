"""Vista de exploración de pronósticos.

Permite a los usuarios filtrar y visualizar pronósticos de demanda.
"""

import pandas as pd
import streamlit as st

from data.rds import fetch_query
from utils.logging import get_logger


@st.cache_data(ttl=300, show_spinner=False)
def _load_shops() -> list[dict]:
    return fetch_query("SELECT shop_id, shop_name FROM shops ORDER BY shop_name")


@st.cache_data(ttl=300, show_spinner=False)
def _load_categories() -> list[str]:
    rows = fetch_query("SELECT DISTINCT category_name FROM products ORDER BY category_name")
    return [r["category_name"] for r in rows]


@st.cache_data(ttl=300, show_spinner=False)
def _load_forecasts(shop_id: int, category_name: str) -> pd.DataFrame:
    sql = """
        SELECT
            p.forecast_date   AS date,
            p.predicted_units AS predicted,
            p.actual_units    AS actual
        FROM predictions p
        JOIN products pr ON pr.item_id = p.item_id
        WHERE p.shop_id        = :shop_id
          AND pr.category_name = :category_name
        ORDER BY p.forecast_date
    """
    rows = fetch_query(sql, {"shop_id": shop_id, "category_name": category_name})
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    return df


def render():
    """Renderiza la página de exploración de pronósticos."""
    logger = get_logger(__name__)
    st.title("🔎 Forecast Exploration")

    # ── Filtros dinámicos desde RDS ──────────────────────────────────────────
    st.sidebar.header("Filters")
    try:
        shops = _load_shops()
        categories = _load_categories()
    except Exception as exc:
        st.error("No se pudo conectar a la base de datos. Verifica la configuración de RDS.")
        logger.exception("Error cargando catálogos: %s", exc)
        return

    if not shops or not categories:
        st.warning("No hay datos de tiendas o categorías disponibles todavía.")
        return

    shop_options = {s["shop_name"]: s["shop_id"] for s in shops}
    selected_shop_name = st.sidebar.selectbox("Store", list(shop_options.keys()))
    selected_category = st.sidebar.selectbox("Category", categories)

    shop_id = shop_options[selected_shop_name]
    logger.info("Filters selected: shop_id=%s, category=%s", shop_id, selected_category)

    # ── Carga de pronósticos ─────────────────────────────────────────────────
    with st.spinner("Loading forecast data..."):
        try:
            data = _load_forecasts(shop_id, selected_category)
        except Exception as exc:
            st.error("Error al cargar pronósticos. Intenta nuevamente.")
            logger.exception("Error cargando pronósticos: %s", exc)
            return

    if data.empty:
        st.info("No hay pronósticos disponibles para los filtros seleccionados.")
        return

    # ── Vista de datos ───────────────────────────────────────────────────────
    st.subheader("Forecast Data")
    st.dataframe(data, use_container_width=True)

    st.subheader("Forecast Trend")
    chart_cols = [c for c in ["predicted", "actual"] if c in data.columns and data[c].notna().any()]
    st.line_chart(data.set_index("date")[chart_cols])
