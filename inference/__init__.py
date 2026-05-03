"""Paquete de inferencia: backtest y forecast futuro."""

from inference.predict import generate_backtest, generate_forecasts, load_model

__all__ = ["load_model", "generate_backtest", "generate_forecasts"]
