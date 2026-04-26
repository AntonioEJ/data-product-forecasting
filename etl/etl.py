"""ETL 01 - Carga, limpieza y agregación mensual Tarea-05.

Lee archivos desde:
    data/raw/

Escribe datasets preparados en:
    data/prep/

Escribe outputs de control (opcionales) en:
    artifacts/

Uso:
    uv run python src/etl.py.
"""

from __future__ import annotations

import argparse
import gc
import logging
import os
import socket
import subprocess
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd


###Argparse
def parse_args():
    """Parses ETL command-line arguments."""
    parser = argparse.ArgumentParser(
        prog="processing", description="ETL step: carga, limpieza y agregación mensual"
    )

    parser.add_argument(
        "--raw-dir",
        type=str,
        default=None,
        help="Directorio de datos crudos. Si no se especifica, usa data/raw",
    )

    parser.add_argument(
        "--prep-dir",
        type=str,
        default=None,
        help="Directorio de salida preprocesada. Si no se especifica, usa data/prep",
    )

    parser.add_argument(
        "--artifacts-dir",
        type=str,
        default=None,
        help="Directorio de artifacts. Si no se especifica, usa artifacts/",
    )

    return parser.parse_args()


# ----------------------------
# Logging
# ----------------------------
class UTCFormatter(logging.Formatter):
    """Formatter que fuerza timestamps en UTC y en formato ISO 8601 (con sufijo Z)."""

    def formatTime(self, record, datefmt=None):  # noqa: N802 (firma esperada por logging)
        """Format log time in UTC ISO 8601."""
        dt = datetime.fromtimestamp(record.created, tz=UTC)
        return dt.isoformat(timespec="seconds").replace("+00:00", "Z")


def setup_logging(log_dir: Path) -> logging.LoggerAdapter:
    """Configura el sistema de logging del ETL.

    Los logs se escriben:
    - En consola
    - En artifacts/logs/etl.log

    Parameters
    ----------
    log_dir : pathlib.Path
        Directorio donde se almacenarán los logs.

    Returns:
    -------
    logging.LoggerAdapter
        Logger con contexto (hostname) incluido en cada evento.
    """
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "etl.log"

    formatter = UTCFormatter(
        fmt="%(asctime)s - %(hostname)s - %(name)s - %(levelname)s - %(message)s"
    )

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # Evitar logs duplicados si se re-ejecuta en el mismo proceso
    root_logger.handlers.clear()

    file_handler = logging.FileHandler(log_file)  # append por default (mode="a")
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)

    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.INFO)
    stream_handler.setFormatter(formatter)

    root_logger.addHandler(file_handler)
    root_logger.addHandler(stream_handler)

    base_logger = logging.getLogger(__name__)
    logger_adapter = logging.LoggerAdapter(
        base_logger, {"hostname": socket.gethostname()}
    )
    return logger_adapter


# logger global (se inicializa en main)
logger: logging.LoggerAdapter


# ----------------------------
# Utilidades de rutas
# ----------------------------
def find_repo_root(start: Path) -> Path:
    """Encuentra el directorio raíz del proyecto de la tarea.

    El root se identifica buscando un archivo `pyproject.toml` y la carpeta `data/`
    en alguno de los directorios padre.
    """
    cur = start.resolve()
    for _ in range(10):
        if (cur / "pyproject.toml").exists() and (cur / "data").exists():
            return cur
        cur = cur.parent

    raise RuntimeError(
        "No se encontró el root del proyecto (pyproject.toml + data/). "
        "Ejecuta el script dentro de una carpeta de tarea (tareas/tarea-XX)."
    )


# ----------------------------
# Kaggle download (Extract) - Competencia
# ----------------------------
def _kaggle_credentials_available() -> bool:
    """Valida si hay credenciales de Kaggle disponibles por.

    - env vars: KAGGLE_USERNAME y KAGGLE_KEY
    - archivo: ~/.kaggle/kaggle.json
    """
    if os.getenv("KAGGLE_USERNAME") and os.getenv("KAGGLE_KEY"):
        return True
    kaggle_json = Path.home() / ".kaggle" / "kaggle.json"
    return kaggle_json.exists()


