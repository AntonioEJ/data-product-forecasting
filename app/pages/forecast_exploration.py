"""Vista de exploración de pronósticos.

Permite filtrar por tienda o por categoría y visualizar la proyección
de la próxima temporada versus el histórico real.

Diseño de queries:
- Toda la agregación ocurre en PostgreSQL (SUM por fecha).
- La app recibe como máximo ~24 filas por consulta → respuesta en < 1 s.
- Los catálogos (tiendas/categorías) se cachean 5 min con @st.cache_data.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from data.rds import fetch_query
from utils.logging import get_logger

# ── Queries ───────────────────────────────────────────────────────────────────

_SQL_BY_STORE = """
    SELECT
        p.forecast_date                    AS date,
        SUM(p.predicted_units)             AS predicted,
        SUM(p.actual_units)                AS actual
    FROM predictions p
    WHERE p.shop_id = :val
    GROUP BY p.forecast_date
    ORDER BY p.forecast_date
"""

_SQL_BY_CATEGORY = """
    SELECT
        p.forecast_date                    AS date,
        SUM(p.predicted_units)             AS predicted,
        SUM(p.actual_units)                AS actual
    FROM predictions p
    JOIN products pr ON pr.item_id = p.item_id
    WHERE pr.category_name = :val
    GROUP BY p.forecast_date
    ORDER BY p.forecast_date
