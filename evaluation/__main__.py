"""Punto de entrada para ejecutar la evaluación como módulo.

Uso:
    uv run python -m evaluation
"""

from pathlib import Path

from config import ModelConfig, PathsConfig, find_repo_root

from evaluation.evaluate import run_evaluation


def main() -> None:
    repo_root = find_repo_root(Path(__file__))
    paths = PathsConfig.from_repo_root(repo_root)
    cfg = ModelConfig()

    result = run_evaluation(
        model_path=paths.models_dir / "model.pkl",
        data_path=paths.data_prep / "monthly_with_lags.parquet",
        items_path=paths.data_raw / "items.csv",
        categories_path=paths.data_raw / "item_categories_en.csv",
        output_path=paths.predictions_dir / "metrics_by_category.parquet",
        cfg=cfg,
    )

    print(
        f"Categorías procesadas: {result['n_categories']} | "
        f"Observaciones: {result['n_obs']} | "
        f"Output: {result['output_path']}"
    )


if __name__ == "__main__":
    main()
