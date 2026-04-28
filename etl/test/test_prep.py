"""Tests that validate ETL output files exist in data/prep/.

This module contains smoke tests that verify the ETL pipeline produced all
expected output files under ``data/prep/``. These tests are fast (no I/O
beyond a filesystem stat call) and are designed to run in CI after the ETL
step completes.

Notes:
    - Paths are resolved relative to the repository root using ``__file__``,
      so the tests work regardless of the working directory when pytest is
      invoked (local, Docker, SageMaker Processing Job).
    - To add new expected files, extend ``_EXPECTED_FILES``.
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
    """Verify that all expected ETL output files are present in data/prep/.

    Iterates over ``_EXPECTED_FILES`` and asserts each one exists on disk.
    Logs a summary of present and missing files to aid debugging in CI logs.

    Raises:
        AssertionError: If one or more expected files are missing, with a
            descriptive message listing each missing filename and the
            directory that was checked.
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
