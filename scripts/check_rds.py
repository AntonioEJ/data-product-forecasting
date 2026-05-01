"""Valida la conexion a RDS PostgreSQL usando variables de entorno."""

import os
import sys

import psycopg


def main() -> None:
    host = os.environ.get("RDS_HOST", "forecast-app-db.cgfw8ius6eld.us-east-1.rds.amazonaws.com")
    port = int(os.environ.get("RDS_PORT", "5432"))
    dbname = os.environ.get("RDS_DBNAME", "forecasting")
    user = os.environ.get("RDS_USER", "postgres")
    password = os.environ.get("RDS_PASSWORD", "")

    if not password:
        print("ERROR: RDS_PASSWORD no definida.")
        print("Uso: RDS_PASSWORD=<tu_password> uv run python scripts/check_rds.py")
        sys.exit(1)

    print(f"Conectando a {host}:{port}/{dbname} como {user} ...")

    try:
        with psycopg.connect(
            host=host,
            port=port,
            dbname=dbname,
            user=user,
            password=password,
            connect_timeout=10,
        ) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT version();")
                version = cur.fetchone()[0]
                print(f"OK - Conexion exitosa")
                print(f"    {version}")

                cur.execute(
                    "SELECT schemaname, tablename FROM pg_tables "
                    "WHERE schemaname NOT IN ('pg_catalog','information_schema') "
                    "ORDER BY schemaname, tablename;"
                )
                rows = cur.fetchall()
                if rows:
                    print(f"\nTablas en la base de datos ({len(rows)}):")
                    for schema, table in rows:
                        print(f"    {schema}.{table}")
                else:
                    print("\nBase de datos vacia (sin tablas de usuario)")

    except psycopg.OperationalError as e:
        print(f"ERROR: No se pudo conectar a RDS.")
        print(f"    {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
