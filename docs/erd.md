# Esquema Relacional (ERD) — RDS PostgreSQL

## Descripción general

Modelo relacional para el producto de forecasting de demanda. Seis tablas implementadas en `db/schema.py`.

## Diagrama ERD (Mermaid)

```mermaid
erDiagram
    products ||--o{ predictions : "item_id"
    shops ||--o{ predictions : "shop_id"
    batch_jobs ||--o{ predictions : "batch_job_id"
    products ||--o{ feedback : "item_id"
    shops ||--o{ feedback : "shop_id"

    products {
        int item_id PK
        string(500) item_name
        string(200) category_name
    }
    shops {
        int shop_id PK
        string(500) shop_name
        string(200) city
    }
    predictions {
        int id PK
        int shop_id FK
        int item_id FK
        date forecast_date
        float predicted_units
        float actual_units
        datetime created_at
        int batch_job_id FK
    }
    metrics {
        int id PK
        string(200) category_name
        float mae
        float rmse
        float mae_naive
        float rmse_naive
        datetime computed_at
    }
    batch_jobs {
        int id PK
        string(100) filter_type
        string(500) filter_value
        string(1000) s3_url
        string(50) status
        datetime created_at
    }
    feedback {
        int id PK
        int shop_id FK
        int item_id FK
        text comment
        string(20) status
        string(100) reported_by
        datetime created_at
    }
```

## Notas

- `metrics` agrega errores por `category_name`, no por predicción individual. El campo `computed_at` permite rastrear cuándo se calculó cada snapshot de métricas.
- `batch_jobs` registra solicitudes de exportación desde la vista 2. `filter_type` y `filter_value` indican el alcance (categoría, tienda, catálogo completo).
- `actual_units` en `predictions` es nullable: se rellena cuando llega el ground truth.
- `created_at` en `predictions` permite auditoría temporal de cuándo se generó cada pronóstico.
- `batch_job_id` (nullable) liga predicciones al export que las generó, para trazabilidad desde la vista 2.
- `feedback` persiste comentarios de la vista 4 con flujo open/reviewed/resolved (`status`).
- PKs autoincrementales salvo `item_id` y `shop_id`, que se preservan del dataset original de Kaggle.