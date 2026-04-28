"""Tests que validan la existencia de archivos de salida del ETL en data/prep/.

Este módulo contiene smoke tests que verifican que el pipeline ETL produjo todos
los archivos esperados bajo ``data/prep/``. Son rápidos (solo un stat al
sistema de archivos) y están diseñados para correr en CI después del paso ETL.

Notas:
    - Las rutas se resuelven relativas a la raíz del repositorio usando
      ``__file__``, por lo que funcionan sin importar el directorio de trabajo
      (local, Docker, SageMaker Processing Job).
    - Para agregar nuevos archivos esperados, extender ``_EXPECTED_FILES``.
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_REPO_ROOT: Path = Path(__file__).resolve().parents[2]
_DATA_PREP: Path = _REPO_ROOT / "data" / "prep"

_EXPECTED_FILES: list[str] = [
    "df_base.csv",
    "df_base.parquet",
    "monthly_with_lags.csv",
    "monthly_with_lags.parquet",
]


def test_prep_files_exist() -> None:
    """Verifica que los archivos de salida del ETL existan en data/prep/.

    Itera sobre ``_EXPECTED_FILES`` y verifica que cada uno exista en disco.
    Registra un resumen de archivos presentes y faltantes para facilitar
    la depuración en logs de CI.

    Raises:
        AssertionError: Si uno o más archivos esperados faltan, con un
            mensaje descriptivo listando cada archivo faltante y el
            directorio verificado.
    """
    logger.info("Checking ETL output files in %s", _DATA_PREP)

    present = [f for f in _EXPECTED_FILES if (_DATA_PREP / f).exists()]
    missing = [f for f in _EXPECTED_FILES if f not in present]

    for filename in present:
        logger.info("  FOUND: %s", filename)

    for filename in missing:
        logger.warning("  MISSING: %s", filename)

    assert not missing, (
        f"Missing {len(missing)} file(s) in {_DATA_PREP}:\n"
        + "\n".join(f"  - {f}" for f in missing)
        + "\nRun the ETL pipeline first to generate them."
    )

    logger.info("All %d expected files found in %s", len(present), _DATA_PREP)
