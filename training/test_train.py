"""Smoke tests del pipeline de training."""

import inspect
from pathlib import Path


def test_train_pipeline_importable():
    from training.train import train_pipeline  # noqa: F401


def test_train_pipeline_signature():
    from training.train import train_pipeline

    sig = inspect.signature(train_pipeline)
    params = list(sig.parameters.keys())
    assert params == ["input_parquet", "output_model", "cfg"]


def test_train_pipeline_cfg_default_is_none():
    from training.train import train_pipeline

    sig = inspect.signature(train_pipeline)
    assert sig.parameters["cfg"].default is None


def test_train_pipeline_returns_expected_keys(tmp_path):
    """Ejecuta el pipeline real contra el parquet de data/prep."""
    from training.train import train_pipeline
    from config import ModelConfig, PathsConfig, find_repo_root

    repo_root = find_repo_root(Path(__file__))
    paths = PathsConfig.from_repo_root(repo_root)
    cfg = ModelConfig()

    input_parquet = paths.data_prep / cfg.dataset_filename
    if not input_parquet.exists():
        import pytest
        pytest.skip(f"Dataset no disponible: {input_parquet}")

    output_model = tmp_path / "model.pkl"
    result = train_pipeline(input_parquet, output_model, cfg)

    expected_keys = {"mae", "rmse", "mae_naive", "rmse_naive", "model_path", "n_train", "n_val"}
    assert expected_keys == set(result.keys())
    assert output_model.exists()
    assert result["n_train"] > 0
    assert result["n_val"] > 0
    assert result["mae"] >= 0.0
    assert result["rmse"] >= 0.0
