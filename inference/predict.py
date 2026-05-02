"""Funciones de inferencia: backtest sobre validación y forecast del mes siguiente."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd

from config import ModelConfig
from etl.features import build_features, make_modeling_dataset, temporal_split
from utils.logging import get_logger, setup_logging

setup_logging()
logger = get_logger(__name__)


def load_model(model_path: Path) -> tuple[Any, dict]:
    """Carga el modelo y sus metadatos del JSON adyacente.

    Args:
        model_path: Ruta al modelo serializado (.pkl).

    Returns:
        Tupla (model, metadata_dict).
    """
    model_path = Path(model_path)
    model = joblib.load(model_path)
    metadata_path = model_path.with_suffix(".json")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    return model, metadata


def _build_output_df(
    shop_ids: np.ndarray,
    item_ids: np.ndarray,
    forecast_dates,
    predicted_units: np.ndarray,
    actual_units,
) -> pd.DataFrame:
    """Construye el DataFrame de salida con tipos compatibles con RDS."""
    n = len(shop_ids)
    return pd.DataFrame(
        {
            "shop_id": shop_ids.astype(np.int64),
            "item_id": item_ids.astype(np.int64),
            "forecast_date": forecast_dates,
            "predicted_units": predicted_units.astype(np.float64),
            "actual_units": actual_units,
            "created_at": pd.Timestamp.utcnow(),
            "batch_job_id": pd.array([pd.NA] * n, dtype="Int64"),
        }
    )


def generate_backtest(
    model_path: Path,
    data_path: Path,
    output_path: Path,
    cfg: ModelConfig | None = None,
) -> dict:
    """Predice sobre el validation set usando el mismo split que evaluation/.

    Args:
        model_path: Ruta al modelo serializado (.pkl).
        data_path: Ruta al parquet preparado (monthly_with_lags.parquet).
        output_path: Ruta donde guardar el parquet de backtest.
        cfg: Configuración del modelo. Si es None, usa defaults.

    Returns:
        Dict con n_rows, output_path, date_min, date_max.
    """
    if cfg is None:
        cfg = ModelConfig()

    model_path = Path(model_path)
    data_path = Path(data_path)
    output_path = Path(output_path)

    model, metadata = load_model(model_path)
    feature_cols = metadata["features"]

    df = pd.read_parquet(data_path)
    df_feat = build_features(df, cfg)
    df_model, _ = make_modeling_dataset(df_feat, cfg)
    _, valid_df = temporal_split(df_model, cfg)

    x_valid = valid_df[feature_cols]
    y_pred = np.clip(model.predict(x_valid), cfg.clip_pred_min, None)

    forecast_dates = pd.to_datetime(valid_df[cfg.time_col]).dt.date

    out_df = _build_output_df(
        shop_ids=valid_df["shop_id"].to_numpy(),
        item_ids=valid_df["item_id"].to_numpy(),
        forecast_dates=forecast_dates.to_numpy(),
        predicted_units=y_pred,
        actual_units=valid_df[cfg.target_col].to_numpy().astype(np.float64),
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_parquet(output_path, index=False)

    date_min = out_df["forecast_date"].min()
    date_max = out_df["forecast_date"].max()

    logger.info(
        "Backtest generado | n_rows=%d | date_min=%s | date_max=%s | output=%s",
        len(out_df),
        date_min,
        date_max,
        output_path,
    )

    return {
        "n_rows": len(out_df),
        "output_path": str(output_path),
        "date_min": str(date_min),
        "date_max": str(date_max),
    }


def generate_forecasts(
    model_path: Path,
    data_path: Path,
    output_path: Path,
    cfg: ModelConfig | None = None,
) -> dict:
    """Genera predicciones del mes siguiente al último observado.

    Usa las filas del último mes disponible (con sus lags/rolls ya calculados)
    como input para predecir el período siguiente.

    Args:
        model_path: Ruta al modelo serializado (.pkl).
        data_path: Ruta al parquet preparado (monthly_with_lags.parquet).
        output_path: Ruta donde guardar el parquet de forecasts.
        cfg: Configuración del modelo. Si es None, usa defaults.

    Returns:
        Dict con n_rows, output_path, forecast_date.
    """
    if cfg is None:
        cfg = ModelConfig()

    model_path = Path(model_path)
    data_path = Path(data_path)
    output_path = Path(output_path)

    model, metadata = load_model(model_path)
    feature_cols = metadata["features"]

    df = pd.read_parquet(data_path)
    df_feat = build_features(df, cfg)
    df_model, _ = make_modeling_dataset(df_feat, cfg)

    last_month = df_model[cfg.time_col].max()
    latest_rows = df_model[df_model[cfg.time_col] == last_month].copy()

    x_latest = latest_rows[feature_cols]
    y_pred = np.clip(model.predict(x_latest), cfg.clip_pred_min, None)

    next_month = (pd.Timestamp(last_month) + pd.DateOffset(months=1)).date()
    n = len(latest_rows)

    out_df = _build_output_df(
        shop_ids=latest_rows["shop_id"].to_numpy(),
        item_ids=latest_rows["item_id"].to_numpy(),
        forecast_dates=np.array([next_month] * n),
        predicted_units=y_pred,
        actual_units=np.full(n, np.nan, dtype=np.float64),
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_parquet(output_path, index=False)

    logger.info(
        "Forecasts generados | n_rows=%d | forecast_date=%s | output=%s",
        len(out_df),
        next_month,
        output_path,
    )

    return {
        "n_rows": len(out_df),
        "output_path": str(output_path),
        "forecast_date": str(next_month),
    }
