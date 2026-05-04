# Arquitectura y Decisiones Clave

## Justificación de Arquitectura

### 1. Precomputed Predictions (Batch)
- **Ventaja:** Consultas interactivas son rápidas y predecibles, ya que la app solo lee de RDS.
- **Trade-off:** Menor flexibilidad para escenarios de inferencia en tiempo real, pero mayor control de costos y robustez operativa.
- **Escalabilidad:** El pipeline de predicción puede escalar de forma independiente a la app.

### 2. Separación de Capas
- **ETL y ML desacoplados:** Permite evolucionar el pipeline sin afectar la experiencia del usuario.
- **App desacoplada de la lógica de negocio y acceso a datos:** Facilita pruebas, mantenibilidad y escalabilidad.

### 3. AWS como plataforma
- **S3:** Data lake central, bajo costo, integración nativa con Glue y ETL.
- **Glue Data Catalog:** Descubrimiento y gobierno de datos.
- **RDS:** Consultas SQL eficientes, integridad relacional, soporte para transacciones y feedback.
- **ECS Fargate:** Despliegue serverless, escalado automático, sin gestión de servidores.
- **ECR:** Control de versiones y despliegue seguro de imágenes Docker.
- **CloudFormation:** Infraestructura reproducible, auditable y versionada.
- **Secrets Manager:** Seguridad y cumplimiento para credenciales.

### 4. Logging y Observabilidad
- **Logging estructurado:** Compatible con CloudWatch, facilita monitoreo y troubleshooting.
- **Métricas y feedback:** Permiten mejorar el producto y la operación.

### 5. Seguridad y Operación
- **Principio de mínimo privilegio:** Acceso restringido por rol IAM.
- **Secrets fuera del código:** Cumplimiento y mejores prácticas.

## Diagrama de Arquitectura

![Diagrama de arquitectura](screenshots/arquitectura.drawio.png)

```mermaid
graph TD
    A[CSV Kaggle\nDatos crudos] --> B[ETL\netl/bronze.py · silver.py · features.py]
    B --> C[Pipeline ML offline\ntraining · evaluation · inference]
    C --> D[Artefactos parquet\npredicciones + métricas]
    D --> E[DB Loaders idempotentes\ndb/load_*.py]
    E --> F[RDS PostgreSQL 17\n6 tablas]
    F --> G[Streamlit App\nECS Fargate + ALB]
    G --> H[VP Planeación\nDirector Compras\nGerente Tienda\nCientífico de Datos]
    G --> I[Feedback]
    I --> F
    J[AWS Secrets Manager] -.credenciales.-> G
    K[ECR] -.imagen Docker.-> G
    L[CloudFormation\ninfra/core.yaml] -.despliega.-> G
    L -.despliega.-> F
    M[CloudWatch] -.logs.-> G
```

---

Este diseño prioriza la usabilidad, confiabilidad, escalabilidad y mantenibilidad, siguiendo estándares de la industria y prácticas AWS recomendadas.