"""

# ── Loaders cacheados ─────────────────────────────────────────────────────────

@st.cache_data(ttl=300, show_spinner=False)
def _load_shops() -> dict[str, int]:
    rows = fetch_query("SELECT shop_id, shop_name FROM shops ORDER BY shop_name")
    return {r["shop_name"]: r["shop_id"] for r in rows}


@st.cache_data(ttl=300, show_spinner=False)
def _load_categories() -> list[str]:
    rows = fetch_query(
        "SELECT DISTINCT category_name FROM products ORDER BY category_name"
    )
    return [r["category_name"] for r in rows]


@st.cache_data(ttl=300, show_spinner=False)
def _load_by_store(shop_id: int) -> pd.DataFrame:
    rows = fetch_query(_SQL_BY_STORE, {"val": shop_id})
    return _to_df(rows)


@st.cache_data(ttl=300, show_spinner=False)
def _load_by_category(category_name: str) -> pd.DataFrame:
    rows = fetch_query(_SQL_BY_CATEGORY, {"val": category_name})
    return _to_df(rows)


def _to_df(rows: list[dict]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    df["predicted"] = df["predicted"].astype(float)
    df["actual"] = pd.to_numeric(df["actual"], errors="coerce")
    return df.sort_values("date").reset_index(drop=True)


# ── Helpers de UI ─────────────────────────────────────────────────────────────

def _kpi(label: str, value: str, delta: str | None = None) -> None:
    st.metric(label=label, value=value, delta=delta)


def _format_units(n: float) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f} M"
    if n >= 1_000:
        return f"{n / 1_000:.1f} K"
    return f"{n:,.0f}"


# ── Render principal ──────────────────────────────────────────────────────────

def render() -> None:
    """Renderiza la página de exploración de pronósticos."""
    logger = get_logger(__name__)
    st.title("🔎 Exploración de Pronósticos")

    # ── Sidebar: modo de filtro ───────────────────────────────────────────────
    st.sidebar.header("Filtros")
    filter_mode = st.sidebar.radio(
        "Filtrar por",
        ["Tienda", "Categoría"],
        horizontal=True,
    )

    # ── Cargar catálogos ──────────────────────────────────────────────────────
    try:
        shops = _load_shops()
        categories = _load_categories()
    except Exception as exc:
        st.error("No se pudo conectar a la base de datos. Verifica las variables de entorno RDS_*.")
        logger.exception("Error cargando catálogos: %s", exc)
        return

    # ── Selectbox según modo ──────────────────────────────────────────────────
    filter_label = ""
    df = pd.DataFrame()

    if filter_mode == "Tienda":
        if not shops:
            st.warning("No hay tiendas disponibles en la base de datos.")
            return
        selected = st.sidebar.selectbox("Tienda", list(shops.keys()))
        filter_label = selected
        shop_id = shops[selected]
        logger.info("Filtro: tienda=%s (id=%s)", selected, shop_id)

        with st.spinner("Cargando pronósticos..."):
            try:
                df = _load_by_store(shop_id)
            except Exception as exc:
                st.error("Error al consultar predicciones por tienda.")
                logger.exception("Error _load_by_store: %s", exc)
                return

    else:  # Categoría
        if not categories:
            st.warning("No hay categorías disponibles en la base de datos.")
            return
        selected = st.sidebar.selectbox("Categoría", categories)
        filter_label = selected
        logger.info("Filter: category=%s", selected)

        with st.spinner("Cargando pronósticos..."):
            try:
                df = _load_by_category(selected)
            except Exception as exc:
                st.error("Error al consultar predicciones por categoría.")
                logger.exception("Error _load_by_category: %s", exc)
                return

    if df.empty:
        st.info("No hay pronósticos disponibles para la selección actual.")
        return

    # ── Separar histórico vs próxima temporada ────────────────────────────────
    historical = df[df["actual"].notna()].copy()
    next_season = df[df["actual"].isna()].copy()

    # ── KPIs ──────────────────────────────────────────────────────────────────
    st.subheader(f"📌 {filter_label}")
    col1, col2, col3 = st.columns(3)

    with col1:
        total_next = next_season["predicted"].sum() if not next_season.empty else 0.0
        _kpi("Unidades Proyectadas — Próxima Temporada", _format_units(total_next))

    with col2:
        total_hist = historical["actual"].sum() if not historical.empty else 0.0
        _kpi("Unidades Reales — Última Temporada", _format_units(total_hist))

    with col3:
        if total_hist > 0:
            delta_pct = (total_next - total_hist) / total_hist * 100
            _kpi("Variación Anual", f"{delta_pct:+.1f}%")
        else:
            _kpi("Variación Anual", "N/A")

    st.divider()

    # ── Gráfico principal: histórico + proyección ─────────────────────────────
    st.subheader("📈 Tendencia: Histórico vs Pronóstico Próxima Temporada")

    chart_df = df.set_index("date")[["actual", "predicted"]].rename(
        columns={"actual": "Real (histórico)", "predicted": "Pronóstico"}
    )
    # Solo mostrar columnas con al menos un valor
    chart_df = chart_df[[c for c in chart_df.columns if chart_df[c].notna().any()]]
    st.line_chart(chart_df, use_container_width=True)

    # ── Tabla próxima temporada ───────────────────────────────────────────────
    if not next_season.empty:
        st.subheader("🔮 Detalle de Proyección — Próxima Temporada")
        display = next_season[["date", "predicted"]].copy()
        display.columns = ["Mes", "Unidades Proyectadas"]
        display["Month"] = display["Month"].dt.strftime("%Y-%m")
        display["Predicted Units"] = display["Predicted Units"].map("{:,.0f}".format)
        st.dataframe(display, use_container_width=True, hide_index=True)
    else:
        st.info("No hay pronósticos futuros disponibles para la selección actual.")

    # ── Tabla histórico ───────────────────────────────────────────────────────
    with st.expander("📋 Datos históricos (backtest)"):
        if historical.empty:
            st.write("Sin datos históricos con valores reales.")
        else:
            hist_display = historical[["date", "predicted", "actual"]].copy()
            hist_display.columns = ["Mes", "Pronóstico", "Real"]
            hist_display["Month"] = hist_display["Month"].dt.strftime("%Y-%m")
            hist_display["Predicted"] = hist_display["Predicted"].map("{:,.0f}".format)
            hist_display["Actual"] = hist_display["Actual"].map("{:,.0f}".format)
            st.dataframe(hist_display, use_container_width=True, hide_index=True)
