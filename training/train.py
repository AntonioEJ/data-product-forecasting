"""Pipeline de entrenamiento LightGBM para forecasting de ventas.

Flujo:
  1. Lee el parquet preparado
  2. Genera features (lags/rolls)
  3. Split temporal
  4. Entrena LightGBM
  5. Evalúa contra baseline naive
  6. Persiste el modelo en artifacts/models/
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error

from config import ModelConfig, find_repo_root
from etl.features import build_features, make_modeling_dataset, temporal_split


def _naive_baseline(
    train_df: pd.DataFrame,
    valid_df: pd.DataFrame,
    cfg: ModelConfig,
) -> tuple[float, float]:
    """Calcula MAE y RMSE del baseline naive (último valor observado por shop-item)."""
    key_cols = list(cfg.key_cols)
    target = cfg.target_col

    last_train = (
        train_df.sort_values(cfg.time_col)
        .groupby(key_cols)[target]
        .last()
        .reset_index()
        .rename(columns={target: "naive_pred"})
    )

    df_val = valid_df.merge(last_train, on=key_cols, how="left")
    # Shop-items sin historial en train → media global
    global_mean = float(train_df[target].mean())
    df_val["naive_pred"] = df_val["naive_pred"].fillna(global_mean)

    mae = float(mean_absolute_error(df_val[target], df_val["naive_pred"]))
    rmse = float(np.sqrt(mean_squared_error(df_val[target], df_val["naive_pred"])))
    return mae, rmse


def _fit_lgbm(
    x_train: pd.DataFrame,
    y_train: pd.Series,
    x_valid: pd.DataFrame,
    y_valid: pd.Series,
    cfg: ModelConfig,
) -> Any:
    """Entrena LightGBM con early stopping. Falla explícitamente si no está instalado."""
    try:
        import lightgbm as lgb
    except ImportError as exc:
        raise ImportError(
            "LightGBM no está instalado. Añade 'lightgbm' a las dependencias del proyecto."
        ) from exc

    model = lgb.LGBMRegressor(
        n_estimators=5000,
        learning_rate=0.03,
        num_leaves=63,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=cfg.random_state,
        n_jobs=-1,
    )
    model.fit(
        x_train,
        y_train,
        eval_set=[(x_valid, y_valid)],
        eval_metric="rmse",
        callbacks=[lgb.early_stopping(stopping_rounds=50, verbose=False)],
    )
    return model


def train_pipeline(
    input_parquet: Path,
    output_model: Path,
    cfg: ModelConfig | None = None,
) -> dict:
    """Entrena LightGBM y retorna métricas + path del modelo.

    Args:
        input_parquet: Ruta al parquet preparado (monthly_with_lags.parquet).
        output_model: Ruta donde guardar el modelo serializado (.pkl).
        cfg: Configuración del modelo. Si es None, usa defaults.

    Returns:
        Dict con mae, rmse, mae_naive, rmse_naive, model_path, n_train, n_val.
    """
    if cfg is None:
        cfg = ModelConfig()

    input_parquet = Path(input_parquet)
    output_model = Path(output_model)

    if not input_parquet.exists():
        raise FileNotFoundError(
            f"No existe el dataset preparado: {input_parquet}. "
            "Ejecuta primero el pipeline de ETL."
        )

    t0 = time.time()

    df = pd.read_parquet(input_parquet)
    df_feat = build_features(df, cfg)
    df_model, feature_cols = make_modeling_dataset(df_feat, cfg)
    train_df, valid_df = temporal_split(df_model, cfg)

    x_train = train_df[feature_cols]
    y_train = train_df[cfg.target_col]
    x_valid = valid_df[feature_cols]
    y_valid = valid_df[cfg.target_col]

    mae_naive, rmse_naive = _naive_baseline(train_df, valid_df, cfg)

    model = _fit_lgbm(x_train, y_train, x_valid, y_valid, cfg)

    pred = np.clip(model.predict(x_valid), cfg.clip_pred_min, None)
    mae = float(mean_absolute_error(y_valid, pred))
    rmse = float(np.sqrt(mean_squared_error(y_valid, pred)))

    output_model.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, output_model)

    # Metadata junto al modelo
    metadata = {
        "model_path": output_model.name,
        "dataset": input_parquet.name,
        "target": cfg.target_col,
        "time_col": cfg.time_col,
        "features": feature_cols,
        "n_features": len(feature_cols),
        "clip_pred_min": cfg.clip_pred_min,
        "training_seconds": round(time.time() - t0, 2),
        "metrics": {
            "mae": mae,
            "rmse": rmse,
            "mae_naive": mae_naive,
            "rmse_naive": rmse_naive,
        },
    }
    metadata_path = output_model.with_suffix(".json")
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    return {
        "mae": mae,
        "rmse": rmse,
        "mae_naive": mae_naive,
        "rmse_naive": rmse_naive,
        "model_path": str(output_model),
        "n_train": len(train_df),
        "n_val": len(valid_df),
    }
