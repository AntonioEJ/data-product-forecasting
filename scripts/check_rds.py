"""Valida la conexion a RDS PostgreSQL.

Modos de uso:
  - SageMaker/ECS (recomendado): lee credenciales de AWS Secrets Manager automaticamente.
  - Local: provee RDS_PASSWORD como variable de entorno.

Uso local:
    RDS_PASSWORD=<password> python scripts/check_rds.py

Uso en SageMaker (sin variables de entorno):
    python scripts/check_rds.py
"""

import json
import os
import sys

import psycopg

SECRET_NAME = "forecast-app-rds-credentials"
REGION = "us-east-1"
RDS_HOST_DEFAULT = "forecast-app-db.cgfw8ius6eld.us-east-1.rds.amazonaws.com"


def _get_secret() -> dict:
    """Obtiene las credenciales desde AWS Secrets Manager."""
    import boto3
    client = boto3.client("secretsmanager", region_name=REGION)
    response = client.get_secret_value(SecretId=SECRET_NAME)
    return json.loads(response["SecretString"])


def main() -> None:
    # Intentar obtener credenciales desde Secrets Manager (funciona en SageMaker/ECS)
    secret: dict = {}
    if not os.environ.get("RDS_PASSWORD"):
        try:
            secret = _get_secret()
            print(f"Credenciales obtenidas desde Secrets Manager ({SECRET_NAME})")
        except Exception as e:
            print(f"No se pudo acceder a Secrets Manager: {e}")
            print("Provee RDS_PASSWORD como variable de entorno.")
            sys.exit(1)

    host = os.environ.get("RDS_HOST") or secret.get("host", RDS_HOST_DEFAULT)
    port = int(os.environ.get("RDS_PORT") or secret.get("port", 5432))
    dbname = os.environ.get("RDS_DBNAME") or secret.get("dbname", "forecasting")
    user = os.environ.get("RDS_USER") or secret.get("username", "postgres")
    password = os.environ.get("RDS_PASSWORD") or secret.get("password", "")

    if not password:
        print("ERROR: No se encontro contrasena en Secrets Manager ni en RDS_PASSWORD.")
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
