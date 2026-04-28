#!/usr/bin/env python3
"""
Bronze Layer ETL Script — Medallion Architecture
===============================================

Este script automatiza la carga de todos los archivos CSV ubicados en la carpeta
`data/raw/` del repositorio, subiéndolos a S3 en formato Parquet y registrando
cada archivo como una tabla independiente en AWS Glue Data Catalog (capa Bronze).

Características:
- Descubre y procesa automáticamente todos los archivos `.csv` en `data/raw/`.
- Sube cada archivo como un dataset Parquet a S3 bajo la ruta:
  `s3://<bucket>/forecasting/bronze/<nombre_archivo>/`
- Registra cada tabla en Glue con el nombre del archivo (sin extensión).
- Validación básica: cada archivo debe tener al menos una fila.
- Reproducible: usa rutas relativas desde la raíz del repositorio, funciona igual en cualquier entorno clonado.
- Al final, valida que todos los archivos hayan sido subidos correctamente a S3.

Uso:
    python etl/bronze.py --bucket <nombre-bucket-s3>

Ejemplo:
    python etl/bronze.py --bucket mi-bucket-datalake

Requisitos:
- awswrangler, boto3, pandas
- Permisos para escribir en el bucket S3 y Glue

Autor: José Antonio Esparza, Gustavo Pardo
Fecha: 2026-04
"""
import sys
import os
import logging
import argparse
from typing import Dict, List

import pandas as pd
import boto3
from botocore.exceptions import ClientError
import awswrangler as wr



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
    """Punto de entrada principal del script.

    Descubre todos los archivos CSV en data/raw/, los valida, sube a S3 y registra en Glue.
    Al final, valida que todos los archivos hayan sido subidos correctamente.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--bucket", required=True, help="Nombre del bucket S3 destino")
    args = parser.parse_args()
    # Calcula la ruta absoluta a data/raw desde la raíz del repositorio
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir = os.path.join(repo_root, "data", "raw")
    if not os.path.isdir(data_dir):
        raise RuntimeError(f"No se encontró el directorio de datos esperado: {data_dir}")
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
                columns_types={col: "string" for col in df.columns},
                exist_ok=True,
            )
            logger.info(f"✓ {table} cargado a S3 y registrado en Glue")

    # Validación: verifica que todos los archivos CSV fueron subidos
    archivos_csv = [f for f in os.listdir(data_dir) if f.endswith('.csv')]
    tablas_subidas = []
    for filename in archivos_csv:
        table = os.path.splitext(filename)[0].lower()
        s3_path = S3_PREFIX_TEMPLATE.format(bucket=args.bucket, table=table)
        # Verifica que el path existe en S3
        try:
            files = wr.s3.list_objects(s3_path)
            if files:
                logger.info(f"✓ Validación: {table} existe en S3 ({len(files)} archivos)")
                tablas_subidas.append(table)
            else:
                logger.error(f"✗ Validación: {table} NO tiene archivos en S3")
        except Exception as e:
            logger.error(f"✗ Validación: error al listar {s3_path}: {e}")
    if len(tablas_subidas) == len(archivos_csv):
        logger.info(f"✓ Todos los archivos CSV de data/raw fueron subidos correctamente a S3.")
    else:
        logger.error(f"✗ Algunos archivos CSV no fueron subidos a S3. Revisa los logs.")

if __name__ == "__main__":
    main()
