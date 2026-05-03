# Forecast Demand — Data Product POC

**Autores:** José Antonio Esparza · Gustavo Pardo  
**Repositorio:** https://github.com/AntonioEJ/data-product-forecasting  
**App en producción:** http://forecast-app-alb-33822663.us-east-1.elb.amazonaws.com

---

## 1. El problema de negocio

Las áreas de Finanzas y Planeación de una empresa de retail con 60 tiendas y más de 22,000 productos toman decisiones de inventario y compra con visibilidad limitada de la demanda futura. El resultado habitual: sobrestock en productos lentos, quiebre de stock en temporadas clave y pronósticos hechos a mano en Excel que no escalan.

Este proyecto construye un **producto de datos de pronóstico de demanda** que transforma ~2.9 millones de registros históricos de ventas en predicciones mensuales accionables, accesibles para cualquier usuario de negocio a través de una aplicación web sin necesidad de conocimientos técnicos.

**¿Qué valor genera?**

- Los equipos de Finanzas pueden ver la proyección de la próxima temporada por tienda o categoría en segundos.
- Planeación puede exportar un CSV de predicciones filtradas directamente desde el browser, sin depender de un analista.
- El negocio puede reportar discrepancias entre el pronóstico y la realidad, cerrando el ciclo de mejora continua.
- El equipo técnico puede monitorear la calidad del modelo (MAE, RMSE) y compararlo contra un baseline naive, todo desde la misma interfaz.

---

## 2. URLs clave

| Recurso | URL |
|---|---|
| Repositorio GitHub | https://github.com/AntonioEJ/data-product-forecasting |
| App en producción (AWS) | http://forecast-app-alb-33822663.us-east-1.elb.amazonaws.com |

---

## 3. Arquitectura de la solución

El sistema está diseñado como una arquitectura de datos por capas, donde cada componente tiene una responsabilidad clara y puede evolucionar de forma independiente.

```
Kaggle (fuente de datos históricos)
       │
       ▼
  S3 — Data Lake (raw)
       │
       ▼
  ETL con arquitectura Medallion
  ├── Bronze: CSV → Parquet en S3
  ├── Silver: datos limpios y normalizados
  └── Gold:  tabla analítica vía Athena
       │
       ▼
  Feature Engineering → LightGBM
       │
       ▼
  RDS PostgreSQL (predicciones precomputadas)
       │
       ▼
  Streamlit en ECS Fargate (app web para el negocio)
```

La decisión más importante de diseño es que **las predicciones se calculan en batch y se persisten en RDS**, no en tiempo real. Esto mantiene la app rápida y predecible para el usuario, desacopla el pipeline de ML del frontend, y permite escalar ambos de forma independiente.

### Servicios AWS utilizados

| Servicio | Rol en el sistema | Por qué este servicio |
|---|---|---|
| **S3** | Data lake: almacena raw, bronze, silver y gold | Bajo costo, durabilidad 99.999999999%, integración nativa con Glue y Athena |
| **Glue Data Catalog** | Registro y descubrimiento de datasets en S3 | Permite que Athena y otros servicios encuentren los datos sin configuración manual |
| **Athena** | Construye la capa Gold mediante CTAS | SQL serverless sobre S3 — sin clústeres, sin gestión, pago por query |
| **RDS PostgreSQL 17** | Almacena predicciones, métricas y feedback | Consultas SQL relacionales con baja latencia; soporte a transacciones para feedback |
| **ECS Fargate** | Ejecuta la app Streamlit en contenedor | Serverless: sin gestión de servidores, escalado automático, pago por uso |
| **ECR** | Registro de imágenes Docker | Control de versiones de imágenes, integrado con ECS y IAM |
| **CloudFormation** | Infraestructura como código | Stack completo reproducible: RDS + ECS + ALB + Secrets Manager en un solo comando |
| **Secrets Manager** | Gestión de credenciales de RDS | Las contraseñas nunca están en código ni en variables de entorno hardcodeadas en producción |
| **ALB** | Balanceador de carga para la app | Punto de entrada HTTP público con health checks; permite zero-downtime deploys |
| **CloudWatch** | Logs de la app y del contenedor | Centralización de logs sin infraestructura adicional |

> **Diagrama de arquitectura:** ver `docs/arquitectura.md` o exportar el archivo `.drawio` en `docs/`.

