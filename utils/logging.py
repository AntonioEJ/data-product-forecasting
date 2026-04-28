"""Configuración centralizada de logging estructurado para data-product-forecasting.

Diseñado para compatibilidad con AWS CloudWatch.
"""

import logging
import sys

LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(module)s | %(message)s"

_LOGGER_INITIALIZED = False


def setup_logging(level: int = logging.INFO) -> None:
    """Configura el logger raíz para logging estructurado.

    Asegura que los logs sean compatibles con AWS CloudWatch y evita
    configuración duplicada.

    Args:
        level: Nivel de logging (default: INFO).
    """
    global _LOGGER_INITIALIZED

    if _LOGGER_INITIALIZED:
        return

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(LOG_FORMAT)
    handler.setFormatter(formatter)

    root_logger.handlers.clear()
    root_logger.addHandler(handler)

    # Reduce noise from AWS SDK
    logging.getLogger("boto3").setLevel(logging.WARNING)
    logging.getLogger("botocore").setLevel(logging.WARNING)

    root_logger.info(
        "Logging initialized | level=%s",
        logging.getLevelName(level),
    )

    _LOGGER_INITIALIZED = True


def get_logger(name: str | None = None) -> logging.Logger:
    """Obtiene una instancia de logger con configuración consistente.

    Args:
        name: Nombre del logger (típicamente __name__).

    Returns:
        Logger configurado.
    """
    return logging.getLogger(name)
