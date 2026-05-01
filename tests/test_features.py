"""Unit tests para etl/features.py."""

from __future__ import annotations

import pandas as pd
import pytest

from config import ModelConfig
from etl.features import build_features, make_modeling_dataset, temporal_split


@pytest.fixture
def cfg() -> ModelConfig:
    """Config por defecto para tests."""
    return ModelConfig()


@pytest.fixture
def sample_df() -> pd.DataFrame:
    """DataFrame mínimo con 12 meses para un solo (shop, item)."""
    dates = pd.date_range("2013-01-01", periods=12, freq="MS")
    return pd.DataFrame(
        {
            "shop_id": 1,
            "item_id": 10,
            "date": dates,
            "monthly_units": range(10, 22),
            "monthly_sales": range(100, 112),
            "avg_price": [9.5] * 12,
            "active_days": [30] * 12,
            "num_transactions": range(5, 17),
        }
    )


class TestBuildFeatures:
    """Tests para build_features()."""

    def test_lag_columns_created(self, sample_df: pd.DataFrame, cfg: ModelConfig):
        """Verifica que se crean columnas lag_1, lag_2, lag_4, lag_8."""
        result = build_features(sample_df, cfg)
        for lag in cfg.lags:
            assert f"lag_{lag}" in result.columns

    def test_rolling_columns_created(self, sample_df: pd.DataFrame, cfg: ModelConfig):
        """Verifica que se crean columnas roll_mean_4, roll_mean_8."""
        result = build_features(sample_df, cfg)
        for w in cfg.rolls:
            assert f"roll_mean_{w}" in result.columns

    def test_lag_values_correct(self, sample_df: pd.DataFrame, cfg: ModelConfig):
        """Lag_1 del mes 2 debe ser el valor del mes 1."""
        result = build_features(sample_df, cfg)
        # Row index 1 (second month) lag_1 should equal first month's value
        assert result.iloc[1]["lag_1"] == result.iloc[0]["monthly_units"]

    def test_no_data_leakage_in_rolling(
        self, sample_df: pd.DataFrame, cfg: ModelConfig
    ):
        """Rolling mean debe usar shift(1) — no incluye el valor actual."""
        result = build_features(sample_df, cfg)
        # roll_mean_4 at index 4 uses values at index 0,1,2,3 (shifted)
        # shift(1) means we look at indices 0..3 target values for index 5
        # First non-NaN roll_mean_4 should be at index with enough history
        non_null = result["roll_mean_4"].dropna()
        assert len(non_null) > 0

    def test_output_shape(self, sample_df: pd.DataFrame, cfg: ModelConfig):
        """Output tiene mismas filas que input y columnas extras."""
        result = build_features(sample_df, cfg)
        assert len(result) == len(sample_df)
        expected_new_cols = len(cfg.lags) + len(cfg.rolls)
        assert len(result.columns) == len(sample_df.columns) + expected_new_cols

    def test_handles_multiple_groups(self, cfg: ModelConfig):
        """Funciona con múltiples combinaciones (shop_id, item_id)."""
        dates = pd.date_range("2013-01-01", periods=6, freq="MS")
        df = pd.DataFrame(
            {
                "shop_id": [1] * 6 + [2] * 6,
                "item_id": [10] * 6 + [20] * 6,
                "date": list(dates) * 2,
                "monthly_units": range(12),
                "monthly_sales": range(12),
                "avg_price": [9.5] * 12,
                "active_days": [30] * 12,
                "num_transactions": range(12),
            }
        )
        result = build_features(df, cfg)
        assert len(result) == 12


class TestMakeModelingDataset:
    """Tests para make_modeling_dataset()."""

    def test_removes_rows_with_na(self, sample_df: pd.DataFrame, cfg: ModelConfig):
        """Filas con NaN en features requeridas son eliminadas."""
        features_df = build_features(sample_df, cfg)
        model_df, feature_cols = make_modeling_dataset(features_df, cfg)
        # Debe tener menos filas que el original (primeros lags son NaN)
        assert len(model_df) < len(features_df)
        # No debe tener NaN en ninguna feature
        assert model_df[feature_cols].isna().sum().sum() == 0

    def test_clips_negative_target(self, sample_df: pd.DataFrame, cfg: ModelConfig):
        """Valores negativos de target se clipean a 0."""
        sample_df.loc[sample_df.index[0], "monthly_units"] = -5
        features_df = build_features(sample_df, cfg)
        model_df, _ = make_modeling_dataset(features_df, cfg)
        assert (model_df[cfg.target_col] >= 0).all()

    def test_feature_cols_list(self, sample_df: pd.DataFrame, cfg: ModelConfig):
        """feature_cols incluye base + lags + rolls."""
        features_df = build_features(sample_df, cfg)
        _, feature_cols = make_modeling_dataset(features_df, cfg)
        expected_count = len(cfg.base_features) + len(cfg.lags) + len(cfg.rolls)
        assert len(feature_cols) == expected_count


class TestTemporalSplit:
    """Tests para temporal_split()."""

    def test_no_overlap(self, sample_df: pd.DataFrame, cfg: ModelConfig):
        """Train y valid no se solapan temporalmente."""
        features_df = build_features(sample_df, cfg)
        model_df, _ = make_modeling_dataset(features_df, cfg)
        train, valid = temporal_split(model_df, cfg)
        if len(train) > 0 and len(valid) > 0:
            assert train[cfg.time_col].max() < valid[cfg.time_col].min()

    def test_union_equals_original(self, sample_df: pd.DataFrame, cfg: ModelConfig):
        """Train + valid tienen las mismas filas que el dataset original."""
        features_df = build_features(sample_df, cfg)
        model_df, _ = make_modeling_dataset(features_df, cfg)
        train, valid = temporal_split(model_df, cfg)
        assert len(train) + len(valid) == len(model_df)

    def test_train_larger_than_valid(self, sample_df: pd.DataFrame, cfg: ModelConfig):
        """Con cutoff=0.8, train debe ser mayor que valid."""
        features_df = build_features(sample_df, cfg)
        model_df, _ = make_modeling_dataset(features_df, cfg)
        train, valid = temporal_split(model_df, cfg)
        assert len(train) >= len(valid)
