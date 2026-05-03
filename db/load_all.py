"""Orchestrador de carga completa a RDS."""

from __future__ import annotations

import datetime
from pathlib import Path

import pandas as pd

from utils.logging import get_logger, setup_logging

logger = get_logger(__name__)

# Rutas por defecto relativas al directorio de trabajo
_ITEMS = Path("data/raw/items_en.csv")
_CATEGORIES = Path("data/raw/item_categories_en.csv")
_SHOPS = Path("data/raw/shops_en.csv")
_BACKTEST = Path("artifacts/predictions/backtest.parquet")
_FORECASTS = Path("artifacts/predictions/forecasts.parquet")
_METRICS = Path("artifacts/predictions/metrics_by_category.parquet")


def _check_csv(path: Path, required_cols: list[str]) -> list[str]:
    """Valida existencia y columnas mínimas de un CSV. Retorna lista de issues."""
    issues = []
    if not path.exists():
        return [f"{path} no existe"]
    try:
        df = pd.read_csv(path, nrows=3)
        missing = [c for c in required_cols if c not in df.columns]
        if missing:
            issues.append(f"{path}: columnas faltantes {missing}")
        else:
            logger.info("  OK  %s — %d cols, primeras filas OK", path, len(df.columns))
    except Exception as exc:
        issues.append(f"{path}: error al leer — {exc}")
    return issues


def _check_parquet(path: Path, required_cols: list[str]) -> list[str]:
    """Valida existencia y columnas mínimas de un parquet. Retorna lista de issues."""
    issues = []
    if not path.exists():
        return [f"{path} no existe"]
    try:
        df = pd.read_parquet(path)
        missing = [c for c in required_cols if c not in df.columns]
        if missing:
            issues.append(f"{path}: columnas faltantes {missing}")
        else:
            logger.info("  OK  %s — %d filas, %d cols", path, len(df), len(df.columns))
    except Exception as exc:
        issues.append(f"{path}: error al leer — {exc}")
    return issues


def _dry_run() -> dict:
    """Valida todos los artefactos sin conectar a RDS."""
    issues: list[str] = []

    issues += _check_csv(_ITEMS, ["item_id", "item_name", "item_category_id"])
    issues += _check_csv(_CATEGORIES, ["item_category_id", "item_category_name"])
    issues += _check_csv(_SHOPS, ["shop_id", "shop_name"])
    issues += _check_parquet(_BACKTEST, ["shop_id", "item_id", "forecast_date", "predicted_units", "actual_units", "created_at"])
    issues += _check_parquet(_FORECASTS, ["shop_id", "item_id", "forecast_date", "predicted_units", "actual_units", "created_at"])
    issues += _check_parquet(_METRICS, ["category_name", "mae", "rmse", "mae_naive", "rmse_naive", "computed_at"])

    status = "ok" if not issues else "failed"
    return {"validation": status, "issues": issues}


def main(dry_run: bool = False) -> dict:
    """Carga completa de parquets y CSVs a RDS.

    Args:
        dry_run: Si True, solo valida artefactos locales sin conectar a RDS.

    Returns:
        Dict con resultados de validación o conteos de carga.
    """
    setup_logging()

    if dry_run:
        logger.info("=== DRY-RUN: validando artefactos locales ===")
        result = _dry_run()
        if result["validation"] == "ok":
            logger.info("Validación completa: todos los artefactos OK")
        else:
            for issue in result["issues"]:
                logger.error("FALLA: %s", issue)
        return result

    # Carga real
    from data.rds import _get_engine
    from db.init_db import main as init_db
    from db.load_catalogs import load_products, load_shops
    from db.load_metrics import load_metrics
    from db.load_predictions import load_predictions

    engine = _get_engine()

    logger.info("Inicializando schema en RDS")
    init_db()

    # Borrar tablas hijas antes que las padres para no violar FK constraints
    from db.schema import feedback, predictions as pred_tbl

    with engine.begin() as conn:
        conn.execute(feedback.delete())
        conn.execute(pred_tbl.delete())

    logger.info("Cargando shops")
    n_shops = load_shops(_SHOPS, engine)

    logger.info("Cargando products")
    n_products = load_products(_ITEMS, _CATEGORIES, engine)

    logger.info("Cargando predictions")
    pred_counts = load_predictions(_BACKTEST, _FORECASTS, engine)

    logger.info("Cargando metrics")
    n_metrics = load_metrics(_METRICS, engine)

    result = {
        "shops": n_shops,
        "products": n_products,
        "predictions": pred_counts,
        "metrics": n_metrics,
        "loaded_at": datetime.datetime.utcnow().isoformat(),
    }
    logger.info("Carga completa: %s", result)
    return result
