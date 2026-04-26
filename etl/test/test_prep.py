"""Test helpers for ETL outputs."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from pandas.testing import assert_frame_equal


def _load(path: Path) -> pd.DataFrame:
    if path.suffix == ".parquet":
        return pd.read_parquet(path)
    if path.suffix == ".csv":
        return pd.read_csv(path)
    raise ValueError(f"Extensión no soportada: {path.suffix}")


def assert_outputs_equal(
    old_path: Path,
    new_path: Path,
    *,
    sort_keys: list[str] | None = None,
    check_dtypes: bool = False,
) -> None:
    """Asserts that two output files are equal.

    Optionally sorts and checks dtypes.
    """
    old = _load(old_path)
    new = _load(new_path)

    if sort_keys:
        old = old.sort_values(sort_keys).reset_index(drop=True)
        new = new.sort_values(sort_keys).reset_index(drop=True)

    old = old.reindex(sorted(old.columns), axis=1)
    new = new.reindex(sorted(new.columns), axis=1)

    assert_frame_equal(
        old,
        new,
        check_dtype=check_dtypes,
        check_like=False,
        atol=0.0,
        rtol=0.0,
    )


# ✅ ESTE ES EL TEST REAL QUE PYTEST VA A EJECUTAR
def test_monthly_outputs_equal():
    """Test that monthly_with_lags outputs are equal."""
    """Test that monthly_with_lags outputs are equal."""
    base = Path("data/prep")

    assert_outputs_equal(
        old_path=base / "monthly_with_lags_old.parquet",
        new_path=base / "monthly_with_lags_new.parquet",
        sort_keys=["date", "shop_id", "item_id"],
        check_dtypes=False,
    )


def test_df_base_outputs_equal():
    """Test that df_base outputs are equal."""
    """Test that df_base outputs are equal."""
    base = Path("data/prep")

    assert_outputs_equal(
        old_path=base / "df_base_old.parquet",
        new_path=base / "df_base_new.parquet",
        sort_keys=["date", "shop_id", "item_id"],
        check_dtypes=False,
    )
