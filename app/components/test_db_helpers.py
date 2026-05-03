"""Smoke tests para app/components/db_helpers.py."""

from __future__ import annotations

import os

import pytest


def _rds_disponible() -> bool:
    """Verifica si las env vars de RDS están configuradas."""
    return bool(os.environ.get("RDS_PASSWORD"))


def test_imports_no_fallan():
    """Todas las funciones del helper se pueden importar sin error."""
    from app.components.db_helpers import (  # noqa: F401
        get_categories_list,
        get_feedback_list,
        get_metrics_by_category,
        get_predictions_with_actuals,
        get_shops_list,
        submit_feedback,
    )


def test_categories_list_no_vacia():
    """get_categories_list retorna al menos una categoría desde RDS."""
    if not _rds_disponible():
        pytest.skip("RDS no configurado — define RDS_PASSWORD para ejecutar.")

    from app.components.db_helpers import get_categories_list

    categorias = get_categories_list()
    assert isinstance(categorias, list)
    assert len(categorias) > 0, "La lista de categorías no puede estar vacía."
