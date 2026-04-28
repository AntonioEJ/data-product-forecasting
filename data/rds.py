"""Capa de conexión y acceso a datos en RDS PostgreSQL."""

import logging
import os
from typing import Any

import psycopg2
from psycopg2.extras import RealDictCursor

logger = logging.getLogger("data.rds")
logger.setLevel(logging.INFO)

DB_CONFIG = {
    "host": os.getenv("RDS_HOST", "localhost"),
    "port": int(os.getenv("RDS_PORT", "5432")),
    "dbname": os.getenv("RDS_DBNAME", "forecasting"),
    "user": os.getenv("RDS_USER", "postgres"),
    "password": os.getenv("RDS_PASSWORD", ""),
}


def get_connection() -> psycopg2.extensions.connection:
    """Crea una nueva conexión a la base de datos desde variables de entorno.

    Los parámetros de conexión se leen de las variables de entorno RDS_HOST,
    RDS_PORT, RDS_DBNAME, RDS_USER y RDS_PASSWORD.

    Returns:
        Objeto de conexión psycopg2.

    Raises:
        ValueError: Si la variable de entorno RDS_PASSWORD no está definida.
        psycopg2.OperationalError: Si no se puede establecer la conexión.
    """
    if not os.getenv("RDS_PASSWORD"):
        raise ValueError(
            "RDS_PASSWORD environment variable is not set. "
            "Configure it via environment variables or AWS Secrets Manager."
        )
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        logger.info("Conectado a RDS PostgreSQL en host=%s", DB_CONFIG["host"])
        return conn
    except psycopg2.OperationalError:
        logger.exception("Error al conectar a RDS en host=%s", DB_CONFIG["host"])
        raise


def fetch_query(query: str, params: tuple | None = None) -> list[dict[str, Any]]:
    """Ejecuta un SELECT y retorna los resultados como lista de diccionarios.

    Args:
        query: Sentencia SQL SELECT.
        params: Parámetros de la consulta.

    Returns:
        Lista de filas como diccionarios.

    Raises:
        psycopg2.Error: Si la consulta falla.
    """
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, params)
            results = cur.fetchall()
            logger.info("Consulta SELECT ejecutada, filas=%d", len(results))
            return list(results)


def execute_query(query: str, params: tuple | None = None) -> None:
    """Ejecuta una sentencia INSERT/UPDATE/DELETE.

    Args:
        query: Sentencia SQL.
        params: Parámetros de la consulta.

    Raises:
        psycopg2.Error: Si la consulta falla.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            conn.commit()
            logger.info("Consulta de escritura ejecutada y confirmada correctamente")
