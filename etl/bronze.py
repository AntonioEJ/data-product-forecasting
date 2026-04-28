#!/usr/bin/env python3
"""Bronze Layer ETL Script — Medallion Architecture.

Automates loading all CSV files from ``data/raw/`` to S3 in Parquet format
and registers each file as an independent table in AWS Glue Data Catalog.

Features:
- Auto-discovers all ``.csv`` files in ``data/raw/``.
- Uploads each file as a Parquet dataset to S3 under:
  ``s3://<bucket>/forecasting/bronze/<table_name>/``
- Registers each table in Glue with the filename (no extension) as table name.
- Basic validation: each file must have at least one row.
- Reproducible: uses repo-relative paths, works in any cloned environment.
- Final validation: confirms all CSV files were uploaded to S3.

Usage::

    python etl/bronze.py --bucket <s3-bucket-name>

Requirements:
    awswrangler, boto3, pandas — with S3 and Glue write permissions.

Authors:
    José Antonio Esparza, Gustavo Pardo — 2026-04
"""

import argparse
import logging
import os

import awswrangler as wr
import pandas as pd

GLUE_DATABASE: str = "forecasting_bronze"
S3_PREFIX_TEMPLATE: str = "s3://{bucket}/forecasting/bronze/{table}/"
CHUNK_SIZE: int = 500_000


def setup_logging():
    """Configura y retorna un logger con salida a consola.

    Returns:
        logging.Logger: Instancia de logger configurada.
    """
    logger = logging.getLogger("bronze_etl")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        console = logging.StreamHandler()
        logger.addHandler(console)
    return logger


logger = setup_logging()


def validate_file(file_path: str) -> None:
    """Valida que el archivo exista en el sistema de archivos.

    Args:
        file_path (str): Ruta absoluta o relativa al archivo a validar.

    Raises:
        FileNotFoundError: Si el archivo no existe.
    """
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")


def validate_dataframe(df: pd.DataFrame, table_name: str) -> None:
    """Valida que el DataFrame no esté vacío.

    Args:
        df (pd.DataFrame): DataFrame a validar.
        table_name (str): Nombre lógico de la tabla (para logs).

    Raises:
        AssertionError: Si el DataFrame está vacío.
    """
    assert not df.empty, f"DataFrame for '{table_name}' is empty"
    logger.info(f"✓ {table_name} passed validación básica ({df.shape[0]} rows)")


def main():
    """Discover CSV files in data/raw/, validate, upload to S3, and register in Glue.

    Validates all CSV files have been successfully uploaded at the end.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--bucket", required=True, help="S3 bucket name")
    args = parser.parse_args()
    # Calcula la ruta absoluta a data/raw desde la raíz del repositorio
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir = os.path.join(repo_root, "data", "raw")
    if not os.path.isdir(data_dir):
        raise RuntimeError(
            f"No se encontró el directorio de datos esperado: {data_dir}"
        )
    for filename in os.listdir(data_dir):
        if filename.endswith(".csv"):
            table = os.path.splitext(filename)[0].lower()
            path = os.path.join(data_dir, filename)
            validate_file(path)
            df = pd.read_csv(path)
            df.columns = df.columns.str.lower()
            validate_dataframe(df, table)
            logger.info(f"✓ {table} ({filename}) leído: {df.shape[0]} filas")
            s3_path = S3_PREFIX_TEMPLATE.format(bucket=args.bucket, table=table)
            wr.s3.to_parquet(df, path=s3_path, dataset=True, mode="overwrite")
            wr.catalog.create_table(
                database=GLUE_DATABASE,
                table=table,
                path=s3_path,
                columns_types=dict.fromkeys(df.columns, "string"),
                exist_ok=True,
            )
            logger.info(f"✓ {table} cargado a S3 y registrado en Glue")

    # Validación: verifica que todos los archivos CSV fueron subidos
    archivos_csv = [f for f in os.listdir(data_dir) if f.endswith(".csv")]
    tablas_subidas = []
    for filename in archivos_csv:
        table = os.path.splitext(filename)[0].lower()
        s3_path = S3_PREFIX_TEMPLATE.format(bucket=args.bucket, table=table)
        # Verifica que el path existe en S3
        try:
            files = wr.s3.list_objects(s3_path)
            if files:
                logger.info(
                    f"✓ Validación: {table} existe en S3 ({len(files)} archivos)"
                )
                tablas_subidas.append(table)
            else:
                logger.error(f"✗ Validación: {table} NO tiene archivos en S3")
        except Exception as e:
            logger.error(f"✗ Validación: error al listar {s3_path}: {e}")
    if len(tablas_subidas) == len(archivos_csv):
        logger.info(
            "✓ Todos los archivos CSV de data/raw fueron subidos correctamente a S3."
        )
    else:
        logger.error("✗ Algunos archivos CSV no fueron subidos a S3. Revisa los logs.")


if __name__ == "__main__":
    main()
