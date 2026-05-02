"""Tests sintéticos para inference/predict.py."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import joblib
import numpy as np
import pandas as pd
import pytest

from config import ModelConfig
from inference.predict import generate_backtest, generate_forecasts, load_model


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def cfg():
    return ModelConfig()


@pytest.fixture
def feature_cols():
    cfg = ModelConfig()
    return (
        list(cfg.base_features)
        + [f"lag_{lag}" for lag in cfg.lags]
        + [f"roll_mean_{w}" for w in cfg.rolls]
    )


@pytest.fixture
def fake_metadata(feature_cols):
    return {"features": feature_cols}


@pytest.fixture
def fake_model(feature_cols):
    """Stub de modelo: predict retorna un valor proporcional al número de filas."""
    model = MagicMock()
    model.predict.side_effect = lambda x: np.ones(len(x)) * 5.0
    return model


@pytest.fixture
def fake_df(feature_cols):
    """DataFrame mínimo que simula el output de make_modeling_dataset."""
    n = 3
    base = {
        "shop_id": [1, 2, 3],
        "item_id": [10, 20, 30],
        "date": pd.to_datetime(["2015-08-31", "2015-09-30", "2015-10-31"]),
        "monthly_units": [5.0, 3.0, 2.0],
        "monthly_sales": [100.0, 60.0, 40.0],
        "avg_price": [20.0, 20.0, 20.0],
        "active_days": [30, 30, 30],
        "num_transactions": [5, 3, 2],
    }
    for col in feature_cols:
        if col not in base:
            base[col] = [1.0] * n
    return pd.DataFrame(base)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_load_model_devuelve_tupla(tmp_path, fake_model, fake_metadata):
    model_path = tmp_path / "model.pkl"
    joblib.dump(fake_model, model_path)
    (tmp_path / "model.json").write_text(json.dumps(fake_metadata), encoding="utf-8")

    result = load_model(model_path)

    assert isinstance(result, tuple)
    assert len(result) == 2


def test_generate_backtest_columnas(tmp_path, fake_model, fake_metadata, fake_df, cfg):
    """Smoke test: el parquet de backtest tiene exactamente las columnas esperadas."""
    output_path = tmp_path / "backtest.parquet"

    with (
        patch("inference.predict.load_model", return_value=(fake_model, fake_metadata)),
        patch("inference.predict.pd.read_parquet", return_value=fake_df),
        patch("inference.predict.build_features", return_value=fake_df),
        patch("inference.predict.make_modeling_dataset", return_value=(fake_df, fake_metadata["features"])),
        patch("inference.predict.temporal_split", return_value=(fake_df, fake_df)),
    ):
        generate_backtest(tmp_path / "model.pkl", tmp_path / "data.parquet", output_path, cfg)

    out = pd.read_parquet(output_path)
    expected_cols = {"shop_id", "item_id", "forecast_date", "predicted_units", "actual_units", "created_at", "batch_job_id"}
    assert set(out.columns) == expected_cols
    assert out["shop_id"].dtype == np.dtype("int64")
    assert out["item_id"].dtype == np.dtype("int64")
    assert out["predicted_units"].dtype == np.dtype("float64")
    assert out["actual_units"].dtype == np.dtype("float64")


def test_generate_forecasts_actuals_null(tmp_path, fake_model, fake_metadata, fake_df, cfg):
    """En forecasts, todas las actual_units deben ser null."""
    output_path = tmp_path / "forecasts.parquet"

    with (
        patch("inference.predict.load_model", return_value=(fake_model, fake_metadata)),
        patch("inference.predict.pd.read_parquet", return_value=fake_df),
        patch("inference.predict.build_features", return_value=fake_df),
        patch("inference.predict.make_modeling_dataset", return_value=(fake_df, fake_metadata["features"])),
    ):
        generate_forecasts(tmp_path / "model.pkl", tmp_path / "data.parquet", output_path, cfg)

    out = pd.read_parquet(output_path)
    assert out["actual_units"].isna().all()


def test_generate_backtest_actuals_no_null(tmp_path, fake_model, fake_metadata, fake_df, cfg):
    """En backtest, las actual_units no deben ser null."""
    output_path = tmp_path / "backtest.parquet"

    with (
        patch("inference.predict.load_model", return_value=(fake_model, fake_metadata)),
        patch("inference.predict.pd.read_parquet", return_value=fake_df),
        patch("inference.predict.build_features", return_value=fake_df),
        patch("inference.predict.make_modeling_dataset", return_value=(fake_df, fake_metadata["features"])),
        patch("inference.predict.temporal_split", return_value=(fake_df, fake_df)),
    ):
        generate_backtest(tmp_path / "model.pkl", tmp_path / "data.parquet", output_path, cfg)

    out = pd.read_parquet(output_path)
    assert out["actual_units"].notna().all()


def test_predicciones_no_negativas(tmp_path, fake_model, fake_metadata, fake_df, cfg):
    """Tras clipping, todos los predicted_units deben ser >= 0."""
    # El modelo devuelve valores negativos que deben ser clippeados
    fake_model.predict.side_effect = lambda x: np.array([-1.0, -0.5, 3.0][: len(x)])
    output_path = tmp_path / "backtest.parquet"

    with (
        patch("inference.predict.load_model", return_value=(fake_model, fake_metadata)),
        patch("inference.predict.pd.read_parquet", return_value=fake_df),
        patch("inference.predict.build_features", return_value=fake_df),
        patch("inference.predict.make_modeling_dataset", return_value=(fake_df, fake_metadata["features"])),
        patch("inference.predict.temporal_split", return_value=(fake_df, fake_df)),
    ):
        generate_backtest(tmp_path / "model.pkl", tmp_path / "data.parquet", output_path, cfg)

    out = pd.read_parquet(output_path)
    assert (out["predicted_units"] >= 0).all()
