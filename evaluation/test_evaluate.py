"""Casos sintéticos para métricas y agregación."""

import math

import numpy as np
import pandas as pd
import pytest

from evaluation.evaluate import compute_metrics_by_category, compute_metrics_global


def test_metrics_perfectas():
    y = np.array([1.0, 2.0, 3.0])
    metrics = compute_metrics_global(y, y, y)
    assert metrics["mae"] == pytest.approx(0.0)
    assert metrics["rmse"] == pytest.approx(0.0)
    assert metrics["n_obs"] == 3


def test_metrics_constantes():
    y_true = np.array([1.0, 2.0, 3.0, 4.0])
    y_pred = np.array([2.0, 2.0, 2.0, 2.0])
    y_naive = y_pred  # no importa para este test

    metrics = compute_metrics_global(y_true, y_pred, y_naive)

    assert metrics["mae"] == pytest.approx(1.0)
    # RMSE = sqrt((1 + 0 + 1 + 4) / 4) = sqrt(1.5)
    assert metrics["rmse"] == pytest.approx(math.sqrt(1.5))


def _make_mock_dfs():
    """DataFrames mínimos con dos categorías."""
    predictions_df = pd.DataFrame(
        {
            "item_id": [1, 1, 2, 2, 3, 3, 3],
            "y_true": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0],
            "y_pred": [1.5, 1.5, 3.5, 3.5, 5.5, 5.5, 5.5],
            "y_naive": [1.0, 1.0, 3.0, 3.0, 5.0, 5.0, 5.0],
        }
    )
    items_df = pd.DataFrame(
        {
            "item_id": [1, 2, 3],
            "item_category_id": [10, 10, 20],
        }
    )
    categories_df = pd.DataFrame(
        {
            "item_category_id": [10, 20],
            "item_category_name": ["Cat A", "Cat B"],
        }
    )
    return predictions_df, items_df, categories_df


def test_compute_by_category_estructura():
    predictions_df, items_df, categories_df = _make_mock_dfs()
    result = compute_metrics_by_category(predictions_df, items_df, categories_df)

    columnas_esperadas = {"category_name", "n_obs", "mae", "rmse", "mae_naive", "rmse_naive"}
    assert columnas_esperadas == set(result.columns) - {"computed_at"}
    # Una fila por categoría
    assert len(result) == 2
    assert set(result["category_name"]) == {"Cat A", "Cat B"}


def test_compute_by_category_orden():
    predictions_df, items_df, categories_df = _make_mock_dfs()
    result = compute_metrics_by_category(predictions_df, items_df, categories_df)

    # Cat B tiene 3 obs, Cat A tiene 4 obs → Cat A primero
    assert result.iloc[0]["category_name"] == "Cat A"
    assert result.iloc[1]["category_name"] == "Cat B"
    # Verificar que n_obs está en orden descendente
    assert list(result["n_obs"]) == sorted(result["n_obs"], reverse=True)
