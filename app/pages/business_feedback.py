"""Vista de feedback de negocio.

Permite a los usuarios reportar problemas con los pronósticos y consultar
el historial de reportes.
"""

import streamlit as st

from app.components.db_helpers import (
    get_feedback_list,
    get_shops_list,
    submit_feedback,
)
from data.rds import fetch_query
from utils.logging import get_logger


def _buscar_producto(item_id: int) -> dict | None:
    """Busca un producto por item_id.

    Args:
        item_id: ID del producto.

    Returns:
        Dict con item_name y category_name, o None si no existe.
    """
    rows = fetch_query(
        "SELECT item_name, category_name FROM products WHERE item_id = :item_id LIMIT 1",
        {"item_id": item_id},
    )
    return rows[0] if rows else None


def render():
    """Renderiza la página de feedback de negocio."""
    logger = get_logger(__name__)
    st.title("Feedback de Negocio")
    logger.info("Renderizando vista de feedback de negocio")

    # ── Filtro de estado en sidebar ───────────────────────────────────────────
    st.sidebar.header("Filtros — Productos Reportados")
    status_opciones = {"Todos": None, "open": "open", "reviewed": "reviewed", "resolved": "resolved"}
    selected_status_label = st.sidebar.selectbox(
        "Estado", list(status_opciones.keys()), index=1
    )
    selected_status = status_opciones[selected_status_label]

    # ── Formulario de envío ───────────────────────────────────────────────────
    st.subheader("Enviar Feedback")

    try:
        df_shops = get_shops_list()
    except Exception as exc:
        st.error(f"Error al cargar tiendas: {exc}\n\nVerifica conectividad a RDS.")
        logger.error("Error al cargar tiendas: %s", exc)
        df_shops = None

    if df_shops is not None and not df_shops.empty:
        col_form, col_info = st.columns([2, 1])

        with col_form:
            shop_map = {row["shop_name"]: int(row["shop_id"]) for _, row in df_shops.iterrows()}
            selected_shop_name = st.selectbox("Tienda", list(shop_map.keys()), key="fb_shop")
            selected_shop_id = shop_map[selected_shop_name]

            item_id_input = st.number_input(
                "Item ID del producto", min_value=1, step=1, value=1, key="fb_item_id"
            )

            producto_info = None
            if st.button("Buscar producto"):
                try:
                    producto_info = _buscar_producto(int(item_id_input))
                    if producto_info:
                        st.session_state["fb_producto_info"] = producto_info
                        st.session_state["fb_item_id_confirmado"] = int(item_id_input)
                    else:
                        st.warning(f"No se encontró el producto con item_id={item_id_input}.")
                        st.session_state.pop("fb_producto_info", None)
                        st.session_state.pop("fb_item_id_confirmado", None)
                except Exception as exc:
                    st.error(f"Error al buscar producto: {exc}")
                    logger.error("Error al buscar producto: %s", exc)

        with col_info:
            if "fb_producto_info" in st.session_state:
                info = st.session_state["fb_producto_info"]
                st.info(
                    f"**{info['item_name']}**\n\nCategoría: {info['category_name']}"
                )

        comentario = st.text_area(
            "Comentario", max_chars=1000, key="fb_comentario",
            help="Describe el problema con el pronóstico (máx. 1000 caracteres)."
        )
        reported_by = st.text_input(
            "Tu nombre o equipo (opcional)", key="fb_reported_by"
        )

        if st.button("Enviar", type="primary"):
            item_id_confirmado = st.session_state.get("fb_item_id_confirmado")

            if not item_id_confirmado:
                st.warning("Busca y confirma un producto antes de enviar.")
            elif not comentario.strip():
                st.warning("El comentario no puede estar vacío.")
            else:
                try:
                    resultado = submit_feedback(
                        shop_id=selected_shop_id,
                        item_id=item_id_confirmado,
                        comment=comentario.strip(),
                        reported_by=reported_by.strip() or None,
                    )
                    if resultado == 1:
                        st.success("Feedback enviado correctamente.")
                        logger.info(
                            "Feedback enviado — shop_id=%d, item_id=%d",
                            selected_shop_id,
                            item_id_confirmado,
                        )
                        # Limpiar estado del formulario
                        for key in ["fb_producto_info", "fb_item_id_confirmado"]:
                            st.session_state.pop(key, None)
                        st.rerun()
                    else:
                        st.error("No se pudo guardar el feedback. Verifica conectividad a RDS.")
                except Exception as exc:
                    st.error(f"Error al enviar feedback: {exc}\n\nVerifica conectividad a RDS.")
                    logger.error("Error al enviar feedback: %s", exc)

    # ── Listado de reportes ───────────────────────────────────────────────────
    st.subheader("Productos Reportados")
    try:
        df_feedback = get_feedback_list(status_filter=selected_status)

        if df_feedback.empty:
            st.info("Aún no hay productos reportados.")
        else:
            st.dataframe(df_feedback, use_container_width=True)

    except Exception as exc:
        st.error(
            f"Error al cargar el listado de feedback: {exc}\n\nVerifica conectividad a RDS."
        )
        logger.error("Error en listado de feedback: %s", exc)
