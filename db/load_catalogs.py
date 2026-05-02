"""Carga catálogos de productos y tiendas a RDS desde CSV."""

from __future__ import annotations

import math
from pathlib import Path

import pandas as pd
from sqlalchemy.engine import Engine

from db.schema import products, shops
from utils.logging import get_logger

logger = get_logger(__name__)

_BATCH = 5000


def load_products(items_path: str | Path, categories_path: str | Path, engine: Engine) -> int:
    """Lee items.csv y categories, hace merge y carga la tabla products.

    Args:
        items_path: Ruta a items.csv.
        categories_path: Ruta a item_categories_en.csv.
        engine: Engine SQLAlchemy activo.

    Returns:
        Número de filas insertadas.
    """
    items = pd.read_csv(items_path)
    cats = pd.read_csv(categories_path)

    df = items.merge(cats, on="item_category_id", how="left")
    df = df.rename(columns={"item_category_name": "category_name"})
    df = df[["item_id", "item_name", "category_name"]]

    registros = df.to_dict(orient="records")

    with engine.begin() as conn:
        conn.execute(products.delete())
        for i in range(0, len(registros), _BATCH):
            conn.execute(products.insert(), registros[i : i + _BATCH])

    logger.info("products cargados: %d filas", len(registros))
    return len(registros)


def load_shops(shops_path: str | Path, engine: Engine) -> int:
    """Lee shops_en.csv y carga la tabla shops.

    city queda nullable para MVP; parsear shop_name para extraer ciudad
    queda como mejora futura.

    Args:
        shops_path: Ruta a shops_en.csv (versión en inglés).
        engine: Engine SQLAlchemy activo.

    Returns:
        Número de filas insertadas.
    """
    df = pd.read_csv(shops_path)
    df = df[["shop_id", "shop_name"]]
    df = df.assign(city=None)

    registros = df.to_dict(orient="records")

    with engine.begin() as conn:
        conn.execute(shops.delete())
        for i in range(0, len(registros), _BATCH):
            conn.execute(shops.insert(), registros[i : i + _BATCH])

    logger.info("shops cargados: %d filas", len(registros))
    return len(registros)
