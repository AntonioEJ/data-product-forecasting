# 📈 data-product-forecasting

**Producto de Datos de Pronóstico de Demanda — AWS, MLOps y Data Engineering**

---

## 👥 Autores

- José Antonio Esparza
- Gustavo Pardo

---

## 📋 Descripción General

Este proyecto implementa un producto de datos de pronóstico de demanda, desplegado en AWS y orientado a usuarios de negocio (Finanzas, Planeación, BI). Expone pronósticos de ventas mediante una aplicación web Streamlit, soportando consultas interactivas y flujos batch, con arquitectura y prácticas de ingeniería profesional.

---

## 🏗️ Arquitectura del Proyecto

### Diagrama General

```
┌────────────────────────────┐
│  Descarga data en S3 (Raw) │
└─────────────┬─────────────┘
              │
       ┌──────▼──────┐
       │   ETL/Glue  │
       └──────┬──────┘
              │
       ┌──────▼──────┐
       │   S3 Proc.  │
       └──────┬──────┘
              │
       ┌──────▼──────┐
       │   ML Batch  │
       └──────┬──────┘
              │
       ┌──────▼──────┐
       │    RDS      │
       └──────┬──────┘
              │
       ┌──────▼──────┐
       │ Streamlit   │
       └──────┬──────┘
              │
       ┌──────▼──────┐
       │  Usuario    │
       └─────────────┘
```

**Servicios AWS:**
- S3 (data lake), Glue Data Catalog, RDS (PostgreSQL), ECS Fargate, ECR, CloudFormation, Secrets Manager, (opcional: SageMaker)

**Decisiones clave:**
- Predicciones precomputadas (batch) en RDS para baja latencia.
- Exportaciones batch a S3 con URL firmada.
- Manejo seguro de credenciales con Secrets Manager.
- Logging estructurado compatible con CloudWatch.

---

data/           → Acceso a datos (RDS, S3)

## 📁 Estructura del Proyecto
```bash
.
├── app           → UI Streamlit
│   ├── __init__.py
│   ├── components
│   ├── main.py
│   └── pages
│       ├── batch_export.py
│       ├── business_feedback.py
│       ├── forecast_exploration.py
│       └── model_evaluation.py
├── artifacts     → Artefactos de modelos y predicciones
│   ├── models
│   └── predictions
├── config        → Configuración general
├── data          → Datos crudos, procesados y resultados
│   ├── inference
│   ├── predictions
│   ├── prep
│   ├── raw
│   └── rds.py
├── Dockerfile    → Imagen principal del proyecto
├── docs          → Documentación, diagramas, reporte
│   ├── arquitectura.md
│   ├── erd.md
│   ├── Modelo_de_Datos.png
│   └── screenshots
├── etl           → ETL y procesamiento batch
│   ├── __init__.py
│   ├── __main__.py
│   ├── Dockerfile
│   ├── etl.py
│   ├── features.py
│   └── test
│       └── test_prep.py
├── infra         → Infraestructura como código (CloudFormation)
│   └── core.yaml
├── models        → Lógica y artefactos de ML
├── notebooks     → EDA y prototipos
├── pyproject.toml
├── README.md
├── services      → Lógica de negocio
└── utils         → Utilidades compartidas
      └── logging.py
```

---

## 🛠️ Tecnologías Utilizadas

| Categoría         | Herramientas |
|-------------------|--------------|
| Lenguaje          | Python 3.11+ |
| Web/App           | Streamlit    |
| Cloud             | AWS (S3, Glue, RDS, ECS, ECR, CloudFormation, Secrets Manager) |
| ML/ETL            | pandas, numpy, scikit-learn, boto3, sqlalchemy, psycopg2-binary |
| Infraestructura   | Docker, CloudFormation, uv, ruff |
| Logging           | logging (CloudWatch ready) |
| Linting/Testing   | ruff, pytest |

---

## ✅ Buenas Prácticas Implementadas