![Arquitectura](docs/screenshots/arquitectura.png)

---

## 4. Flujo end-to-end del sistema

### Paso 1 — Ingesta de datos
Los datos históricos de ventas provienen del dataset público [Predict Future Sales](https://www.kaggle.com/c/competitive-data-science-predict-future-sales) de Kaggle (~2.9M registros). Se descargan con la API oficial de Kaggle y se almacenan en `data/raw/`. Los archivos no se versionan en Git.

### Paso 2 — ETL con arquitectura Medallion
El pipeline ETL (`etl/`) transforma los datos en tres capas:

- **Bronze**: los CSV originales se convierten a Parquet y se suben a S3. Se registran en Glue Data Catalog. Sin transformaciones — reflejo fiel del dato crudo.
- **Silver**: los datos limpios y normalizados (`data/prep/`) se suben a S3 en formato Parquet. Incluye corrección de tipos, manejo de nulos y traducción de catálogos al inglés.
- **Gold**: una consulta CTAS en Athena genera la tabla analítica consolidada `forecasting_gold.ventas_analitica`, que combina ventas, productos y tiendas en una sola vista optimizada para ML.

### Paso 3 — Feature Engineering
El script `etl/features.py` genera lags mensuales y medias móviles sobre la tabla Gold. El resultado es `data/prep/monthly_with_lags.csv`, el dataset de entrenamiento del modelo.

### Paso 4 — Modelo y predicciones
El componente de modelado (desarrollado por otro miembro del equipo) entrena un modelo **LightGBM** con los features generados y produce predicciones batch por tienda, producto y mes. Las predicciones se cargan en RDS con el script `db/load_predictions.py`.

### Paso 5 — Persistencia y exposición
Las predicciones, métricas del modelo y datos de catálogo quedan almacenados en RDS PostgreSQL, donde la app Streamlit los consulta en tiempo real mediante queries parametrizadas.

### Paso 6 — Consumo en la app
La app Streamlit (desplegada en ECS Fargate) expone los resultados a usuarios de negocio. Todas las queries pasan por `data/rds.py`, que gestiona el connection pooling y los parámetros de seguridad.

---

## 5. Modelo de datos (RDS)

La base de datos `forecasting` en RDS PostgreSQL almacena todo lo que la aplicación necesita para operar: predicciones, métricas del modelo, catálogos de referencia, historial de exportaciones y retroalimentación del negocio.

### Tablas principales

| Tabla | Propósito | Escribe | Lee |
|---|---|---|---|
| `predictions` | Pronósticos por tienda, producto y mes. Incluye el valor real cuando ya ocurrió. | Pipeline de ML (`db/load_predictions.py`) | App Streamlit (todas las vistas) |
| `metrics` | MAE, RMSE y comparación vs baseline naive por categoría de producto. | Pipeline de evaluación (`db/load_metrics.py`) | Vista de Evaluación del Modelo |
| `products` | Catálogo de productos con nombre y categoría. | Script de carga (`db/load_all.py`) | App Streamlit (filtros y joins) |
| `shops` | Catálogo de tiendas con nombre y ciudad. | Script de carga (`db/load_all.py`) | App Streamlit (filtros y joins) |
| `batch_jobs` | Registro de exportaciones CSV solicitadas desde la app. | App Streamlit (batch export) | App Streamlit (historial) |
| `feedback` | Comentarios del negocio sobre pronósticos específicos. | App Streamlit (usuarios de negocio) | App Streamlit (vista de feedback) |

> **Diagrama ERD:** ver `docs/erd.md`.

![ERD](docs/screenshots/erd.png)

La clave de diseño es que `predictions` vincula tiendas, productos y fechas en una sola tabla. Cuando `actual_units IS NULL`, el registro es un pronóstico futuro. Cuando tiene valor, es un dato histórico que permite calcular el error del modelo.

---

## 6. Aplicación Streamlit

La app es el punto de contacto entre los datos y el negocio. Está desplegada públicamente en http://forecast-app-alb-33822663.us-east-1.elb.amazonaws.com y tiene cuatro secciones:

### Exploración de Pronósticos
El usuario puede filtrar por **tienda** o **categoría** y ver dos vistas:
- El histórico de predicciones vs ventas reales (para evaluar confianza en el modelo)
- La proyección de la próxima temporada

Esto responde directamente a la pregunta del negocio: *"¿Cuánto se va a vender el próximo mes en mi tienda?"*

### Exportación Masiva
Permite descargar un CSV de pronósticos filtrado por tienda, categoría o catálogo completo, directamente desde el browser. Diseñado para Finanzas: sin acceso a SQL, sin depender del equipo técnico.

### Evaluación del Modelo
Muestra el MAE y RMSE ponderados a nivel global y por categoría, comparados contra un baseline naive. Incluye un scatter chart de predicho vs real para validación visual. El filtro por categoría y tienda permite al equipo técnico auditar el comportamiento del modelo en segmentos específicos.

### Retroalimentación del Negocio
Los usuarios pueden reportar problemas con pronósticos específicos (búsqueda por item_id, tienda y comentario libre). El historial de reportes puede filtrarse por estado: abierto, revisado o resuelto. Cierra el ciclo entre el modelo y el negocio.

### Screenshots de la aplicación

**Exploración de Pronósticos — filtro por tienda:**
![Exploración por tienda](docs/screenshots/app_forecast_tienda.png)

**Exploración de Pronósticos — proyección próxima temporada:**
![Próxima temporada](docs/screenshots/app_forecast_temporada.png)

**Exportación Masiva:**
![Exportación batch](docs/screenshots/app_batch_export.png)

**Evaluación del Modelo — métricas globales y por categoría:**
![Evaluación modelo](docs/screenshots/app_model_evaluation.png)

**Retroalimentación del Negocio:**
![Feedback negocio](docs/screenshots/app_business_feedback.png)

---

## 7. Despliegue

La infraestructura completa se despliega con un solo comando de CloudFormation desde AWS CloudShell.

### Stack de infraestructura (`infra/core.yaml`)
- RDS PostgreSQL 17 (db.t3.micro, almacenamiento encriptado)
- ECS Fargate cluster + service + task definition
- ALB internet-facing con health check en `/_stcore/health`
- Secrets Manager con las credenciales de RDS
- IAM roles con principio de mínimo privilegio (acceso a secrets scoped por ARN)
- CloudWatch log group

### Pipeline de deploy

```
Código (GitHub)
      │
      ▼
Docker build (SageMaker)
      │
      ▼
ECR (imagen versionada)
      │
      ▼
ECS Fargate (nuevo deployment)
      │
      ▼
ALB → app pública
```

**Build y push de imagen** (desde SageMaker):
```bash
ECR_URI=529236942598.dkr.ecr.us-east-1.amazonaws.com/forecast-app-ecr
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin $ECR_URI
docker build --network sagemaker -t "${ECR_URI}:latest" .
docker push "${ECR_URI}:latest"
```

**Force re-deploy** (desde CloudShell):
```bash
aws ecs update-service \
    --cluster forecast-app-cluster \
    --service forecast-app \
    --force-new-deployment \
    --region us-east-1
```

### Credenciales

En producción (ECS), la app obtiene las credenciales de RDS automáticamente desde Secrets Manager. En local, se usan variables de entorno. El código en `data/rds.py` resuelve ambos casos sin configuración adicional.

### Screenshots de AWS

**ECS Fargate — servicio corriendo:**
![ECS servicio](docs/screenshots/aws_ecs_service.png)

**CloudFormation — stack en CREATE_COMPLETE:**
![CloudFormation stack](docs/screenshots/aws_cloudformation.png)

**ECR — imagen publicada:**
![ECR imagen](docs/screenshots/aws_ecr.png)

**RDS — instancia disponible:**
![RDS disponible](docs/screenshots/aws_rds.png)

**App pública en el browser:**
![App en producción](docs/screenshots/app_produccion_browser.png)

---

## 8. Operación

### Logs
Todos los logs de la app (queries, errores, feedback registrado) van a **CloudWatch Logs** bajo el grupo `/ecs/forecast-app`. El logging usa un formato estructurado con timestamps y contexto, compatible con filtros y alarmas de CloudWatch.

### Manejo de fallas
La app maneja errores de conectividad a RDS de forma explícita: cada vista muestra un mensaje de error descriptivo en lugar de fallar silenciosamente. El ALB tiene health checks cada 30 segundos y reemplaza automáticamente tareas no saludables.

### Disponibilidad
ECS Fargate mantiene la tarea en ejecución continua. Si el contenedor falla, ECS lo reemplaza automáticamente. El ALB gestiona el zero-downtime durante re-deploys gracias al rolling deployment configurado en la task definition.

---

## 9. Costos estimados (us-east-1)

| Servicio | Estimado mensual |
|---|---|
| RDS db.t3.micro (PostgreSQL) | ~$15 USD |
| ECS Fargate (0.25 vCPU / 0.5 GB, 24/7) | ~$10 USD |
| ALB | ~$18 USD |
| S3 (< 5 GB) | < $1 USD |
| Secrets Manager (1 secreto) | < $1 USD |
| CloudWatch Logs | < $1 USD |
| **Total estimado** | **~$45 USD/mes** |

Para un POC o entorno de desarrollo, el costo puede reducirse apagando RDS e ECS fuera de horario (~70% de ahorro). Para producción real, el costo escala principalmente con el tamaño de RDS y la carga en Fargate.

---

## 10. Limitaciones y próximos pasos

### Limitaciones actuales (POC)

- **Datos estáticos**: las predicciones se generaron en batch una sola vez. No hay pipeline programado para actualizar pronósticos automáticamente.
- **Sin autenticación**: la app es pública. Un entorno de producción requiere integración con un Identity Provider (Cognito, Okta).
- **Un solo ambiente**: no hay separación dev/staging/prod. Todo corre en un solo stack de CloudFormation.
- **Modelo no versionado**: LightGBM se entrena una vez. No hay tracking de experimentos ni A/B testing de modelos.
- **Sin alertas operativas**: CloudWatch tiene los logs, pero no hay alarmas configuradas para MAE fuera de umbral o errores de app.

### Para escalar a producción

1. **Orquestar el pipeline** con Apache Airflow o AWS Step Functions para re-entrenar y re-predecir mensualmente.
2. **Versionar modelos** con MLflow o SageMaker Model Registry.
3. **Agregar autenticación** con Amazon Cognito o integración SSO.
4. **Separar ambientes** (dev/prod) con stacks de CloudFormation independientes.
5. **Configurar alarmas** en CloudWatch para degradación del modelo y errores de app.

---

## 11. Uso de Herramientas de IA en el Proyecto

Como requisito de transparencia académica, el equipo declara el siguiente uso de herramientas de inteligencia artificial:

**Herramienta utilizada:** GitHub Copilot (Claude Sonnet) — asistente integrado en VS Code.

**Para qué se utilizó:**

| Área | Uso específico |
|---|---|
| Consultas técnicas | Resolver dudas sobre APIs de SQLAlchemy, psycopg v3, Streamlit y boto3 |
| Revisión de sintaxis | Identificar errores de sintaxis y sugerencias de corrección en Python |
| Documentación | Apoyo en redacción de docstrings y secciones del README |
| Comandos de AWS CLI | Consultar la sintaxis correcta de comandos `aws ecs`, `aws ecr`, `aws cloudformation` |
| Debugging | Orientación para interpretar stack traces y mensajes de error |

**Lo que NO fue generado por IA:** el diseño de la arquitectura, las decisiones de modelado, la estructura del repositorio, el esquema de la base de datos, el pipeline ETL, la lógica de las vistas de Streamlit, el stack de CloudFormation y los tests unitarios son producto del trabajo original del equipo.

El código, los diagramas y la explicación del diseño fueron desarrollados, revisados y validados por los autores. Las herramientas de IA se usaron como apoyo puntual equivalente al uso de documentación oficial o Stack Overflow.

---

## Reporte del POC

El documento `docs/reporte.md` contiene el reporte autocontenido del sistema: descripción del problema, arquitectura, modelo de datos, evaluación del modelo, tour de la app y consideraciones de costo. Es el artefacto de revisión independiente del README.

---

## Documentación adicional

- Decisiones de arquitectura: `docs/arquitectura.md`
- Modelo de datos (ERD): `docs/erd.md`
- Diagrama de arquitectura (editable): `docs/arquitectura.drawio`
- Diagrama ERD (editable): `docs/erd.drawio`
- Documentación de módulos Python: `docs/api/`
