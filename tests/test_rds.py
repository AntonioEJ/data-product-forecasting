"""Unit tests para data/rds.py."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest


class TestGetEngine:
    """Tests para _get_engine()."""

    def test_raises_without_password(self):
        """Lanza ValueError si RDS_PASSWORD no está definida."""
        from data.rds import _get_engine

        _get_engine.cache_clear()
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("RDS_PASSWORD", None)
            with pytest.raises(ValueError, match="RDS_PASSWORD"):
                _get_engine()

    def test_creates_engine_with_env_vars(self):
        """Crea engine correctamente cuando las env vars están disponibles."""
        from data.rds import _get_engine

        _get_engine.cache_clear()
        env = {
            "RDS_PASSWORD": "testpass",
            "RDS_HOST": "localhost",
            "RDS_PORT": "5432",
            "RDS_DBNAME": "testdb",
            "RDS_USER": "testuser",
        }
        with patch.dict(os.environ, env, clear=False):
            with patch("data.rds.create_engine") as mock_engine:
                mock_engine.return_value = MagicMock()
                _get_engine()
                mock_engine.assert_called_once()
                call_url = mock_engine.call_args[0][0]
                assert "postgresql+psycopg://" in call_url
                assert "testuser" in call_url
                assert "testpass" in call_url
                assert "localhost" in call_url

    def teardown_method(self):
        """Limpia cache entre tests."""
        from data.rds import _get_engine

        _get_engine.cache_clear()


class TestFetchQuery:
    """Tests para fetch_query()."""

    def test_returns_list_of_dicts(self):
        """fetch_query retorna lista de diccionarios."""
        from data.rds import fetch_query

        mock_row = MagicMock()
        mock_row.__getitem__ = lambda self, key: "value"
        mock_mappings = MagicMock()
        mock_mappings.all.return_value = [{"id": 1, "name": "test"}]

        mock_result = MagicMock()
        mock_result.mappings.return_value = mock_mappings

        mock_conn = MagicMock()
        mock_conn.execute.return_value = mock_result
        mock_conn.__enter__ = lambda self: self
        mock_conn.__exit__ = MagicMock(return_value=False)

        with patch("data.rds._get_engine") as mock_engine:
            mock_engine.return_value.connect.return_value = mock_conn
            result = fetch_query("SELECT 1")
            assert result == [{"id": 1, "name": "test"}]

    def test_passes_params_to_execute(self):
        """Los params se pasan correctamente al execute."""
        from data.rds import fetch_query

        mock_mappings = MagicMock()
        mock_mappings.all.return_value = []

        mock_result = MagicMock()
        mock_result.mappings.return_value = mock_mappings

        mock_conn = MagicMock()
        mock_conn.execute.return_value = mock_result
        mock_conn.__enter__ = lambda self: self
        mock_conn.__exit__ = MagicMock(return_value=False)

        with patch("data.rds._get_engine") as mock_engine:
            mock_engine.return_value.connect.return_value = mock_conn
            fetch_query("SELECT :id", params={"id": 42})
            args = mock_conn.execute.call_args
            assert args[0][1] == {"id": 42}


class TestExecuteQuery:
    """Tests para execute_query()."""

    def test_uses_begin_context(self):
        """execute_query usa engine.begin() para auto-commit."""
        from data.rds import execute_query

        mock_conn = MagicMock()
        mock_conn.__enter__ = lambda self: self
        mock_conn.__exit__ = MagicMock(return_value=False)

        with patch("data.rds._get_engine") as mock_engine:
            mock_engine.return_value.begin.return_value = mock_conn
            execute_query("INSERT INTO t VALUES (:v)", params={"v": 1})
            mock_conn.execute.assert_called_once()
