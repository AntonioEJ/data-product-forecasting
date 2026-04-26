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

## Diagrama de Arquitectura (para draw.io)

```mermaid
graph TD
    A[S3 Raw Data] --> B[ETL/Glue]
    B --> C[S3 Processed Data]
    C --> D[ML Pipeline (SageMaker/ETL)]
    D --> E[Predictions (Batch)]
    E --> F[RDS PostgreSQL]
    F --> G[Streamlit App (ECS Fargate)]
    G --> H[Business User]
    G --> I[S3 Exported CSV (Batch)]
    I --> J[Signed URL]
    G --> K[Feedback]
    K --> F
```

---

Este diseño prioriza la usabilidad, confiabilidad, escalabilidad y mantenibilidad, siguiendo estándares de la industria y prácticas AWS recomendadas.