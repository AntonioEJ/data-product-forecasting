"""Punto de entrada para ejecutar el training como módulo.

Uso:
    uv run python -m training
"""

from config import ModelConfig, PathsConfig, find_repo_root
from pathlib import Path
from utils.logging import get_logger, setup_logging

from training.train import train_pipeline

setup_logging()
logger = get_logger(__name__)


def main() -> None:
    repo_root = find_repo_root(Path(__file__))
    paths = PathsConfig.from_repo_root(repo_root)
    cfg = ModelConfig()

    input_parquet = paths.data_prep / cfg.dataset_filename
    output_model = paths.models_dir / "model.pkl"

    logger.info("Iniciando entrenamiento | input=%s", input_parquet)

    metrics = train_pipeline(input_parquet, output_model, cfg)

    logger.info(
        "Entrenamiento finalizado | "
        "MAE=%.4f | RMSE=%.4f | MAE_naive=%.4f | RMSE_naive=%.4f | "
        "n_train=%d | n_val=%d | model=%s",
        metrics["mae"],
        metrics["rmse"],
        metrics["mae_naive"],
        metrics["rmse_naive"],
        metrics["n_train"],
        metrics["n_val"],
        metrics["model_path"],
    )


if __name__ == "__main__":
    main()