| Práctica                | Implementación |
|-------------------------|----------------|
| Modularidad             | Separación app, servicios, datos, modelos, utils |
| Logging estructurado    | logging con formato, niveles y timestamps |
| Manejo de errores       | try/except, logs claros, sin fallos silenciosos |
| Docstrings profesionales| Google/NumPy style en todas las funciones |
| Linting y formato       | ruff (PEP8, imports, unused code) |
| Reproducibilidad        | uv + lockfile, pyproject.toml |
| Configuración segura    | Secrets Manager, variables de entorno |
| Infraestructura como código | CloudFormation para todos los recursos |

---

## 🚀 Ejecución Completa

### Prerrequisitos

1. AWS CLI configurado y permisos para crear recursos.
2. Dependencias instaladas:

```bash
uv sync --all-extras
```

### Despliegue de Infraestructura

```bash
aws cloudformation deploy \
  --template-file infra/core.yaml \
  --stack-name forecasting-stack \
  --parameter-overrides DBUser=<usuario> DBPassword=<password> \
  --capabilities CAPABILITY_NAMED_IAM
```


### Instalación del ambiente y ejecución por etapas

Clona el repositorio desde tu instancia EC2:

```bash
git clone https://github.com/AntonioEJ/data-product-forecasting-a.git
cd data-product-forecasting-a
# Exporta tus credenciales de Kaggle (reemplaza USER y KEY por tus valores)
export KAGGLE_USERNAME=USER
export KAGGLE_KEY=KEY

```
#### Ejecución con Docker (Pipeline por etapas)

Antes de construir y ejecutar el contenedor, instala las dependencias en tu entorno local (opcional pero recomendado para pruebas y desarrollo):

```bash
pip install uv
uv venv  # Crea el entorno virtual (recomendado)
uv sync
# Si prefieres instalar en el sistema global (no recomendado), usa:
# uv pip install -r pyproject.toml --system

# Ejecuta el pipeline ETL localmente (opcional)
uv run python -m etl.etl --raw-dir data/raw --prep-dir data/prep --artifacts-dir artifacts
```

Construye y ejecuta el contenedor para el pipeline ETL y procesamiento batch (desde la raíz del proyecto):

```bash
# ETL y Feature Engineering
docker build -t etl-pipeline:latest -f etl/Dockerfile .
docker run --rm \
       -v "$PWD/data:/app/data" \
       -v "$PWD/artifacts:/app/artifacts" \
       etl-pipeline:latest
```

Notas:
- El Dockerfile de ETL está en etl/Dockerfile y espera el contexto de build en la raíz del proyecto.
- El WORKDIR dentro del contenedor es /app y el PYTHONPATH está configurado como /app/etl.
- El ENTRYPOINT ejecuta el pipeline ETL (etl/etl.py) automáticamente.
- Si usas otros Dockerfile para etapas como entrenamiento o inferencia, repite el patrón cambiando la ruta y el ENTRYPOINT según corresponda.

Si implementas etapas adicionales (entrenamiento, inferencia), crea los Dockerfile correspondientes en las carpetas models/ o services/ y repite el patrón:

```bash
# Ejemplo para entrenamiento (si existe Dockerfile en models/)
docker build -t ml-training:latest -f models/Dockerfile .
docker run --rm \
       -v "$PWD/data:/app/data" \
       -v "$PWD/artifacts:/app/artifacts" \
       ml-training:latest
```

---

## 🧪 Validación de código

Para asegurar la calidad y el formato del código, puedes ejecutar:

```bash
# Linting general
ruff check .

# Validar formato
ruff format --check .

# Revisar docstrings
ruff check . --select D

# Ejecutar pruebas
pytest
```

> Nota: Tras crear el entorno virtual con `uv venv`, puedes activarlo manualmente con:
> - Linux/Mac: `source .venv/bin/activate`
> - Windows: `.venv\Scripts\activate`
> Esto es opcional, ya que uv lo maneja internamente, pero puede ser útil para algunos usuarios.

---

Para documentación técnica y diagramas, consulta la carpeta docs/
