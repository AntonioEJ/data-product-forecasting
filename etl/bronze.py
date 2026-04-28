#!/usr/bin/env python3
"""Script ETL de la capa Bronze — Arquitectura Medallion.

Automatiza la carga de todos los archivos CSV de ``data/raw/`` a S3 en formato
Parquet y registra cada archivo como tabla independiente en AWS Glue Data Catalog.

Características:
- Whitelist explícita de archivos a cargar (``BRONZE_FILES``).
- Subida en chunks de 500K filas para mantener bajo consumo de RAM.
- Registro de cada tabla en Glue bajo ``forecasting_bronze``.
- Idempotente: primer chunk usa ``overwrite``, los siguientes ``append``.
- Cifras de control al final: tablas procesadas, filas totales, tiempo.
- Logs a consola y a ``artifacts/logs/bronze_etl.log``.

Uso::

    python etl/bronze.py --bucket <nombre-bucket-s3> [--data-dir <ruta>]

Requisitos:
    awswrangler, boto3, pandas — con permisos de escritura en S3 y Glue.

Autores:
    José Antonio Esparza, Gustavo Pardo — 2026-04
"""

import argparse
import gc
import logging
import os
import sys
import time

import awswrangler as wr
import pandas as pd

GLUE_DATABASE: str = "forecasting_bronze"
S3_PREFIX_TEMPLATE: str = "s3://{bucket}/forecasting/bronze/{table}/"
CHUNK_SIZE: int = 500_000

# Archivos a cargar en la capa Bronze (whitelist explícita)
BRONZE_FILES: list[str] = [
    "item_categories.csv",
    "item_categories_en.csv",
    "items.csv",
    "items_en.csv",
    "sales_train.csv",
    "sample_submission.csv",
    "shops.csv",
    "shops_en.csv",
    "test.csv",
]


def setup_logging(log_dir: str) -> logging.Logger:
    """Configura logger con salida a consola y archivo.

    Args:
        log_dir: Ruta al directorio donde se escribirá el log.

    Returns:
        Instancia de logger configurada.
    """
    os.makedirs(log_dir, exist_ok=True)
    _logger = logging.getLogger("bronze_etl")
    _logger.setLevel(logging.INFO)
    if not _logger.handlers:
        fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
        console = logging.StreamHandler()
        console.setFormatter(fmt)
        _logger.addHandler(console)
        fh = logging.FileHandler(os.path.join(log_dir, "bronze_etl.log"))
        fh.setFormatter(fmt)
        _logger.addHandler(fh)
    return _logger


logger = logging.getLogger("bronze_etl")


def validate_file(file_path: str) -> None:
    """Valida que el archivo exista en el sistema de archivos.

    Args:
        file_path: Ruta absoluta o relativa al archivo a validar.

    Raises:
        FileNotFoundError: Si el archivo no existe.
    """
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"Archivo no encontrado: {file_path}")


def validate_first_chunk(chunk: pd.DataFrame, table_name: str) -> None:
    """Valida que el primer chunk no esté vacío.

    Args:
        chunk: Primer chunk del CSV leído.
        table_name: Nombre lógico de la tabla (para logs).

    Raises:
        AssertionError: Si el chunk está vacío.
    """
    assert not chunk.empty, f"DataFrame para '{table_name}' está vacío"
    logger.info(
        "✓ %s — validación básica OK (%d filas en primer chunk)",
        table_name,
        len(chunk),
    )


def upload_table(path: str, table: str, bucket: str) -> int:
    """Lee un CSV en chunks y lo sube a S3 registrando en Glue.

    Args:
        path: Ruta local al archivo CSV.
        table: Nombre de la tabla destino en S3/Glue.
        bucket: Nombre del bucket S3.

    Returns:
        Total de filas procesadas.
    """
    s3_path = S3_PREFIX_TEMPLATE.format(bucket=bucket, table=table)
    row_count = 0
    for chunk_idx, chunk in enumerate(pd.read_csv(path, chunksize=CHUNK_SIZE)):
        chunk.columns = chunk.columns.str.lower()
        if chunk_idx == 0:
            validate_first_chunk(chunk, table)
        mode = "overwrite" if chunk_idx == 0 else "append"
        wr.s3.to_parquet(
            chunk,
            path=s3_path,
            dataset=True,
            mode=mode,
            database=GLUE_DATABASE,
            table=table,
        )
        row_count += len(chunk)
        del chunk
        gc.collect()
    return row_count


def main() -> None:
    """Descubre CSVs, valida, sube a S3 en chunks y registra en Glue.

    Imprime cifras de control al finalizar: tablas procesadas, filas totales y
    tiempo de ejecución. Termina con código 1 ante cualquier error no manejado.
    """
    parser = argparse.ArgumentParser(
        description="ETL capa Bronze — CSV → S3 Parquet + Glue"
    )
    parser.add_argument("--bucket", required=True, help="Nombre del bucket S3 destino")
    parser.add_argument(
        "--data-dir", default=None, help="Ruta a data/raw/ (default: auto)"
    )
    args = parser.parse_args()

    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir = args.data_dir or os.path.join(repo_root, "data", "raw")
    log_dir = os.path.join(repo_root, "artifacts", "logs")

    setup_logging(log_dir)

    try:
        if not os.path.isdir(data_dir):
            raise RuntimeError(f"Directorio no encontrado: {data_dir}")

        archivos_csv = sorted(
            f for f in BRONZE_FILES if os.path.isfile(os.path.join(data_dir, f))
        )
        missing = [
            f for f in BRONZE_FILES if not os.path.isfile(os.path.join(data_dir, f))
        ]
        if missing:
            logger.warning(
                "Archivos no encontrados en %s: %s", data_dir, ", ".join(missing)
            )
        if not archivos_csv:
            raise RuntimeError(
                f"Ningún archivo de la whitelist encontrado en {data_dir}"
            )

        logger.info("=== Bronze ETL — inicio ===")
        logger.info(
            "Bucket: %s | Data dir: %s | Archivos: %d",
            args.bucket,
            data_dir,
            len(archivos_csv),
        )

        t_start = time.time()
        tablas_ok: list[str] = []
        total_filas = 0

        for filename in archivos_csv:
            table = os.path.splitext(filename)[0].lower()
            path = os.path.join(data_dir, filename)
            t0 = time.time()
            validate_file(path)
            rows = upload_table(path, table, args.bucket)
            elapsed = time.time() - t0
            logger.info("✓ %s — %d filas subidas en %.1fs", table, rows, elapsed)
            tablas_ok.append(table)
            total_filas += rows

        # Cifras de control finales
        elapsed_total = time.time() - t_start
        logger.info("=== Bronze ETL — cifras de control ===")
        logger.info("  Tablas procesadas : %d / %d", len(tablas_ok), len(archivos_csv))
        logger.info("  Filas totales     : %d", total_filas)
        logger.info("  Tiempo total      : %.1fs", elapsed_total)
        logger.info("  Tablas            : %s", ", ".join(tablas_ok))
        logger.info("=== Bronze ETL — fin OK ===")

    except Exception:
        logger.exception("Error fatal en Bronze ETL")
        sys.exit(1)


if __name__ == "__main__":
    main()
