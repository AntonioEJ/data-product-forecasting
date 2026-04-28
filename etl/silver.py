#!/usr/bin/env python3
"""Script ETL de la capa Silver — Arquitectura Medallion.

Automatiza la carga de todos los archivos Parquet de ``data/prep/`` a S3
y registra cada uno como tabla independiente en AWS Glue Data Catalog.

Características:
- Descubre automáticamente todos los ``.parquet`` en ``data/prep/``.
- Lectura archivo por archivo; libera memoria con ``del df`` + ``gc.collect()``.
- Subida a S3 bajo ``s3://<bucket>/forecasting/silver/<tabla>/``.
- Registro en Glue bajo ``forecasting_silver``.
- Idempotente: ``mode="overwrite"`` en cada ejecución.
- Cifras de control al final: tablas procesadas, filas totales, tiempo.
- Logs a consola y a ``artifacts/logs/silver_etl.log``.

Uso::

    python etl/silver.py --bucket <nombre-bucket-s3>

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

GLUE_DATABASE: str = "forecasting_silver"
S3_PREFIX_TEMPLATE: str = "s3://{bucket}/forecasting/silver/{table}/"

# Archivos a cargar en la capa Silver (whitelist explícita)
SILVER_FILES: list[str] = [
    "df_base.parquet",
    "monthly_with_lags.parquet",
]


def setup_logging(log_dir: str) -> logging.Logger:
    """Configura logger con salida a consola y archivo.

    Args:
        log_dir: Ruta al directorio donde se escribirá el log.

    Returns:
        Instancia de logger configurada.
    """
    os.makedirs(log_dir, exist_ok=True)
    _logger = logging.getLogger("silver_etl")
    _logger.setLevel(logging.INFO)
    if not _logger.handlers:
        fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
        console = logging.StreamHandler()
        console.setFormatter(fmt)
        _logger.addHandler(console)
        fh = logging.FileHandler(os.path.join(log_dir, "silver_etl.log"))
        fh.setFormatter(fmt)
        _logger.addHandler(fh)
    return _logger


logger = logging.getLogger("silver_etl")


def validate_file(file_path: str) -> None:
    """Valida que el archivo exista en el sistema de archivos.

    Args:
        file_path: Ruta absoluta o relativa al archivo a validar.

    Raises:
        FileNotFoundError: Si el archivo no existe.
    """
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"Archivo no encontrado: {file_path}")


def validate_dataframe(df: pd.DataFrame, table_name: str) -> None:
    """Valida que el DataFrame no esté vacío.

    Args:
        df: DataFrame a validar.
        table_name: Nombre lógico de la tabla (para logs).

    Raises:
        AssertionError: Si el DataFrame está vacío.
    """
    assert not df.empty, f"DataFrame para '{table_name}' está vacío"
    logger.info("✓ %s — validación básica OK (%d filas)", table_name, len(df))


def upload_table(path: str, table: str, bucket: str) -> int:
    """Lee un Parquet y lo sube a S3 registrando en Glue.

    Libera memoria con ``del df`` + ``gc.collect()`` al finalizar.

    Args:
        path: Ruta local al archivo Parquet.
        table: Nombre de la tabla destino en S3/Glue.
        bucket: Nombre del bucket S3.

    Returns:
        Total de filas procesadas.
    """
    df = pd.read_parquet(path)
    df.columns = df.columns.str.lower()
    validate_dataframe(df, table)
    row_count = len(df)
    s3_path = S3_PREFIX_TEMPLATE.format(bucket=bucket, table=table)
    wr.s3.to_parquet(
        df,
        path=s3_path,
        dataset=True,
        mode="overwrite",
        database=GLUE_DATABASE,
        table=table,
    )
    del df
    gc.collect()
    return row_count


def main() -> None:
    """Descubre Parquets, valida, sube a S3 y registra en Glue.

    Imprime cifras de control al finalizar: tablas procesadas, filas totales y
    tiempo de ejecución. Termina con código 1 ante cualquier error no manejado.
    """
    parser = argparse.ArgumentParser(
        description="ETL capa Silver — Parquet → S3 + Glue"
    )
    parser.add_argument("--bucket", required=True, help="Nombre del bucket S3 destino")
    args = parser.parse_args()

    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir = os.path.join(repo_root, "data", "prep")
    log_dir = os.path.join(repo_root, "artifacts", "logs")

    setup_logging(log_dir)

    try:
        if not os.path.isdir(data_dir):
            raise RuntimeError(f"Directorio no encontrado: {data_dir}")

        archivos = sorted(
            f for f in SILVER_FILES if os.path.isfile(os.path.join(data_dir, f))
        )
        missing = [
            f for f in SILVER_FILES if not os.path.isfile(os.path.join(data_dir, f))
        ]
        if missing:
            logger.warning(
                "Archivos no encontrados en %s: %s",
                data_dir,
                ", ".join(missing),
            )
        if not archivos:
            raise RuntimeError(
                f"Ningún archivo de la whitelist encontrado en {data_dir}"
            )

        logger.info("=== Silver ETL — inicio ===")
        logger.info(
            "Bucket: %s | Data dir: %s | Archivos: %d",
            args.bucket,
            data_dir,
            len(archivos),
        )

        wr.catalog.create_database(name=GLUE_DATABASE, exist_ok=True)
        logger.info("Base de datos Glue '%s' lista.", GLUE_DATABASE)

        t_start = time.time()
        tablas_ok: list[str] = []
        tablas_fail: list[str] = []
        total_filas = 0

        for filename in archivos:
            table = os.path.splitext(filename)[0].lower()
            path = os.path.join(data_dir, filename)
            t0 = time.time()
            try:
                validate_file(path)
                rows = upload_table(path, table, args.bucket)
                elapsed = time.time() - t0
                logger.info("✓ %s — %d filas subidas en %.1fs", table, rows, elapsed)
                tablas_ok.append(table)
                total_filas += rows
            except Exception:
                elapsed = time.time() - t0
                logger.exception("✗ %s — error al procesar en %.1fs", table, elapsed)
                tablas_fail.append(table)

        # Cifras de control finales
        elapsed_total = time.time() - t_start
        logger.info("=== Silver ETL — cifras de control ===")
        logger.info("  Tablas procesadas : %d / %d", len(tablas_ok), len(archivos))
        logger.info("  Tablas fallidas   : %d", len(tablas_fail))
        if tablas_fail:
            logger.info("  Detalle fallas    : %s", ", ".join(tablas_fail))
        logger.info("  Filas totales     : %d", total_filas)
        logger.info("  Tiempo total      : %.1fs", elapsed_total)
        logger.info("  Tablas OK         : %s", ", ".join(tablas_ok))
        logger.info("=== Silver ETL — fin ===")

        if tablas_fail:
            raise RuntimeError(
                f"Silver ETL terminó con errores en: {', '.join(tablas_fail)}"
            )

    except Exception:
        logger.exception("Error fatal en Silver ETL")
        sys.exit(1)


if __name__ == "__main__":
    main()
