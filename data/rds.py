"""Capa de conexión y acceso a datos en RDS PostgreSQL."""

import logging
import os
from functools import lru_cache
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

logger = logging.getLogger("data.rds")


@lru_cache(maxsize=1)
def _get_engine() -> Engine:
    """Crea y cachea el engine con connection pooling.

    Returns:
        Engine de SQLAlchemy.

    Raises:
        ValueError: Si RDS_PASSWORD no está definida.
    """
    password = os.environ.get("RDS_PASSWORD")
    if not password:
        raise ValueError("RDS_PASSWORD no está definida.")
    host = os.getenv("RDS_HOST", "localhost")
    port = os.getenv("RDS_PORT", "5432")
    dbname = os.getenv("RDS_DBNAME", "forecasting")
    user = os.getenv("RDS_USER", "postgres")
    url = f"postgresql+psycopg://{user}:{password}@{host}:{port}/{dbname}"
    engine = create_engine(url, pool_pre_ping=True)
    logger.info("Engine SQLAlchemy creado — host=%s", host)
    return engine


def fetch_query(
    query: str, params: dict[str, Any] | None = None
) -> list[dict[str, Any]]:
    """Ejecuta un SELECT y retorna resultados como lista de diccionarios.

    Args:
        query: SQL SELECT con parámetros ``:nombre``.
        params: Diccionario de parámetros.

    Returns:
        Lista de filas como diccionarios.
    """
    with _get_engine().connect() as conn:
        rows = conn.execute(text(query), params or {}).mappings().all()
        logger.info("SELECT ejecutado — %d filas", len(rows))
        return [dict(r) for r in rows]


def execute_query(query: str, params: dict[str, Any] | None = None) -> None:
    """Ejecuta INSERT/UPDATE/DELETE con commit automático.

    Args:
        query: SQL con parámetros ``:nombre``.
        params: Diccionario de parámetros.
    """
    with _get_engine().begin() as conn:
        conn.execute(text(query), params or {})
        logger.info("Escritura ejecutada y confirmada")