def download_kaggle_competition_data(
    raw_dir: Path,
    competition: str,
    required_files: list[str],
    force: bool = False,
) -> None:
    """Descarga datos de una competencia de Kaggle a data/raw usando Kaggle API.

    Si los archivos requeridos ya existen, no descarga (a menos que force=True).
    """
    raw_dir.mkdir(parents=True, exist_ok=True)

    missing = [f for f in required_files if not (raw_dir / f).exists()]
    if not force and not missing:
        logger.info("Kaggle: archivos ya existen en %s. No se descarga.", raw_dir)
        return

    if not _kaggle_credentials_available():
        raise RuntimeError(
            "No se encontraron credenciales de Kaggle.\n"
            "Configura ~/.kaggle/kaggle.json o exporta:\n"
            "  KAGGLE_USERNAME=...\n"
            "  KAGGLE_KEY=...\n"
        )

    logger.info("Kaggle: descargando competencia '%s' hacia %s", competition, raw_dir)

    cmd = [
        "kaggle",
        "competitions",
        "download",
        "-c",
        competition,
        "-p",
        str(raw_dir),
    ]
    if force:
        cmd.append("--force")

    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        logger.info("Kaggle: descarga completada.")
    except subprocess.CalledProcessError as e:
        logger.error("Kaggle: falló la descarga. STDOUT: %s", e.stdout)
        logger.error("Kaggle: falló la descarga. STDERR: %s", e.stderr)
        raise

    zip_files = sorted(
        raw_dir.glob("*.zip"), key=lambda p: p.stat().st_mtime, reverse=True
    )
    if not zip_files:
        logger.warning(
            "Kaggle: no se encontró .zip en %s. ¿Ya estaban descargados?", raw_dir
        )
        return

    zip_path = zip_files[0]
    logger.info("Kaggle: descomprimiendo %s", zip_path.name)

    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(raw_dir)

    logger.info("Kaggle: descompresión completada en %s", raw_dir)

    try:
        zip_path.unlink()
        logger.info("Kaggle: eliminado zip %s", zip_path.name)
    except Exception:
        logger.warning(
            "Kaggle: no se pudo eliminar el zip %s (no es crítico).", zip_path.name
        )

    missing_after = [f for f in required_files if not (raw_dir / f).exists()]
    if missing_after:
        raise FileNotFoundError(
            f"Kaggle descargó/descomprimió pero aún faltan archivos en {raw_dir}:\n- "
            + "\n- ".join(missing_after)
        )

    logger.info("Kaggle: insumos de competencia listos ✅")


# ----------------------------
# KaggleHub download (Extract) - Traducciones en inglés
# ----------------------------
def download_translations_kagglehub(
    raw_dir: Path,
    dataset_slug: str,
    translation_files: list[str],
    force: bool = False,
) -> None:
    """Descarga 3 archivos de traducciones (en inglés) desde KaggleHub.

    Los guarda en data/raw.
    """
    raw_dir.mkdir(parents=True, exist_ok=True)

    try:
        import kagglehub
        from kagglehub import KaggleDatasetAdapter
    except Exception as e:
        raise RuntimeError(
            "No está instalado kagglehub.\n"
            "Instálalo con:\n"
            "  uv add kagglehub\n"
            f"Detalle: {e}"
        ) from e

    for file_path in translation_files:
        out_path = raw_dir / file_path
        if out_path.exists() and not force:
            logger.info("KaggleHub: %s ya existe. Se omite descarga.", out_path.name)
            continue

        logger.info("KaggleHub: descargando %s desde %s", file_path, dataset_slug)

        df_trans = kagglehub.load_dataset(
            KaggleDatasetAdapter.PANDAS,
            dataset_slug,
            file_path,
        )

        df_trans.to_csv(out_path, index=False)
        logger.info("KaggleHub: guardado %s", out_path)


# ----------------------------
# Lectura de insumos
# ----------------------------
def load_raw_data(raw_dir: Path) -> dict[str, pd.DataFrame]:
    """Carga los archivos crudos requeridos desde `data/raw`."""
    required = [
        "sales_train.csv",
        "test.csv",
        "items_en.csv",
        "shops_en.csv",
        "item_categories_en.csv",
        "sample_submission.csv",
    ]

    missing = [f for f in required if not (raw_dir / f).exists()]
    if missing:
        raise FileNotFoundError(
            f"Faltan archivos en {raw_dir}:\n- " + "\n- ".join(missing)
        )

    logger.info("Cargando datos crudos desde %s", raw_dir)

    return {
        "sales": pd.read_csv(raw_dir / "sales_train.csv"),
        "test": pd.read_csv(raw_dir / "test.csv"),
        "items": pd.read_csv(raw_dir / "items_en.csv"),
        "shops": pd.read_csv(raw_dir / "shops_en.csv"),
        "cats": pd.read_csv(raw_dir / "item_categories_en.csv"),
        "sample": pd.read_csv(raw_dir / "sample_submission.csv"),
    }


