"""Helpers cacheados para consultas a RDS desde las vistas de Streamlit."""

import pandas as pd
import streamlit as st

from data.rds import execute_query, fetch_query
from utils.logging import get_logger

logger = get_logger(__name__)


@st.cache_data(ttl=300)
def get_metrics_by_category() -> pd.DataFrame:
    """Retorna métricas de error por categoría ordenadas por número de observaciones.

    Returns:
        DataFrame con columnas: category_name, n_obs, mae, rmse,
        mae_naive, rmse_naive, computed_at.
    """
    rows = fetch_query(
        """
        SELECT category_name, n_obs, mae, rmse, mae_naive, rmse_naive, computed_at
        FROM metrics
        ORDER BY n_obs DESC
        """
    )
    logger.info("get_metrics_by_category — %d filas", len(rows))
    return pd.DataFrame(rows)


@st.cache_data(ttl=300)
def get_predictions_with_actuals(
    category_name: str | None = None,
    shop_id: int | None = None,
    limit: int = 1000,
) -> pd.DataFrame:
    """Retorna predicciones con valor actual para comparar vs modelo.

    Hace JOIN de predictions con products y shops.
    Solo devuelve filas donde actual_units IS NOT NULL.

    Args:
        category_name: Filtrar por categoría. None = todas.
        shop_id: Filtrar por tienda. None = todas.
        limit: Número máximo de filas a retornar.

    Returns:
        DataFrame con columnas: forecast_date, shop_id, shop_name,
        item_id, item_name, category_name, predicted_units, actual_units.
    """
    query = """
        SELECT
            pr.forecast_date,
            pr.shop_id,
            s.shop_name,
            pr.item_id,
            p.item_name,
            p.category_name,
            pr.predicted_units,
            pr.actual_units
        FROM predictions pr
        JOIN products p ON p.item_id = pr.item_id
        JOIN shops s ON s.shop_id = pr.shop_id
        WHERE pr.actual_units IS NOT NULL
          AND (:category_name IS NULL OR p.category_name = :category_name)
          AND (:shop_id IS NULL OR pr.shop_id = :shop_id)
        ORDER BY pr.forecast_date DESC, pr.item_id
        LIMIT :limit
    """
    params = {
        "category_name": category_name,
        "shop_id": shop_id,
        "limit": limit,
    }
    rows = fetch_query(query, params)
    logger.info(
        "get_predictions_with_actuals — %d filas (cat=%s, shop=%s)",
        len(rows),
        category_name,
        shop_id,
    )
    return pd.DataFrame(rows)


@st.cache_data(ttl=300)
def get_categories_list() -> list[str]:
    """Retorna lista de categorías de productos únicas.

    Returns:
        Lista de strings ordenada alfabéticamente.
    """
    rows = fetch_query(
        """
        SELECT DISTINCT category_name
        FROM products
        ORDER BY category_name
        """
    )
    return [r["category_name"] for r in rows]


@st.cache_data(ttl=300)
def get_shops_list() -> pd.DataFrame:
    """Retorna lista de tiendas con id y nombre.

    Returns:
        DataFrame con columnas: shop_id, shop_name.
    """
    rows = fetch_query(
        """
        SELECT shop_id, shop_name
        FROM shops
        ORDER BY shop_name
        """
    )
    return pd.DataFrame(rows)


@st.cache_data(ttl=300)
def get_feedback_list(status_filter: str | None = None) -> pd.DataFrame:
    """Retorna el listado de feedback con join a shops y products.

    Args:
        status_filter: Filtrar por status ('open', 'reviewed', 'resolved').
                       None = todos.

    Returns:
        DataFrame con columnas: id, shop_id, shop_name, item_id, item_name,
        category_name, comment, status, reported_by, created_at.
    """
    rows = fetch_query(
        """
        SELECT
            f.id,
            f.shop_id,
            s.shop_name,
            f.item_id,
            p.item_name,
            p.category_name,
            f.comment,
            f.status,
            f.reported_by,
            f.created_at
        FROM feedback f
        JOIN shops s ON s.shop_id = f.shop_id
        JOIN products p ON p.item_id = f.item_id
        WHERE (:status_filter IS NULL OR f.status = :status_filter)
        ORDER BY f.created_at DESC
        """,
        {"status_filter": status_filter},
    )
    logger.info("get_feedback_list — %d filas (status=%s)", len(rows), status_filter)
    return pd.DataFrame(rows)


def submit_feedback(
    shop_id: int,
    item_id: int,
    comment: str,
    reported_by: str | None,
) -> int:
    """Inserta un registro de feedback en RDS.

    Args:
        shop_id: ID de la tienda.
        item_id: ID del producto.
        comment: Comentario del usuario (máx 1000 chars).
        reported_by: Nombre o equipo que reporta. Puede ser None.

    Returns:
        1 si la inserción fue exitosa, 0 si falló.
    """
    try:
        execute_query(
            """
            INSERT INTO feedback (shop_id, item_id, comment, status, reported_by, created_at)
            VALUES (:shop_id, :item_id, :comment, 'open', :reported_by, NOW())
            """,
            {
                "shop_id": shop_id,
                "item_id": item_id,
                "comment": comment,
                "reported_by": reported_by or None,
            },
        )
        get_feedback_list.clear()
        logger.info("Feedback insertado — shop_id=%d, item_id=%d", shop_id, item_id)
        return 1
    except Exception as exc:
        logger.error("Error al insertar feedback: %s", exc)
        return 0
