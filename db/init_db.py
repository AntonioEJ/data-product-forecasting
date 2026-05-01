"""Inicializa las tablas del schema en RDS. Idempotente."""

from __future__ import annotations

from data.rds import _get_engine
from db.schema import metadata
from utils.logging import get_logger, setup_logging

logger = get_logger(__name__)


def main() -> None:
    """Crea todas las tablas definidas en el schema contra RDS.

    Idempotente: usa checkfirst implícito de create_all. No destruye
    datos existentes.
    """
    setup_logging()
    tablas = list(metadata.tables.keys())
    logger.info("Inicializando tablas: %s", tablas)
    metadata.create_all(_get_engine())
    logger.info("Tablas listas: %d creadas o ya existentes", len(tablas))


if __name__ == "__main__":
    main()
