"""Punto de entrada para ejecutar inference como módulo.

Uso:
    uv run python -m inference
"""

from pathlib import Path

from config import ModelConfig, PathsConfig, find_repo_root
from utils.logging import get_logger, setup_logging

from inference.predict import generate_backtest, generate_forecasts

setup_logging()
logger = get_logger(__name__)


def main() -> None:
    repo_root = find_repo_root(Path(__file__))
    paths = PathsConfig.from_repo_root(repo_root)
    cfg = ModelConfig()

    model_path = paths.models_dir / "model.pkl"
    data_path = paths.data_prep / "monthly_with_lags.parquet"
    backtest_output = paths.predictions_dir / "backtest.parquet"
    forecasts_output = paths.predictions_dir / "forecasts.parquet"

    logger.info("Iniciando backtest...")
    bt = generate_backtest(model_path, data_path, backtest_output, cfg)
    logger.info(
        "Backtest completado | n_rows=%d | date_min=%s | date_max=%s | output=%s",
        bt["n_rows"],
        bt["date_min"],
        bt["date_max"],
        bt["output_path"],
    )

    logger.info("Iniciando forecasts...")
    fc = generate_forecasts(model_path, data_path, forecasts_output, cfg)
    logger.info(
        "Forecasts completados | n_rows=%d | forecast_date=%s | output=%s",
        fc["n_rows"],
        fc["forecast_date"],
        fc["output_path"],
    )


if __name__ == "__main__":
    main()
