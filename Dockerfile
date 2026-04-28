# syntax=docker/dockerfile:1.4
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_NO_CACHE_DIR=on

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Set workdir
WORKDIR /app

# Copy pyproject.toml and lockfile
COPY pyproject.toml .
COPY uv.lock .

# Install uv and project dependencies with locked versions
RUN pip install --upgrade pip && pip install uv && uv sync --frozen --no-dev

# Copy the rest of the code
COPY . .

# Expose Streamlit port
EXPOSE 8501

# Streamlit config (headless, port)
ENV STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_SERVER_PORT=8501

# Entrypoint
CMD ["streamlit", "run", "app/main.py"]
