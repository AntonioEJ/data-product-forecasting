# Esquema Relacional (ERD) — RDS PostgreSQL

## Descripción General
Modelo relacional normalizado para soportar las operaciones del producto de datos de pronóstico de ventas. Incluye productos, tiendas, predicciones, métricas, trabajos batch y feedback de negocio.

## Diagrama ERD (Mermaid)

```mermaid
erDiagram
    products ||--o{ predictions : "has"
    stores ||--o{ predictions : "has"
    predictions }o--|| metrics : "evaluated by"
    batch_jobs ||--o{ predictions : "exports"
    products ||--o{ feedback : "flagged in"
    stores ||--o{ feedback : "flagged in"
    feedback }o--|| users : "submitted by"

    products {
        int product_id PK
        string name
        string category
        ...
    }
    stores {
        int store_id PK
        string name
        string location
        ...
    }
    predictions {
        int prediction_id PK
        int product_id FK
        int store_id FK
        date forecast_date
        float predicted_value
        float actual_value (nullable)
        int batch_job_id FK (nullable)
        timestamp created_at
    }
    metrics {
        int metric_id PK
        int prediction_id FK
        string metric_name
        float metric_value
    }
    batch_jobs {
        int batch_job_id PK
        string status
        string export_scope
        string s3_url
        timestamp requested_at
        timestamp completed_at (nullable)
    }
    feedback {
        int feedback_id PK
        int product_id FK
        int store_id FK
        int user_id FK
        string comment
        string status
        timestamp submitted_at
    }
    users {
        int user_id PK
        string name
        string email
    }
```

## Notas de Modelado
- Todas las claves primarias (PK) son enteros autoincrementales.
- Las claves foráneas (FK) aseguran integridad referencial.
- Las tablas pueden extenderse con campos adicionales según necesidades del negocio.
- Los nombres y tipos de datos siguen convenciones claras y normalizadas.

---

Este modelo soporta consultas eficientes, integridad de datos y escalabilidad para futuras extensiones.