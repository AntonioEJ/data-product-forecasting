"""
Feature engineering para el pipeline.

Toma como base el dataset mensual generado por ETL y agrega:
- lags adicionales (1,2,4,8) sobre monthly_units
- rolling means (4,8) usando solo pasado (shift(1) antes de rolling)
"""

from __future__ import annotations

import pandas as pd

from src.config import ModelConfig


def build_features(df: pd.DataFrame, cfg: ModelConfig) -> pd.DataFrame:
    """
    Construye features de series de tiempo por (shop_id, item_id).

    Args:
        df: Dataset mensual base (output de ETL).
        cfg: Configuración del modelo.

    Returns:
        DataFrame con features adicionales.
    """
    key_1, key_2 = cfg.key_cols
    time_col = cfg.time_col
    target = cfg.target_col

    df = df.copy()
    df[time_col] = pd.to_datetime(df[time_col], errors="coerce")
    df = df.dropna(subset=[time_col]).sort_values([key_1, key_2, time_col])

    df_mi = df.set_index([key_1, key_2, time_col]).sort_index()

    for lag in cfg.lags:
        df_mi[f"lag_{lag}"] = df_mi.groupby(level=[key_1, key_2])[target].shift(lag)

    for w in cfg.rolls:
        df_mi[f"roll_mean_{w}"] = (
            df_mi.groupby(level=[key_1, key_2])[target]
            .shift(1)
            .rolling(window=w, min_periods=w)
            .mean()
        )

    return df_mi.reset_index()


def make_modeling_dataset(
    df_feat: pd.DataFrame, cfg: ModelConfig
) -> tuple[pd.DataFrame, list[str]]:
    """
    Genera dataset final eliminando NA en target/features.

    Args:
        df_feat: DataFrame con features.
        cfg: Configuración.

    Returns:
        (df_model, feature_cols)
    """
    feature_cols = (
        list(cfg.base_features)
        + [f"lag_{l}" for l in cfg.lags]
        + [f"roll_mean_{w}" for w in cfg.rolls]
    )
    required = [cfg.target_col, cfg.time_col] + feature_cols
    df_model = df_feat.dropna(subset=required).copy()

    # No permitir unidades negativas (concepto del notebook)
    df_model[cfg.target_col] = df_model[cfg.target_col].clip(lower=0)

    return df_model, feature_cols


def temporal_split(
    df_model: pd.DataFrame, cfg: ModelConfig
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Split temporal tipo notebook: cutoff por quantile del tiempo.

    Args:
        df_model: Dataset listo para modelar.
        cfg: Configuración.

    Returns:
        (train_df, valid_df)
    """
    cutoff = df_model[cfg.time_col].quantile(cfg.train_quantile_cutoff)
    train_df = df_model[df_model[cfg.time_col] <= cutoff].copy()
    valid_df = df_model[df_model[cfg.time_col] > cutoff].copy()
    return train_df, valid_df
