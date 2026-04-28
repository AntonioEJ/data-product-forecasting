#!/usr/bin/env python3
"""
Silver Layer ETL Script — Medallion Architecture
==============================================

Este script automatiza la carga de todos los archivos Parquet ubicados en la carpeta
`data/prep/` del repositorio, subiéndolos a S3 y registrando cada archivo como una tabla
independiente en AWS Glue Data Catalog (capa Silver).

Características:
- Descubre y procesa automáticamente todos los archivos `.parquet` en `data/prep/`.
- Sube cada archivo como un dataset Parquet a S3 bajo la ruta:
  `s3://<bucket>/forecasting/silver/<nombre_archivo>/`
- Registra cada tabla en Glue con el nombre del archivo (sin extensión).
- Validación básica: cada archivo debe tener al menos una fila.
- Reproducible: usa rutas relativas desde la raíz del repositorio, funciona igual en cualquier entorno clonado.
- Al final, valida que todos los archivos hayan sido subidos correctamente a S3.

Uso:
    python etl/silver.py --bucket <nombre-bucket-s3>

Ejemplo:
    python etl/silver.py --bucket mi-bucket-datalake

Requisitos:
- awswrangler, boto3, pandas
- Permisos para escribir en el bucket S3 y Glue

Autor: José Antonio Esparza
Fecha: 2026-04
"""
import sys
import os
import logging
import argparse
import pandas as pd
import awswrangler as wr

def setup_logging():
    """Configura y retorna un logger con salida a consola.

    Returns:
        logging.Logger: Instancia de logger configurada.
    """
    logger = logging.getLogger("silver_etl")
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

    Descubre todos los archivos Parquet en data/prep/, los valida, sube a S3 y registra en Glue.
    Al final, valida que todos los archivos hayan sido subidos correctamente.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--bucket", required=True, help="Nombre del bucket S3 destino")
    args = parser.parse_args()
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir = os.path.join(repo_root, "data", "prep")
    s3_prefix_template = "s3://{bucket}/forecasting/silver/{table}/"
    glue_database = "forecasting_silver"
    if not os.path.isdir(data_dir):
        raise RuntimeError(f"No se encontró el directorio de datos esperado: {data_dir}")
    for filename in os.listdir(data_dir):
        if filename.endswith(".parquet"):
            table = os.path.splitext(filename)[0].lower()
            path = os.path.join(data_dir, filename)
            validate_file(path)
            df = pd.read_parquet(path)
            df.columns = df.columns.str.lower()
            validate_dataframe(df, table)
            logger.info(f"✓ {table} ({filename}) leído: {df.shape[0]} filas")
            s3_path = s3_prefix_template.format(bucket=args.bucket, table=table)
            wr.s3.to_parquet(df, path=s3_path, dataset=True, mode="overwrite")
            wr.catalog.create_table(
                database=glue_database,
                table=table,
                path=s3_path,
                columns_types={col: "string" for col in df.columns},
                exist_ok=True,
            )
            logger.info(f"✓ {table} cargado a S3 y registrado en Glue")
    # Validación: verifica que todos los archivos Parquet fueron subidos
    archivos_parquet = [f for f in os.listdir(data_dir) if f.endswith('.parquet')]
    tablas_subidas = []
    for filename in archivos_parquet:
        table = os.path.splitext(filename)[0].lower()
        s3_path = s3_prefix_template.format(bucket=args.bucket, table=table)
        try:
            files = wr.s3.list_objects(s3_path)
            if files:
                logger.info(f"✓ Validación: {table} existe en S3 ({len(files)} archivos)")
                tablas_subidas.append(table)
            else:
                logger.error(f"✗ Validación: {table} NO tiene archivos en S3")
        except Exception as e:
            logger.error(f"✗ Validación: error al listar {s3_path}: {e}")
    if len(tablas_subidas) == len(archivos_parquet):
        logger.info(f"✓ Todos los archivos Parquet de data/prep fueron subidos correctamente a S3.")
    else:
        logger.error(f"✗ Algunos archivos Parquet no fueron subidos a S3. Revisa los logs.")

if __name__ == "__main__":
    main()
