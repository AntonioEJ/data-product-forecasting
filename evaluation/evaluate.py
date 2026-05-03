"""Pipeline de evaluación del modelo de forecasting.

Calcula métricas de error globales y por categoría de producto
usando el mismo split temporal que el pipeline de entrenamiento.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error

from config import ModelConfig
from etl.features import build_features, make_modeling_dataset, temporal_split
from utils.logging import get_logger, setup_logging

setup_logging()
logger = get_logger(__name__)


def compute_metrics_global(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    y_naive: np.ndarray,
) -> dict:
    """Calcula MAE y RMSE del modelo y del baseline naive.

    Args:
        y_true: Valores reales.
        y_pred: Predicciones del modelo.
        y_naive: Predicciones del baseline naive.

    Returns:
        Dict con mae, rmse, mae_naive, rmse_naive, n_obs.
    """
    return {
        "mae": float(mean_absolute_error(y_true, y_pred)),
        "rmse": float(np.sqrt(mean_squared_error(y_true, y_pred))),
        "mae_naive": float(mean_absolute_error(y_true, y_naive)),
        "rmse_naive": float(np.sqrt(mean_squared_error(y_true, y_naive))),
        "n_obs": int(len(y_true)),
    }


def compute_metrics_by_category(
    predictions_df: pd.DataFrame,
    items_df: pd.DataFrame,
    categories_df: pd.DataFrame,
) -> pd.DataFrame:
    """Agrega métricas de error por categoría de producto.

    Args:
        predictions_df: Predicciones con columnas item_id, y_true, y_pred, y_naive.
        items_df: Catálogo de ítems con item_id, item_category_id.
        categories_df: Catálogo de categorías con item_category_id, item_category_name.

    Returns:
        DataFrame con category_name, n_obs, mae, rmse, mae_naive, rmse_naive,
        ordenado por n_obs descendente.
    """
    df = predictions_df.merge(
        items_df[["item_id", "item_category_id"]], on="item_id", how="left"
    )
    df = df.merge(
        categories_df[["item_category_id", "item_category_name"]],
        on="item_category_id",
        how="left",
    )

    def _metrics_per_group(g: pd.DataFrame) -> pd.Series:
        return pd.Series(
            {
                "n_obs": len(g),
                "mae": float(mean_absolute_error(g["y_true"], g["y_pred"])),
                "rmse": float(np.sqrt(mean_squared_error(g["y_true"], g["y_pred"]))),
                "mae_naive": float(mean_absolute_error(g["y_true"], g["y_naive"])),
                "rmse_naive": float(
                    np.sqrt(mean_squared_error(g["y_true"], g["y_naive"]))
                ),
            }
        )

    result = (
        df.groupby("item_category_name")
        .apply(_metrics_per_group)
        .reset_index()
        .rename(columns={"item_category_name": "category_name"})
        .sort_values("n_obs", ascending=False)
        .reset_index(drop=True)
    )

    return result


def run_evaluation(
    model_path: Path,
    data_path: Path,
    items_path: Path,
    categories_path: Path,
    output_path: Path,
    cfg: ModelConfig | None = None,
) -> dict:
    """Orquesta la evaluación: genera predicciones y calcula métricas por categoría.

    Usa el mismo split temporal que el pipeline de entrenamiento.

    Args:
        model_path: Ruta al modelo serializado (.pkl).
        data_path: Ruta al parquet preparado (monthly_with_lags.parquet).
        items_path: Ruta al CSV de ítems (item_id, item_category_id).
        categories_path: Ruta al CSV de categorías (item_category_id, item_category_name).
        output_path: Ruta donde guardar el parquet de métricas por categoría.
        cfg: Configuración del modelo. Si es None, usa defaults.

    Returns:
        Dict con n_categories, n_obs, output_path, global_metrics.
    """
    if cfg is None:
        cfg = ModelConfig()

    model_path = Path(model_path)
    data_path = Path(data_path)
    output_path = Path(output_path)

    model = joblib.load(model_path)

    df = pd.read_parquet(data_path)
    df_feat = build_features(df, cfg)
    df_model, feature_cols = make_modeling_dataset(df_feat, cfg)
    _, valid_df = temporal_split(df_model, cfg)

    x_valid = valid_df[feature_cols]
    y_true = valid_df[cfg.target_col].to_numpy()
    y_pred = np.clip(model.predict(x_valid), cfg.clip_pred_min, None)
    # lag_1 es el último valor observado por (shop, item) — baseline naive
    y_naive = valid_df["lag_1"].to_numpy()

    predictions_df = pd.DataFrame(
        {
            "item_id": valid_df["item_id"].to_numpy(),
            "y_true": y_true,
            "y_pred": y_pred,
            "y_naive": y_naive,
        }
    )

    items_df = pd.read_csv(items_path)
    categories_df = pd.read_csv(categories_path)

    metrics_df = compute_metrics_by_category(predictions_df, items_df, categories_df)
    metrics_df["computed_at"] = datetime.now(tz=timezone.utc)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    metrics_df.to_parquet(output_path, index=False)

    global_metrics = compute_metrics_global(y_true, y_pred, y_naive)

    logger.info(
        "Métricas globales | MAE=%.4f | RMSE=%.4f | MAE_naive=%.4f | RMSE_naive=%.4f | n_obs=%d",
        global_metrics["mae"],
        global_metrics["rmse"],
        global_metrics["mae_naive"],
        global_metrics["rmse_naive"],
        global_metrics["n_obs"],
    )

    n_categories = len(metrics_df)
    n_obs = int(metrics_df["n_obs"].sum())

    logger.info(
        "Evaluación completada | n_categories=%d | n_obs=%d | output=%s",
        n_categories,
        n_obs,
        output_path,
    )

    return {
        "n_categories": n_categories,
        "n_obs": n_obs,
        "output_path": str(output_path),
        "global_metrics": global_metrics,
    }
