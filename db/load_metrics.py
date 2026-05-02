"""Carga métricas por categoría a RDS desde parquet."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from sqlalchemy.engine import Engine

from db.schema import metrics
from utils.logging import get_logger

logger = get_logger(__name__)


def load_metrics(metrics_path: str | Path, engine: Engine) -> int:
    """Lee metrics_by_category.parquet y carga la tabla metrics.

    Se descarta la columna n_obs (no está en el schema).
    El campo id es autoincrement — no se incluye en el INSERT.

    Args:
        metrics_path: Ruta a metrics_by_category.parquet.
        engine: Engine SQLAlchemy activo.

    Returns:
        Número de filas insertadas.
    """
    df = pd.read_parquet(metrics_path)

    cols = ["category_name", "mae", "rmse", "mae_naive", "rmse_naive", "computed_at"]
    df = df[cols]

    registros = df.to_dict(orient="records")

    with engine.begin() as conn:
        conn.execute(metrics.delete())
        conn.execute(metrics.insert(), registros)

    logger.info("metrics cargadas: %d filas", len(registros))
    return len(registros)
