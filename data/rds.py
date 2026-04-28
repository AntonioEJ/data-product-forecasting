"""RDS PostgreSQL connection and data access layer."""

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
    """Create a new database connection from environment variables.

    Connection parameters are read from RDS_HOST, RDS_PORT, RDS_DBNAME,
    RDS_USER, and RDS_PASSWORD environment variables.

    Returns:
        psycopg2 connection object.

    Raises:
        ValueError: If RDS_PASSWORD environment variable is not set.
        psycopg2.OperationalError: If the connection cannot be established.
    """
    if not os.getenv("RDS_PASSWORD"):
        raise ValueError(
            "RDS_PASSWORD environment variable is not set. "
            "Configure it via environment variables or AWS Secrets Manager."
        )
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        logger.info("Connected to RDS PostgreSQL at host=%s", DB_CONFIG["host"])
        return conn
    except psycopg2.OperationalError:
        logger.exception("Failed to connect to RDS at host=%s", DB_CONFIG["host"])
        raise


def fetch_query(query: str, params: tuple | None = None) -> list[dict[str, Any]]:
    """Execute a SELECT query and return results as a list of dicts.

    Args:
        query: SQL SELECT statement
        params: Query parameters
    Returns:
        List of rows as dicts
    Raises:
        psycopg2.Error: If query fails
    """
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, params)
            results = cur.fetchall()
            logger.info("SELECT query executed successfully, rows=%d", len(results))
            return list(results)


def execute_query(query: str, params: tuple | None = None) -> None:
    """Execute an INSERT/UPDATE/DELETE query.

    Args:
        query: SQL statement
        params: Query parameters
    Raises:
        psycopg2.Error: If query fails
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            conn.commit()
            logger.info("Write query executed and committed successfully")
