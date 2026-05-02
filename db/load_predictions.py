"""Carga predicciones (backtest + forecast futuro) a RDS desde parquets."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from sqlalchemy.engine import Engine

from db.schema import predictions
from utils.logging import get_logger

logger = get_logger(__name__)

_BATCH = 5000


def load_predictions(
    backtest_path: str | Path,
    forecasts_path: str | Path,
    engine: Engine,
) -> dict[str, int]:
    """Concatena backtest y forecasts y los carga en la tabla predictions.

    Transformaciones aplicadas:
    - forecast_date se convierte de object a date puro (requerido por PostgreSQL).
    - batch_job_id con pd.NA se reemplaza por None (SQLAlchemy no acepta pd.NA).
    - actual_units queda null para las filas de forecast futuro.

    Args:
        backtest_path: Ruta a backtest.parquet.
        forecasts_path: Ruta a forecasts.parquet.
        engine: Engine SQLAlchemy activo.

    Returns:
        Dict con n_backtest, n_forecasts, n_total.
    """
    bt = pd.read_parquet(backtest_path)
    fc = pd.read_parquet(forecasts_path)

    n_backtest = len(bt)
    n_forecasts = len(fc)

    df = pd.concat([bt, fc], ignore_index=True)

    df["forecast_date"] = pd.to_datetime(df["forecast_date"]).dt.date

    # pd.NA no es serializable por SQLAlchemy — convertir a None nativo.
    # Usamos list comprehension porque Int64.apply() convierte pd.NA → nan (float)
    # antes de ejecutar el lambda, lo que hace fallar int().
    df["batch_job_id"] = [None if pd.isna(v) else int(v) for v in df["batch_job_id"]]

    # actual_units NaN → None para el INSERT
    df["actual_units"] = df["actual_units"].where(df["actual_units"].notna(), other=None)

    cols = ["shop_id", "item_id", "forecast_date", "predicted_units", "actual_units", "created_at", "batch_job_id"]
    registros = df[cols].to_dict(orient="records")

    with engine.begin() as conn:
        conn.execute(predictions.delete())
        for i in range(0, len(registros), _BATCH):
            conn.execute(predictions.insert(), registros[i : i + _BATCH])

    logger.info("predictions cargadas: %d backtest + %d forecasts = %d total", n_backtest, n_forecasts, len(registros))
    return {"n_backtest": n_backtest, "n_forecasts": n_forecasts, "n_total": len(registros)}
