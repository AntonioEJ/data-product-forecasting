FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8
ENV PYTHONPATH=/app/etl

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock ./

RUN uv sync --frozen --no-dev

# Copia solo la carpeta etl

COPY etl ./etl

# Ejecuta el pipeline ETL
ENTRYPOINT ["uv", "run", "python", "-m", "etl.etl"]