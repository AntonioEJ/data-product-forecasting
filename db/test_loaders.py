"""Tests sintéticos de transformaciones de los loaders (sin RDS)."""

from __future__ import annotations

import datetime
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest


# ---------------------------------------------------------------------------
# test_load_products_columnas
# ---------------------------------------------------------------------------

def test_load_products_columnas(tmp_path):
    """load_products hace merge correcto y retorna las columnas esperadas."""
    items_csv = tmp_path / "items.csv"
    cats_csv = tmp_path / "cats.csv"

    items_csv.write_text("item_name,item_id,item_category_id\nFoo,1,10\nBar,2,20\n")
    cats_csv.write_text("item_category_name,item_category_id\nElectronics,10\nBooks,20\n")

    # Engine mock: captura los registros insertados
    inserted = []

    mock_conn = MagicMock()
    mock_conn.__enter__ = lambda s: mock_conn
    mock_conn.__exit__ = MagicMock(return_value=False)

    def fake_execute(stmt, params=None):
        if params:
            inserted.extend(params if isinstance(params, list) else [params])

    mock_conn.execute = fake_execute

    mock_engine = MagicMock()
    mock_engine.begin.return_value = mock_conn

    from db.load_catalogs import load_products

    n = load_products(items_csv, cats_csv, mock_engine)

    assert n == 2
    cols_insertadas = set(inserted[0].keys())
    assert cols_insertadas == {"item_id", "item_name", "category_name"}
    nombres = {r["category_name"] for r in inserted}
    assert nombres == {"Electronics", "Books"}


# ---------------------------------------------------------------------------
# test_load_predictions_concatena
# ---------------------------------------------------------------------------

def test_load_predictions_concatena(tmp_path):
    """load_predictions concatena backtest y forecasts correctamente."""
    now = pd.Timestamp("2026-05-01", tz="UTC")

    bt = pd.DataFrame({
        "shop_id": [1, 2],
        "item_id": [10, 20],
        "forecast_date": ["2015-10-31", "2015-10-31"],
        "predicted_units": [5.0, 3.0],
        "actual_units": [4.0, 2.0],
        "created_at": [now, now],
        "batch_job_id": pd.array([pd.NA, pd.NA], dtype="Int64"),
    })

    fc = pd.DataFrame({
        "shop_id": [3],
        "item_id": [30],
        "forecast_date": ["2015-11-30"],
        "predicted_units": [7.0],
        "actual_units": [None],
        "created_at": [now],
        "batch_job_id": pd.array([pd.NA], dtype="Int64"),
    })

    bt_path = tmp_path / "bt.parquet"
    fc_path = tmp_path / "fc.parquet"
    bt.to_parquet(bt_path)
    fc.to_parquet(fc_path)

    inserted = []

    mock_conn = MagicMock()
    mock_conn.__enter__ = lambda s: mock_conn
    mock_conn.__exit__ = MagicMock(return_value=False)

    def fake_execute(stmt, params=None):
        if params:
            inserted.extend(params if isinstance(params, list) else [params])

    mock_conn.execute = fake_execute
    mock_engine = MagicMock()
    mock_engine.begin.return_value = mock_conn

    from db.load_predictions import load_predictions

    result = load_predictions(bt_path, fc_path, mock_engine)

    assert result["n_backtest"] == 2
    assert result["n_forecasts"] == 1
    assert result["n_total"] == 3
    assert len(inserted) == 3


# ---------------------------------------------------------------------------
# test_forecast_date_es_date
# ---------------------------------------------------------------------------

def test_forecast_date_es_date(tmp_path):
    """Tras la conversión, forecast_date debe ser date, no str ni datetime."""
    now = pd.Timestamp("2026-05-01", tz="UTC")

    bt = pd.DataFrame({
        "shop_id": [1],
        "item_id": [10],
        "forecast_date": ["2015-10-31"],
        "predicted_units": [5.0],
        "actual_units": [4.0],
        "created_at": [now],
        "batch_job_id": pd.array([pd.NA], dtype="Int64"),
    })
    fc = bt.copy()

    bt_path = tmp_path / "bt.parquet"
    fc_path = tmp_path / "fc.parquet"
    bt.to_parquet(bt_path)
    fc.to_parquet(fc_path)

    date_values = []

    mock_conn = MagicMock()
    mock_conn.__enter__ = lambda s: mock_conn
    mock_conn.__exit__ = MagicMock(return_value=False)

    def fake_execute(stmt, params=None):
        if params:
            rows = params if isinstance(params, list) else [params]
            for r in rows:
                date_values.append(r.get("forecast_date"))

    mock_conn.execute = fake_execute
    mock_engine = MagicMock()
    mock_engine.begin.return_value = mock_conn

    from db.load_predictions import load_predictions

    load_predictions(bt_path, fc_path, mock_engine)

    for val in date_values:
        assert isinstance(val, datetime.date), f"Se esperaba date, se obtuvo {type(val)}"
        assert not isinstance(val, datetime.datetime), "date no debe ser datetime"


# ---------------------------------------------------------------------------
# test_dry_run_no_conecta
# ---------------------------------------------------------------------------

def test_dry_run_no_conecta():
    """Con dry_run=True, _get_engine no debe ser invocado."""
    # _get_engine se importa dentro del bloque `if not dry_run:` de load_all.main,
    # por lo que hay que parchearlo en su módulo de origen.
    with patch("data.rds._get_engine", autospec=True) as mock_engine:
        from db.load_all import main

        result = main(dry_run=True)

        mock_engine.assert_not_called()
        assert "validation" in result
        assert result["validation"] in ("ok", "failed")
