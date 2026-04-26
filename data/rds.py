"""
RDS PostgreSQL connection and data access layer.
"""
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from typing import Any, Dict, List, Optional
import logging

logger = logging.getLogger("data.rds")
logger.setLevel(logging.INFO)

DB_CONFIG = {
    "host": os.getenv("RDS_HOST", "localhost"),
    "port": int(os.getenv("RDS_PORT", 5432)),
    "dbname": os.getenv("RDS_DBNAME", "forecasting"),
    "user": os.getenv("RDS_USER", "postgres"),
    "password": os.getenv("RDS_PASSWORD", "password"),
}

def get_connection():
    """
    Create a new database connection using environment variables or AWS Secrets Manager.
    Returns:
        psycopg2 connection object
    Raises:
        psycopg2.Error: If connection fails
    """
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        logger.info("Connected to RDS PostgreSQL.")
        return conn
    except Exception as e:
        logger.error(f"Failed to connect to RDS: {e}")
        raise

def fetch_query(query: str, params: Optional[tuple] = None) -> List[Dict[str, Any]]:
    """
    Execute a SELECT query and return results as a list of dicts.
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
            logger.info(f"Query executed: {query}")
            return results

def execute_query(query: str, params: Optional[tuple] = None) -> None:
    """
    Execute an INSERT/UPDATE/DELETE query.
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
            logger.info(f"Query executed and committed: {query}")
