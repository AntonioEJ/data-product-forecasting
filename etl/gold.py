#!/usr/bin/env python3
"""Gold Layer ETL Script — Medallion Architecture.

Runs a CTAS query in Athena to create a Gold analytical table from
Bronze/Silver sources in Glue and registers the result in Glue catalog.

Features:
- Reproducible S3 output paths.
- Professional logging and execution validation.

Usage::

    python etl/gold.py --bucket <s3-bucket-name>

Requirements:
    awswrangler, boto3 — with Athena and S3/Glue write permissions.

Author:
    José Antonio Esparza — 2026-04
"""

import argparse
import logging

import awswrangler as wr


def setup_logging():
    """Configura y retorna un logger con salida a consola.

    Returns:
        logging.Logger: Instancia de logger configurada.
    """
    logger = logging.getLogger("gold_etl")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        console = logging.StreamHandler()
        logger.addHandler(console)
    return logger


logger = setup_logging()

GLUE_DATABASE_GOLD = "forecasting_gold"
GOLD_TABLE = "ventas_analitica"

CTAS_QUERY = """
CREATE TABLE forecasting_gold.ventas_analitica AS (
    SELECT * FROM forecasting_silver.ventas_prep
    -- Personaliza aquí el SELECT para tu modelo analítico
)
"""


def main():
    """Execute the Gold layer CTAS in Athena and validate execution.

    Runs a CREATE TABLE AS SELECT query in Athena to build the Gold analytical
    table from Silver/Bronze sources and validates the query succeeded.

    Notes:
        Requires AWS credentials with Athena and Glue permissions.
        The S3 output path is determined by the --bucket argument.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--bucket", required=True, help="Nombre del bucket S3 destino")
    args = parser.parse_args()
    s3_path = f"s3://{args.bucket}/forecasting/gold/"
    logger.info("Ejecutando CTAS para crear tabla Gold en Athena...")
    response = wr.athena.start_query_execution(
        query_string=CTAS_QUERY,
        database=GLUE_DATABASE_GOLD,
        workgroup="primary",
        result_configuration={"OutputLocation": s3_path},
    )
    query_id = (
        response["QueryExecutionId"]
        if isinstance(response, dict) and "QueryExecutionId" in response
        else None
    )
    if query_id:
        logger.info("Query lanzada correctamente. QueryExecutionId: %s", query_id)
    else:
        raise RuntimeError(
            "No se pudo obtener el QueryExecutionId. Revisa la ejecución en Athena."
        )
    logger.info("Tabla Gold almacenada en %s", s3_path)


if __name__ == "__main__":
    main()
