"""Vista de feedback de negocio.

Permite a los usuarios enviar retroalimentación sobre los pronósticos.
"""

import streamlit as st

from data.rds import execute_query, fetch_query
from utils.logging import get_logger


@st.cache_data(ttl=300, show_spinner=False)
def _load_shop_options() -> dict[str, int]:
    rows = fetch_query("SELECT shop_id, shop_name FROM shops ORDER BY shop_name")
    return {r["shop_name"]: r["shop_id"] for r in rows}


@st.cache_data(ttl=300, show_spinner=False)
def _load_product_options() -> dict[str, int]:
    rows = fetch_query("SELECT item_id, item_name FROM products ORDER BY item_name LIMIT 500")
    return {r["item_name"]: r["item_id"] for r in rows}


def _load_open_issues() -> list[dict]:
    return fetch_query(
        """
        SELECT f.id, s.shop_name, pr.item_name, f.comment, f.status, f.reported_by, f.created_at
        FROM feedback f
        JOIN shops s     ON s.shop_id  = f.shop_id
        JOIN products pr ON pr.item_id = f.item_id
        ORDER BY f.created_at DESC
        LIMIT 50
        """
    )


def render():
    """Renderiza la página de feedback de negocio."""
    logger = get_logger(__name__)
    st.title("Retroalimentación del Negocio")

    # ── Formulario de envío ───────────────────────────────────────────────────────────
    st.subheader("Enviar Retroalimentación")

    try:
        shop_options = _load_shop_options()
        product_options = _load_product_options()
    except Exception as exc:
        st.error("No se pudo cargar el catálogo. Verifica la conexión a RDS.")
        logger.exception("Error cargando catálogos para feedback: %s", exc)
        return

    if not shop_options or not product_options:
        st.warning("No hay tiendas o productos disponibles todavía.")
        return

    col1, col2 = st.columns(2)
    with col1:
        selected_shop = st.selectbox("Tienda", list(shop_options.keys()))
    with col2:
        selected_product = st.selectbox("Producto", list(product_options.keys()))

    reported_by = st.text_input("Tu nombre (opcional)")
    comment = st.text_area("Comentario", placeholder="Describe el problema con este pronóstico...")

    if st.button("Enviar Retroalimentación"):
        if not comment.strip():
            st.warning("El comentario no puede estar vacío.")
            return

        shop_id = shop_options[selected_shop]
        item_id = product_options[selected_product]

        try:
            execute_query(
                """
                INSERT INTO feedback (shop_id, item_id, comment, status, reported_by, created_at)
                VALUES (:shop_id, :item_id, :comment, 'open', :reported_by, NOW())
                """,
                {
                    "shop_id": shop_id,
                    "item_id": item_id,
                    "comment": comment.strip(),
                    "reported_by": reported_by.strip() or None,
                },
            )
            st.success("✅ Feedback guardado correctamente.")
            logger.info("Feedback guardado: shop_id=%s, item_id=%s", shop_id, item_id)
            st.cache_data.clear()
        except Exception as exc:
            st.error("No se pudo guardar el feedback. Intenta nuevamente.")
            logger.exception("Error guardando feedback: %s", exc)

    # ── Tabla de issues reportados ───────────────────────────────────────────
    st.subheader("Retroalimentación Registrada")
    try:
        issues = _load_open_issues()
    except Exception as exc:
        st.error("No se pudieron cargar los issues.")
        logger.exception("Error cargando issues: %s", exc)
        return

    if not issues:
        st.info("No hay feedback registrado todavía.")
    else:
        import pandas as pd
        df = pd.DataFrame(issues)
        df.columns = ["ID", "Tienda", "Producto", "Comentario", "Estado", "Reportado por", "Fecha"]
        st.dataframe(df, use_container_width=True)
