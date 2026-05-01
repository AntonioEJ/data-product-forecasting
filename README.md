# data-product-forecasting

Producto de datos de pronóstico de demanda construido sobre AWS con pipeline ETL reproducible, arquitectura medallion y frontend Streamlit.

Este proyecto construye un producto de datos de pronóstico de demanda sobre el dataset
[Predict Future Sales](https://www.kaggle.com/c/competitive-data-science-predict-future-sales)
de Kaggle (~2.9M registros de ventas). Abarca ingestión, transformación, feature engineering,
modelado y visualización.

## Autores

- José Antonio Esparza
- Gustavo Pardo

## Qué resuelve

Este proyecto implementa un pipeline end-to-end de forecasting de ventas orientado a usuarios de negocio (Finanzas, Planeación, BI). Descarga datos de competencias de Kaggle, los transforma a través de capas medallion (bronze → silver → gold), genera features para modelos de ML y expone los resultados a través de una aplicación Streamlit conectada a RDS.

No es un notebook exploratorio. Es un producto de datos diseñado para ejecutarse de forma reproducible en local, Docker o SageMaker Processing Jobs.

## Arquitectura

### Flujo de datos

```
Kaggle / S3 (raw)
       │
       ▼
   ETL local / Docker / SageMaker
       │
       ├── Bronze (CSV → Parquet en S3, registro en Glue)
       ├── Silver (datos limpios y preparados)
       └── Gold  (tabla analítica vía Athena CTAS)
       │
       ▼
   Feature Engineering
       │
       ▼
   Modelo (LightGBM) → predicciones batch
       │
       ▼
   RDS PostgreSQL (predicciones precomputadas)
       │
       ▼
   Streamlit (consulta interactiva + exportación batch)
```

### Capas medallion

- **Bronze**: ingesta directa de archivos CSV desde `data/raw/` hacia S3 en formato Parquet. Registro automático en Glue Data Catalog.
- **Silver**: datos limpios y preparados desde `data/prep/`. Misma mecánica de subida a S3 y registro en Glue.
- **Gold**: tabla analítica construida mediante CTAS en Athena a partir de las capas anteriores.

### Decisiones de diseño

- Predicciones precomputadas (batch) almacenadas en RDS para baja latencia en consultas.
- Exportaciones batch a S3 con URL firmada.
- Credenciales gestionadas vía Secrets Manager y variables de entorno (nunca hardcodeadas).
- Logging estructurado compatible con CloudWatch.

## 🛠️ Stack tecnológico

| Categoría | Herramientas | Por qué |
|---|---|---|
| Lenguaje | Python 3.11+ | Ecosistema maduro para data/ML |
| Gestión de deps | uv + lockfile | Instalaciones deterministas y rápidas |
| Linting/formato | Ruff | PEP 8, imports, docstrings, bugbear — un solo tool |
| Frontend | Streamlit | Prototipos rápidos para usuarios de negocio |
| Cloud | AWS (S3, Glue, Athena, RDS, ECS Fargate, ECR, Secrets Manager) | Stack enterprise estándar |
| ML | LightGBM, scikit-learn | Modelos de gradient boosting para series de tiempo |
| ETL | pandas, pyarrow, awswrangler | Lectura/escritura eficiente a S3/Glue |
| DB | SQLAlchemy + psycopg (v3) | Connection pooling, ORM-ready, sin compilación C |
| Contenedores | Docker | Reproducibilidad entre local y cloud |
| IaC | CloudFormation | Infraestructura versionada (RDS + ECS + ALB) |
| CI | GitHub Actions | Lint + format + score en cada PR |

## Estructura del repositorio

```
.
├── app/                        → UI Streamlit
│   ├── __init__.py
│   ├── components/
│   ├── main.py
│   └── pages/
│       ├── batch_export.py
│       ├── business_feedback.py
│       ├── forecast_exploration.py
│       └── model_evaluation.py
├── artifacts/                  → Outputs del ETL
│   ├── logs/
│   │   └── etl.log
│   ├── models/
│   ├── predictions/
│   └── yearly_control.csv
├── backend/                    
├── config/                     
├── config.py                   → Rutas y parámetros centralizados (PathsConfig, ModelConfig)
├── .streamlit/
│   └── config.toml             → Config Streamlit (headless, puerto 8501)
├── data/
│   ├── inference/
│   ├── predictions/
│   ├── prep/                   → Datasets preparados (parquet + csv)
│   │   ├── df_base.csv
│   │   ├── df_base.parquet
│   │   ├── monthly_with_lags.csv
│   │   └── monthly_with_lags.parquet
│   ├── raw/                    → CSVs de Kaggle (no se commitean)
│   │   ├── item_categories_en.csv
│   │   ├── item_categories.csv
│   │   ├── items_en.csv
│   │   ├── items.csv
│   │   ├── sales_train.csv
│   │   ├── sample_submission.csv
│   │   ├── shops_en.csv
│   │   ├── shops.csv
│   │   └── test.csv
│   └── rds.py                  → Capa de acceso a RDS (SQLAlchemy + psycopg3)
├── docs/
│   ├── arquitectura.md
│   ├── erd.md
│   └── screenshots/
├── etl/
│   ├── __init__.py
│   ├── __main__.py
│   ├── bronze.py               → Ingesta CSV → S3/Glue
│   ├── Dockerfile              → Imagen para ejecutar ETL en Docker/SageMaker
│   ├── etl.py                  → Pipeline ETL principal (descarga, limpieza, agregación)
│   ├── features.py             → Feature engineering (lags, rolling means)
│   ├── gold.py                 → CTAS en Athena
│   ├── silver.py               → Datos limpios → S3/Glue
│   └── test/
│       └── test_prep.py        → Tests de validación de outputs
├── inference/                  → (pendiente)
├── infra/
│   └── core.yaml               → CloudFormation stack
├── models/                     → Artefactos de ML
├── notebooks/                  → EDA y prototipos
├── services/                   → Lógica de negocio (pendiente)
├── utils/
│   └── logging.py              → Logging centralizado (CloudWatch-ready)
├── .dockerignore               → Exclusiones del build Docker
├── Dockerfile                  → Imagen Streamlit para Fargate (health check incluido)
├── pyproject.toml              → Dependencias, config de ruff y pytest
└── uv.lock                     → Lockfile determinista
```

## ⚙️ Cómo ejecutar

### Local

```bash
git clone https://github.com/AntonioEJ/data-product-forecasting.git
cd data-product-forecasting

# Instalar dependencias (incluye dev: ruff, pytest)
pip install uv
uv sync --all-extras

# Configurar credenciales de Kaggle
export KAGGLE_USERNAME=<tu-usuario>
export KAGGLE_KEY=<tu-key>

# Ejecutar ETL
uv run python -m etl.etl --raw-dir data/raw --prep-dir data/prep --artifacts-dir artifacts

# Lanzar Streamlit
uv run streamlit run app/main.py
```

### Docker

```bash
# ETL
docker build -t etl-pipeline:latest -f etl/Dockerfile .
docker run --rm \
    -v "$PWD/data:/app/data" \
    -v "$PWD/artifacts:/app/artifacts" \
    -e KAGGLE_USERNAME \
    -e KAGGLE_KEY \
    etl-pipeline:latest

# Streamlit
docker build -t forecasting-app:latest .
docker run --rm -p 8501:8501 forecasting-app:latest
```

### SageMaker Studio 

El proyecto se clona y ejecuta directamente en SageMaker Studio o una instancia de notebook.
La estructura en SageMaker queda en `~/data-product-forecasting` con las mismas carpetas que el repo.

```bash
# Desde la terminal de SageMaker Studio
cd ~/data-product-forecasting

# Instalar uv si no está disponible
pip install uv

# Instalar dependencias
uv sync --all-extras

# Configurar credenciales de Kaggle
export KAGGLE_USERNAME=<tu-usuario>
export KAGGLE_KEY=<tu-key>

uv run python -m etl.etl

```

Outputs generados tras ejecutar el ETL en SageMaker:

```
data/
├── prep/
│   ├── df_base.csv
│   ├── df_base.parquet
│   ├── monthly_with_lags.csv
│   └── monthly_with_lags.parquet
artifacts/
├── logs/
│   └── etl.log
└── yearly_control.csv
```

> **Nota**: en SageMaker no se necesita Docker. El ETL corre directamente con `uv run`.
> Los logs se escriben en `artifacts/logs/etl.log` y también en stdout (visible en CloudWatch).

## Pipeline Medallion (Bronze / Silver / Gold)

Después de ejecutar el ETL principal (`etl.etl`), los scripts medallion suben los datos procesados a S3 y los registran en AWS Glue Data Catalog.

### Bronze — `etl/bronze.py`

```bash
python etl/bronze.py --bucket <tu-bucket>
```

- Lee todos los archivos `.csv` de `data/raw/` (sales_train, items_en, shops_en, etc.).
- Convierte cada archivo a Parquet y lo sube a `s3://<bucket>/forecasting/bronze/<tabla>/`.
- Registra cada tabla en Glue Data Catalog bajo la base de datos `forecasting_bronze`.
- Validación: verifica que cada CSV tenga al menos una fila antes de subir.
- Al final, confirma que todos los archivos existen en S3.

### Silver — `etl/silver.py`

```bash
python etl/silver.py --bucket <tu-bucket>
```

- Lee todos los archivos `.parquet` de `data/prep/` (df_base, monthly_with_lags).
- Sube cada archivo a `s3://<bucket>/forecasting/silver/<tabla>/`.
- Registra cada tabla en Glue Data Catalog bajo la base de datos `forecasting_silver`.
- Validación: confirma existencia de cada archivo en S3 al terminar.

### Gold — `etl/gold.py`

```bash
python etl/gold.py --bucket <tu-bucket>
```

- Ejecuta una consulta CTAS en Athena para crear la tabla analítica `forecasting_gold.ventas_analitica`.
- Combina datos de las capas Bronze/Silver en una vista consolidada para consumo por modelos y dashboards.
- Resultado almacenado en `s3://<bucket>/forecasting/gold/`.

### Orden de ejecución

```bash
# 1. ETL principal (descarga, limpieza, feature engineering)
uv run python -m etl.etl

# 2. Bronze (raw → S3/Glue)
python etl/bronze.py --bucket <tu-bucket>

# 3. Silver (prep → S3/Glue)
python etl/silver.py --bucket <tu-bucket>

# 4. Gold (Athena CTAS)
python etl/gold.py --bucket <tu-bucket>
```

### Buenas Prácticas del Pipeline ETL

| Práctica | Implementación |
|---|---|
| **Idempotencia** | Bronze: `overwrite` en chunk 0 + `append` en siguientes. Silver: `overwrite` por archivo. Gold: `delete_table_if_exists` + limpieza S3 antes del CTAS. |
| **Memory-safe** | Bronze: chunks de 500K filas + `del chunk` + `gc.collect()`. Silver: lectura file-by-file + `del df` + `gc.collect()`. Gold: Athena ejecuta el CTAS sin carga en RAM. |
| **Logging profesional** | Módulo `logging` con handlers a consola y archivo (`artifacts/logs/{capa}_etl.log`). Timestamps por fase, inicio y fin delimitados, cifras de control al final. |
| **Manejo de errores** | `try/except` en `main()` con `logger.exception()` + `sys.exit(1)`. Sin fallos silenciosos. |
| **Docstrings** | Todas las funciones documentadas con Google style: descripción, `Args`, `Returns` y `Raises`. |
| **Modularidad** | Patrón `validate_file` → `upload_table` → `main` en cada script. Funciones con responsabilidad única. |
| **Cifras de control** | Cada script imprime al final: tablas procesadas, filas totales, tiempo por tabla y tiempo total. |
| **CLI** | `argparse` con `--bucket` (y `--data-dir` en Bronze). Documentación disponible con `--help`. |
| **Pylint** | Bronze: 9.78/10 · Silver: 10.00/10 · Gold: 9.82/10 · Features: 10.00/10 · ETL: 9.74/10 |

### Infraestructura (CloudFormation)

`infra/core.yaml` despliega toda la infraestructura en un solo stack:
- RDS PostgreSQL 17 (db.t3.micro, encrypted, free tier)
- Secrets Manager con credenciales
- ECS Fargate cluster + service + task definition
- ALB internet-facing con health check en `/_stcore/health`
- IAM roles con least privilege (secrets scoped por ARN)
- CloudWatch log group

> **Nota:** El build de Docker se hace desde SageMaker. El deploy de CloudFormation
> se hace desde **CloudShell** o la consola de CloudFormation (el rol de SageMaker no tiene
> permisos de CloudFormation/ELB/IAM).

#### Paso 1 — Build de la imagen (SageMaker)

```bash
cd ~/data-product-forecasting
git pull origin feature/etl-processing
docker build --network sagemaker -t data-product-forecast:local .
```

#### Paso 2 — Crear repo ECR y obtener URI (SageMaker)

```bash
REGION=us-east-1
aws ecr create-repository --repository-name forecast-app-ecr --region $REGION 2>/dev/null || true

ECR_URI=$(aws ecr describe-repositories \
    --repository-names forecast-app-ecr \
    --region $REGION \
    --query "repositories[0].repositoryUri" \
    --output text)

echo "ECR URI: $ECR_URI"
```

#### Paso 3 — Login, tag y push a ECR (SageMaker)

```bash
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

aws ecr get-login-password --region $REGION | \
    docker login --username AWS --password-stdin \
    "${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com"

docker tag data-product-forecast:local "${ECR_URI}:latest"
docker push "${ECR_URI}:latest"
```

#### Paso 4 — Obtener VPC y subnets (CloudShell)

Abrir **CloudShell** (icono `>_` en la barra superior de la consola AWS):

```bash
git clone https://github.com/AntonioEJ/data-product-forecasting.git
cd data-product-forecasting
git checkout feature/etl-processing

REGION=us-east-1
ECR_URI="529236942598.dkr.ecr.${REGION}.amazonaws.com/forecast-app-ecr"

VPC_ID=$(aws ec2 describe-vpcs \
    --filters "Name=isDefault,Values=true" \
    --query "Vpcs[0].VpcId" \
    --output text --region $REGION)

SUBNET_IDS=$(aws ec2 describe-subnets \
    --filters "Name=vpc-id,Values=${VPC_ID}" \
    --query "Subnets[*].SubnetId" \
    --output text --region $REGION | tr '\t' ',')

echo "VPC:     ${VPC_ID}"
echo "Subnets: ${SUBNET_IDS}"
```

#### Paso 5 — Desplegar el stack (CloudShell)

```bash
# Limpiar stack fallido si existe
aws cloudformation delete-stack --stack-name forecast-app --region $REGION 2>/dev/null
aws cloudformation wait stack-delete-complete --stack-name forecast-app --region $REGION 2>/dev/null
aws logs delete-log-group --log-group-name /ecs/forecast-app --region $REGION 2>/dev/null || true

# Desplegar
aws cloudformation deploy \
    --template-file infra/core.yaml \
    --stack-name forecast-app \
    --capabilities CAPABILITY_NAMED_IAM \
    --region $REGION \
    --parameter-overrides \
        VpcId="${VPC_ID}" \
        SubnetIds="${SUBNET_IDS}" \
        ImageUri="${ECR_URI}:latest" \
        DBPassword="TuPasswordSeguro123!"
```

CloudFormation crea todos los recursos (~8-10 minutos, RDS es lo que mas tarda).

#### Paso 6 — Verificar el despliegue (CloudShell)

```bash
# Estado del stack
aws cloudformation describe-stacks \
    --stack-name forecast-app \
    --query "Stacks[0].StackStatus" \
    --output text --region $REGION
# Esperado: CREATE_COMPLETE

# Obtener la URL de la app
aws cloudformation describe-stacks \
    --stack-name forecast-app \
    --query "Stacks[0].Outputs[?OutputKey=='AppURL'].OutputValue" \
    --output text --region $REGION
# http://forecast-app-alb-33822663.us-east-1.elb.amazonaws.com
```

**App URL:** http://forecast-app-alb-33822663.us-east-1.elb.amazonaws.com

#### Re-deploy de imagen (actualizaciones futuras)

Desde SageMaker:
```bash
docker build --network sagemaker -t data-product-forecast:local . \
  && docker tag data-product-forecast:local "${ECR_URI}:latest" \
  && docker push "${ECR_URI}:latest"
```

Desde CloudShell:
```bash
aws ecs update-service \
    --cluster forecast-app-cluster \
    --service forecast-app \
    --force-new-deployment \
    --region us-east-1
```

#### Eliminar el stack

```bash
aws cloudformation delete-stack --stack-name forecast-app --region us-east-1
aws cloudformation wait stack-delete-complete --stack-name forecast-app --region us-east-1
```

## Validación de código

```bash
uv run ruff format --check .    # formato
uv run ruff check .             # lint (E/F/I/B/C4/UP/D)
uv run pytest -v                # tests
```

## 📋 Prácticas implementadas

- **PEP 8 estricto**: enforced por Ruff con reglas E, F, I, B, C4, UP, D (Google-style docstrings).
- **Logging estructurado**: formato compatible con CloudWatch, timestamps UTC, hostname como contexto. Sin `print()`.
- **Modularidad del ETL**: descarga, limpieza, feature engineering y persistencia en funciones separadas.
- **Reproducibilidad**: `uv.lock` + `pyproject.toml` + `--frozen` en Docker y CI. Sin instalaciones ad-hoc.
- **Seguridad**: credenciales vía env vars o Secrets Manager. Sin passwords en código. Queries parametrizadas con SQLAlchemy `text()` (`:nombre`).
- **Rutas parametrizables**: `--raw-dir`, `--prep-dir`, `--artifacts-dir` permiten ejecutar en local, Docker y SageMaker sin cambiar código.
- **CI automatizado**: GitHub Actions con format check, lint, ruff score y resumen por PR.

## Mejoras pendientes

- Conectar páginas de Streamlit a RDS (actualmente usan datos mock).
- Implementar training pipeline con tracking de experimentos.
- Agregar tests de integración para las capas S3/Glue.
- Configurar GitHub Actions para CI automático en PRs.

## Documentación adicional

Diagramas de arquitectura y modelo de datos en `docs/`.
