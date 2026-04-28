#!/usr/bin/env python3
"""Script ETL de la capa Gold — Arquitectura Medallion.

Ejecuta una consulta CTAS en Athena para crear una tabla analítica Gold a partir
de las fuentes Silver registradas en Glue.

Características:
- Idempotente: elimina tabla y datos S3 existentes antes de recrear.
- Memory-safe: Athena ejecuta el CTAS completamente en la nube (0 bytes en RAM).
- Bloqueante: espera a que la consulta en Athena termine (``wait=True``).
- Cifras de control al final: tabla creada, ruta S3, tiempo.
- Logs a consola y a ``artifacts/logs/gold_etl.log``.

Uso::

    python etl/gold.py --bucket <nombre-bucket-s3>

Requisitos:
    awswrangler, boto3 — con permisos de escritura en Athena, S3 y Glue.

Autores:
    José Antonio Esparza, Gustavo Pardo — 2026-04
"""

import argparse
import logging
import os
import sys
import time

import awswrangler as wr

GLUE_DATABASE_GOLD: str = "forecasting_gold"
GOLD_TABLE: str = "ventas_analitica"

CTAS_QUERY: str = """
SELECT * FROM forecasting_silver.ventas_prep
-- Personaliza aquí el SELECT para tu modelo analítico
"""


def setup_logging(log_dir: str) -> logging.Logger:
    """Configura logger con salida a consola y archivo.

    Args:
        log_dir: Ruta al directorio donde se escribirá el log.

    Returns:
        Instancia de logger configurada.
    """
    os.makedirs(log_dir, exist_ok=True)
    _logger = logging.getLogger("gold_etl")
    _logger.setLevel(logging.INFO)
    if not _logger.handlers:
        fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
        console = logging.StreamHandler()
        console.setFormatter(fmt)
        _logger.addHandler(console)
        fh = logging.FileHandler(os.path.join(log_dir, "gold_etl.log"))
        fh.setFormatter(fmt)
        _logger.addHandler(fh)
    return _logger


logger = logging.getLogger("gold_etl")


def drop_table_if_exists(database: str, table: str, s3_path: str) -> None:
    """Elimina la tabla Glue y los datos S3 si existen (idempotencia).

    Args:
        database: Base de datos Glue.
        table: Nombre de la tabla a eliminar.
        s3_path: Prefijo S3 donde se almacenan los datos de la tabla.
    """
    if wr.catalog.does_table_exist(database=database, table=table):
        logger.info(
            "Tabla '%s.%s' existe — eliminando para recrear...", database, table
        )
        wr.catalog.delete_table_if_exists(database=database, table=table)
        wr.s3.delete_objects(s3_path)
        logger.info("Tabla y datos anteriores eliminados.")


def main() -> None:
    """Elimina tabla Gold existente, ejecuta CTAS en Athena e imprime cifras de control.

    El CTAS se ejecuta completamente en Athena (memory-safe). Bloquea hasta que
    la consulta termine. Termina con código 1 ante cualquier error no manejado.
    """
    parser = argparse.ArgumentParser(
        description="ETL capa Gold — CTAS en Athena → forecasting_gold"
    )
    parser.add_argument("--bucket", required=True, help="Nombre del bucket S3 destino")
    args = parser.parse_args()

    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    log_dir = os.path.join(repo_root, "artifacts", "logs")
    setup_logging(log_dir)

    try:
        s3_path = f"s3://{args.bucket}/forecasting/gold/{GOLD_TABLE}/"

        logger.info("=== Gold ETL — inicio ===")
        logger.info(
            "Bucket: %s | Tabla destino: %s.%s",
            args.bucket,
            GLUE_DATABASE_GOLD,
            GOLD_TABLE,
        )

        wr.catalog.create_database(name=GLUE_DATABASE_GOLD, exist_ok=True)
        logger.info("Base de datos Glue '%s' lista.", GLUE_DATABASE_GOLD)

        # Idempotencia
        drop_table_if_exists(GLUE_DATABASE_GOLD, GOLD_TABLE, s3_path)

        logger.info("Ejecutando CTAS en Athena (wait=True)...")
        t0 = time.time()
        wr.athena.create_ctas_table(
            sql=CTAS_QUERY,
            database=GLUE_DATABASE_GOLD,
            ctas_table=GOLD_TABLE,
            ctas_database=GLUE_DATABASE_GOLD,
            s3_output=s3_path,
            storage_format="PARQUET",
            write_compression="SNAPPY",
            workgroup="primary",
            wait=True,
        )
        elapsed = time.time() - t0

        # Cifras de control finales
        logger.info("=== Gold ETL — cifras de control ===")
        logger.info("  Tabla creada  : %s.%s", GLUE_DATABASE_GOLD, GOLD_TABLE)
        logger.info("  S3 path       : %s", s3_path)
        logger.info("  Tiempo CTAS   : %.1fs", elapsed)
        logger.info("=== Gold ETL — fin OK ===")

    except Exception:
        logger.exception("Error fatal en Gold ETL")
        sys.exit(1)


if __name__ == "__main__":
    main()
