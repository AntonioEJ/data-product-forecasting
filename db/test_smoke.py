"""Smoke tests del schema de RDS: verifica estructura sin necesitar conexión."""

from __future__ import annotations

from db.schema import batch_jobs, metadata, metrics, predictions, products, shops

EXPECTED_TABLES = {"products", "shops", "predictions", "metrics", "batch_jobs"}


def test_metadata_tiene_cinco_tablas():
    assert set(metadata.tables.keys()) == EXPECTED_TABLES


def test_pk_products():
    pk_cols = {c.name for c in products.primary_key}
    assert pk_cols == {"item_id"}


def test_pk_shops():
    pk_cols = {c.name for c in shops.primary_key}
    assert pk_cols == {"shop_id"}


def test_pk_predictions():
    pk_cols = {c.name for c in predictions.primary_key}
    assert pk_cols == {"id"}


def test_pk_metrics():
    pk_cols = {c.name for c in metrics.primary_key}
    assert pk_cols == {"id"}


def test_pk_batch_jobs():
    pk_cols = {c.name for c in batch_jobs.primary_key}
    assert pk_cols == {"id"}


def test_predictions_columnas_requeridas():
    cols = {c.name for c in predictions.columns}
    assert {
        "shop_id", "item_id", "forecast_date",
        "predicted_units", "actual_units",
        "created_at", "batch_job_id",
    } <= cols


def test_actual_units_nullable():
    col = predictions.c.actual_units
    assert col.nullable is True


def test_predictions_created_at_no_nullable():
    col = predictions.c.created_at
    assert col.nullable is False


def test_predictions_batch_job_id_nullable():
    col = predictions.c.batch_job_id
    assert col.nullable is True


def test_predictions_fk_a_shops():
    col = predictions.c.shop_id
    fks = list(col.foreign_keys)
    assert len(fks) == 1
    assert fks[0].column.table.name == "shops"


def test_predictions_fk_a_products():
    col = predictions.c.item_id
    fks = list(col.foreign_keys)
    assert len(fks) == 1
    assert fks[0].column.table.name == "products"


def test_predictions_fk_a_batch_jobs():
    col = predictions.c.batch_job_id
    fks = list(col.foreign_keys)
    assert len(fks) == 1
    assert fks[0].column.table.name == "batch_jobs"


def test_metrics_columnas_requeridas():
    cols = {c.name for c in metrics.columns}
    assert {
        "category_name", "mae", "rmse",
        "mae_naive", "rmse_naive", "computed_at",
    } <= cols