# ----------------------------
# Transformaciones
# ----------------------------
def build_enriched_sales(df_dict: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Construye el dataset de ventas enriquecido tipo tabla de hechos."""
    logger.info("Construyendo dataset enriquecido tipo tabla de hechos")

    sales = df_dict["sales"]
    items = df_dict["items"]
    shops = df_dict["shops"]
    cats = df_dict["cats"]

    df = (
        sales.merge(items, on="item_id", how="left")
        .merge(shops, on="shop_id", how="left")
        .merge(cats, on="item_category_id", how="left")
    )

    # Tipos (downcast para RAM)
    df["item_price"] = pd.to_numeric(
        df["item_price"], errors="coerce", downcast="float"
    )
    df["item_cnt_day"] = pd.to_numeric(
        df["item_cnt_day"], errors="coerce", downcast="float"
    )

    # Fecha
    df["date"] = pd.to_datetime(df["date"], format="%d.%m.%Y", errors="coerce")

    # KPI base
    df["sales"] = (df["item_cnt_day"] * df["item_price"]).astype("float32")

    # year/month (para controles rápidos)
    df["year"] = df["date"].dt.year.astype("int16")
    df["month"] = df["date"].dt.month.astype("int8")

    # IDs (int chicos si aplica)
    for col in ("shop_id", "item_id", "item_category_id"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce", downcast="integer")

    logger.info("Dataset enriquecido generado con shape %s", df.shape)
    return df


def build_yearly_control(df: pd.DataFrame) -> pd.DataFrame:
    """Genera métricas anuales de control."""
    logger.info("Generando métricas anuales cifras control")

    return df.groupby("year", as_index=False).agg(
        total_sales=("sales", "sum"),
        total_units=("item_cnt_day", "sum"),
        num_transactions=("item_cnt_day", "size"),
        avg_price=("item_price", "mean"),
        active_products=("item_id", "nunique"),
        active_shops=("shop_id", "nunique"),
    )


def build_monthly_with_lags(
    df: pd.DataFrame, items_lookup: pd.DataFrame
) -> pd.DataFrame:
    """Genera una tabla agregada mensual con variables lag.

    - Mantiene columna `date` con month-end (equivalente a freq="ME").
    - Quita `item_name` de la llave (groupby) y lo agrega después (opción B).
    - Conserva mismas métricas, columnas y orden (layout) de salida.

    Parameters
    ----------
    df : pd.DataFrame
        Dataset enriquecido diario.
    items_lookup : pd.DataFrame
        DataFrame con columnas ["item_id", "item_name"] y item_id único (catálogo).
    """
    logger.info("Construyendo agregado mensual con lags")

    # Copia chica (evita tocar df original si luego lo quieres usar)
    df = df.copy()

    # Month-end vectorizado (equivalente a Grouper freq="ME")
    df["month_end"] = df["date"] + pd.offsets.MonthEnd(0)

    # Para active_days sin lambda costosa: normaliza datetime (00:00:00) y nunique
    df["date_day"] = df["date"].dt.normalize()

    # 1) Groupby SIN item_name en llave
    monthly = (
        df.groupby(["month_end", "shop_id", "item_id"], sort=False, observed=False)
        .agg(
            monthly_sales=("sales", "sum"),
            monthly_units=("item_cnt_day", "sum"),
            avg_price=("item_price", "mean"),
            min_price=("item_price", "min"),
            max_price=("item_price", "max"),
            num_transactions=("item_cnt_day", "size"),
            active_days=("date_day", "nunique"),
        )
        .reset_index()
        .rename(columns={"month_end": "date"})
    )

    # 2) Agregar item_name desde lookup (barato vs derivarlo del df de 2.9M filas)
    items_lookup = items_lookup[["item_id", "item_name"]].drop_duplicates("item_id")
    monthly = monthly.merge(items_lookup, on="item_id", how="left")

    # 3) year/month como antes
    monthly["year"] = monthly["date"].dt.year.astype("int16")
    monthly["month"] = monthly["date"].dt.month.astype("int8")

    # 4) Orden para lags (igual que antes)
    monthly = monthly.sort_values(["shop_id", "item_id", "year", "month"]).reset_index(
        drop=True
    )

    # 5) Lags (1 mes)
    monthly["monthly_sales_lag_1"] = monthly.groupby(
        ["shop_id", "item_id"], sort=False
    )["monthly_sales"].shift(1)
    monthly["monthly_units_lag_1"] = monthly.groupby(
        ["shop_id", "item_id"], sort=False
    )["monthly_units"].shift(1)

    # 6) Fill solo lags
    monthly[["monthly_sales_lag_1", "monthly_units_lag_1"]] = monthly[
        ["monthly_sales_lag_1", "monthly_units_lag_1"]
    ].fillna(0)

    # 7) Layout idéntico al previo
    monthly = monthly[
        [
            "date",
            "shop_id",
            "item_id",
            "item_name",
            "monthly_sales",
            "monthly_units",
            "avg_price",
            "min_price",
            "max_price",
            "num_transactions",
            "active_days",
            "year",
            "month",
            "monthly_sales_lag_1",
            "monthly_units_lag_1",
        ]
    ]

    logger.info("Agregado mensual generado con shape %s", monthly.shape)
    return monthly


# ----------------------------
# Main
# ----------------------------
def main() -> None:
    """Ejecuta el pipeline ETL completo para la Tarea-03."""
    # Checar el logger.
    global logger

    args = parse_args()

    repo_root = find_repo_root(Path(__file__))

    raw_dir = Path(args.raw_dir) if args.raw_dir else repo_root / "data" / "raw"
    prep_dir = Path(args.prep_dir) if args.prep_dir else repo_root / "data" / "prep"
    artifacts_dir = (
        Path(args.artifacts_dir) if args.artifacts_dir else repo_root / "artifacts"
    )

    logger = setup_logging(artifacts_dir / "logs")
    logger.info("🚀 Iniciando ETL Tarea-03")

    logger = setup_logging(repo_root / "artifacts" / "logs")

    logger.info("🚀 Iniciando ETL Tarea-03")

    raw_dir = repo_root / "data" / "raw"
    prep_dir = repo_root / "data" / "prep"
    artifacts_dir = repo_root / "artifacts"

    prep_dir.mkdir(parents=True, exist_ok=True)
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)

    # 0A) Extract: Descargar zip de la competencia si faltan insumos base
    required_competition = [
        "sales_train.csv",
        "test.csv",
        "sample_submission.csv",
    ]
    download_kaggle_competition_data(
        raw_dir=raw_dir,
        competition="competitive-data-science-predict-future-sales",
        required_files=required_competition,
        force=False,
    )

    # 0B) Extract: Descargar traducciones EN (3 archivos extra) desde KaggleHub
    translations = [
        "items_en.csv",
        "shops_en.csv",
        "item_categories_en.csv",
    ]
    download_translations_kagglehub(
        raw_dir=raw_dir,
        dataset_slug="remisharoon/predict-future-sales-translated-dataset",
        translation_files=translations,
        force=False,
    )

    # 1) Load
    df_dict = load_raw_data(raw_dir)

    # 2) Build enriched dataset
    df = build_enriched_sales(df_dict)

    # 3) Controles
    yearly_control = build_yearly_control(df)
    yearly_control_path = artifacts_dir / "yearly_control.csv"
    yearly_control.to_csv(yearly_control_path, index=False)
    logger.info("Cifras Control anual guardado en %s", yearly_control_path)

    # 4) Monthly + lags (opción B + optimizado)
    items_lookup = df_dict["items"][["item_id", "item_name"]].drop_duplicates("item_id")
    monthly = build_monthly_with_lags(df, items_lookup=items_lookup)

    # 5) Outputs
    df_out_parquet = prep_dir / "df_base.parquet"
    monthly_out_parquet = prep_dir / "monthly_with_lags.parquet"
    df_out_csv = prep_dir / "df_base.csv"
    monthly_out_csv = prep_dir / "monthly_with_lags.csv"

    # 6) Save with parquet fallback
    try:
        df.to_parquet(df_out_parquet, index=False)
        monthly.to_parquet(monthly_out_parquet, index=False)
        logger.info(
            "Parquet guardado correctamente: %s y %s",
            df_out_parquet,
            monthly_out_parquet,
        )
    except Exception as e:
        logger.warning("Parquet no disponible (%s). Guardando CSV.", e)
        df.to_csv(df_out_csv, index=False)
        monthly.to_csv(monthly_out_csv, index=False)
        logger.info("CSV guardado en %s y %s", df_out_csv, monthly_out_csv)
    else:
        df.to_csv(df_out_csv, index=False)
        monthly.to_csv(monthly_out_csv, index=False)
        logger.info("CSV guardado en %s y %s", df_out_csv, monthly_out_csv)

    # Limpieza RAM
    del df, monthly
    gc.collect()

    logger.info("✅ ETL finalizado correctamente")


if __name__ == "__main__":
    main()
