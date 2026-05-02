"""Punto de entrada CLI para carga de datos a RDS.

Uso:
    uv run python -m db --dry-run   # valida artefactos locales
    uv run python -m db              # carga real (requiere env vars RDS_*)
"""

from __future__ import annotations

import argparse
import json
import sys

from db.load_all import main


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Carga parquets y CSVs a RDS.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Valida artefactos locales sin conectar a RDS.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    result = main(dry_run=args.dry_run)
    print(json.dumps(result, indent=2, default=str))
    if result.get("validation") == "failed":
        sys.exit(1)
