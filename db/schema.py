"""Schema de RDS: tablas del producto de forecasting."""

from __future__ import annotations

from sqlalchemy import Column, Date, DateTime, Float, Integer, MetaData, String, Table

metadata = MetaData()

products = Table(
    "products",
    metadata,
    Column("item_id", Integer, primary_key=True),
    Column("item_name", String(500), nullable=False),
    Column("category_name", String(200), nullable=False),
)

shops = Table(
    "shops",
    metadata,
    Column("shop_id", Integer, primary_key=True),
    Column("shop_name", String(500), nullable=False),
    Column("city", String(200), nullable=True),
)

predictions = Table(
    "predictions",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("shop_id", Integer, nullable=False),
    Column("item_id", Integer, nullable=False),
    Column("forecast_date", Date, nullable=False),
    Column("predicted_units", Float, nullable=False),
    Column("actual_units", Float, nullable=True),
)

metrics = Table(
    "metrics",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("category_name", String(200), nullable=False),
    Column("mae", Float, nullable=False),
    Column("rmse", Float, nullable=False),
    Column("mae_naive", Float, nullable=False),
    Column("rmse_naive", Float, nullable=False),
    Column("computed_at", DateTime, nullable=False),
)

batch_jobs = Table(
    "batch_jobs",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("filter_type", String(100), nullable=True),
    Column("filter_value", String(500), nullable=True),
    Column("s3_url", String(1000), nullable=True),
    Column("status", String(50), nullable=False),
    Column("created_at", DateTime, nullable=False),
)
