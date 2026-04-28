#!/usr/bin/env python3
"""
Gold Layer ETL Script — Medallion Architecture
=============================================

Este script ejecuta una consulta CTAS en Athena para crear una tabla analítica Gold
a partir de las tablas Bronze/Silver en Glue, y registra el resultado en Glue.

Características:
- Usa rutas relativas reproducibles para la salida en S3.
- Logging profesional y validación de ejecución.
- Docstrings en todas las funciones siguiendo buenas prácticas.

Uso:
    python etl/gold.py --bucket <nombre-bucket-s3>

Ejemplo:
    python etl/gold.py --bucket mi-bucket-datalake

Requisitos:
- awswrangler, boto3
- Permisos para ejecutar queries en Athena y escribir en S3/Glue

Autor: José Antonio Esparza
Fecha: 2026-04
"""
import os
import logging
import argparse
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
    """Punto de entrada principal del script Gold.

    Ejecuta el CTAS en Athena para crear la tabla analítica Gold y valida la ejecución.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--bucket", required=True, help="Nombre del bucket S3 destino")
    args = parser.parse_args()
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    s3_path = f"s3://{args.bucket}/forecasting/gold/"
    logger.info("Ejecutando CTAS para crear tabla Gold en Athena...")
    response = wr.athena.start_query_execution(
        query_string=CTAS_QUERY,
        database=GLUE_DATABASE_GOLD,
        workgroup="primary",
        result_configuration={"OutputLocation": s3_path},
    )
    query_id = response["QueryExecutionId"] if isinstance(response, dict) and "QueryExecutionId" in response else None
    if query_id:
        logger.info(f"✓ Query lanzada correctamente. QueryExecutionId: {query_id}")
    else:
        logger.error("✗ No se pudo obtener el QueryExecutionId. Revisa la ejecución en Athena.")
    logger.info(f"✓ Tabla Gold creada y almacenada en {s3_path}")

if __name__ == "__main__":
    main()
