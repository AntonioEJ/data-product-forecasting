"""Configuración central del proyecto.

Define rutas estándar, constantes y parámetros del pipeline para que:
- no haya strings "mágicos" regados,
- sea fácil mantener el repo a futuro,
- y el pipeline sea reproducible.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


def find_repo_root(start: Path) -> Path:
    """Encuentra el root del proyecto buscando pyproject.toml y data/.

    Args:
        start: Ruta base (típicamente __file__).

    Returns:
        Ruta al root del proyecto.

    Raises:
        RuntimeError: Si no se encuentra el root.
    """
    current = start.resolve()
    for _ in range(15):
        if (current / "pyproject.toml").exists() and (current / "data").exists():
            return current
        current = current.parent
    raise RuntimeError(
        "No se encontró el root del proyecto (pyproject.toml + data/). "
        "Ejecuta dentro de una carpeta de tarea (p.ej. tareas/tarea-03)."
    )


@dataclass(frozen=True)
class PathsConfig:
    """Rutas estándar del proyecto."""

    repo_root: Path
    data_raw: Path
    data_prep: Path
    artifacts_dir: Path
    logs_dir: Path
    models_dir: Path
    predictions_dir: Path
    reports_dir: Path

    @staticmethod
    def from_repo_root(repo_root: Path) -> PathsConfig:
        """Construye la configuración de rutas a partir del root."""
        artifacts_dir = repo_root / "artifacts"
        return PathsConfig(
            repo_root=repo_root,
            data_raw=repo_root / "data" / "raw",
            data_prep=repo_root / "data" / "prep",
            artifacts_dir=artifacts_dir,
            logs_dir=artifacts_dir / "logs",
            models_dir=artifacts_dir / "models",
            predictions_dir=artifacts_dir / "predictions",
            reports_dir=artifacts_dir / "reports",
        )


@dataclass(frozen=True)
class ModelConfig:
    """Configuración de features y modelado."""

    random_state: int = 42

    # Dataset que sale de ETL
    dataset_filename: str = "monthly_with_lags.parquet"

    # Llaves y tiempo
    key_cols: tuple[str, str] = ("shop_id", "item_id")
    time_col: str = "date"

    # Target
    target_col: str = "monthly_units"

    # Features base disponibles desde ETL
    base_features: tuple[str, ...] = (
        "shop_id",
        "item_id",
        "monthly_sales",
        "avg_price",
        "active_days",
        "num_transactions",
    )

    # En el notebook usaban lags 1,2,4,8 y rolling means
    lags: tuple[int, ...] = (1, 2, 4, 8)
    rolls: tuple[int, ...] = (4, 8)

    # Split temporal
    train_quantile_cutoff: float = 0.8

    # Predicciones no negativas
    clip_pred_min: float = 0.0
