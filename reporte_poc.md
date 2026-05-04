# Producto de Datos para Forecasting de Demanda en 1C Company

**Equipo:** Gustavo Pardo (Data & Modelo) · Antonio Espinosa (App & Infraestructura)
**Curso:** Arquitectura de Productos de Datos y Métodos de Gran Escala
**Fecha:** 3 de mayo de 2026
**Repositorio:** [github.com/AntonioEJ/data-product-forecasting](https://github.com/AntonioEJ/data-product-forecasting)
**App desplegada:** `forecast-app-alb-33822663.us-east-1.elb.amazonaws.com`

---

## 1. Resumen Ejecutivo

1C Company opera 60 tiendas con un catálogo de más de 22,000 productos repartidos en 84 categorías. El equipo de planeación toma cada mes la decisión de cuánto comprar de cada producto para cada tienda, y hoy lo hace con intuición y experiencia. Eso funciona, pero deja dinero sobre la mesa: hay sobreinventario en categorías de baja rotación y faltantes en productos que se mueven rápido.

Este proyecto entrega un producto de datos que pronostica las ventas mensuales del siguiente período por combinación tienda-producto, y deja al equipo de negocio una interfaz web para explorar los pronósticos, exportarlos y dar feedback cuando alguno no cuadra.

**Lo que conseguimos:**

- El modelo (LightGBM con features de retraso temporal) baja el error de predicción **74% respecto al baseline naive**: MAE de 0.30 vs 1.18 unidades por predicción.
- En **53 de 57 categorías evaluadas (93%)** el modelo le gana al baseline. Las 4 categorías donde no gana tienen volúmenes marginales — entre 1 y 25 observaciones, sin material para aprender.
- El sistema produce **8,675 pronósticos** para noviembre 2015 sobre el catálogo activo, accesibles desde la app vía exploración interactiva o exportación CSV.
- La infraestructura completa vive en AWS (PostgreSQL en RDS, Streamlit en ECS Fargate detrás de un ALB) y está versionada en CloudFormation.

**Lo que esto le da a 1C:** decisiones de compra con respaldo cuantitativo, granularidad por tienda y producto, y un canal estructurado para que el equipo de tienda reporte cuando un pronóstico no le cuadra — material directo para el siguiente ciclo de mejora del modelo.

---

## 2. Voz del Cliente

Antes de tocar código nos sentamos a entender quién iba a usar esto. Identificamos siete roles distintos en 1C que tendrían algo que ganar o perder con el producto. Cada uno tiene una pregunta concreta que necesita responder, y la app está diseñada alrededor de esas preguntas:

| Stakeholder | Lo que necesita | Dónde lo resuelve |
|---|---|---|
| VP de Planeación | "¿Cuántas unidades vamos a vender de cada categoría el mes que viene?" | Vista 1: Forecast Exploration |
| Director de Compras | "Necesito el catálogo entero en un Excel para mi análisis." | Vista 2: Batch Export |
| Chief Applied Scientist | "Demuéstrenme que el modelo agrega valor sobre lo que ya hacemos." | Vista 3: Model Evaluation |
| Gerente de Tienda | "Este producto siempre se vende más de lo que dicen ustedes — quiero reportarlo." | Vista 4: Business Feedback |
| Equipo de Datos | "Tengo que poder mantener y extender esto sin volverme loco." | Pipeline modular con tests, Docker, CFN |
| Equipo de TI | "La infra tiene que vivir en nuestra cuenta y poder operarla nosotros." | Stack completo en AWS, IaC |
| Auditoría | "Necesito saber qué predicción se generó cuándo y quién dijo qué del feedback." | Tablas con `created_at`, autor de feedback |

La estructura de cuatro vistas no fue arbitraria. Cada una resuelve un problema concreto de un usuario concreto. La alternativa habría sido hacer una vista monolítica que tratara de servirles a todos a la vez, y eso es justamente lo que produce los dashboards que nadie usa.

---

## 3. Arquitectura del Sistema

### 3.1 Vista de alto nivel

```
┌─────────────────────┐
│ Datos crudos (CSV)  │  Bronze: items.csv, shops.csv,
│ Kaggle Future Sales │  item_categories_en.csv, sales_train.csv
└──────────┬──────────┘
           ↓
┌─────────────────────┐
│ ETL en memoria      │  build_features: lags, rolling means
│ (etl/features.py)   │  make_modeling_dataset, temporal_split
└──────────┬──────────┘
           ↓
┌─────────────────────┐
│ Pipeline ML         │  training/ → modelo LightGBM
│ (offline, local)    │  evaluation/ → métricas por categoría
│                     │  inference/ → backtest + forecasts
└──────────┬──────────┘
           ↓ parquets
┌─────────────────────┐
│ Loaders idempotentes│  db/load_*.py: cargan parquets a RDS
│ (db/)               │  con DELETE+INSERT controlado
└──────────┬──────────┘
           ↓ INSERT
┌─────────────────────┐
│ PostgreSQL en RDS   │  6 tablas: products, shops,
│ (AWS)               │  predictions, metrics, feedback,
│                     │  batch_jobs
└──────────┬──────────┘
           ↑ SELECT/INSERT
┌─────────────────────┐
│ Streamlit App       │  4 vistas conectadas a RDS
│ (ECS Fargate + ALB) │  con cache @st.cache_data(ttl=300)
└─────────────────────┘
```

### 3.2 Las piezas que importan

**Pipeline de modelo (corre offline, en local).** Tres pasos independientes que se ejecutan como módulos de Python:

- `training/` entrena el LightGBM con early stopping. Con 200K filas tarda 25 segundos.
- `evaluation/` calcula métricas globales y por categoría sobre el set de validación temporal.
- `inference/` genera dos artefactos distintos: el backtest (47,324 predicciones del período de validación, con ground truth real) y el forecast (8,675 predicciones para noviembre 2015, sin ground truth porque es el futuro).

**Persistencia (RDS PostgreSQL 17.4).** Seis tablas con foreign keys explícitas. Una decisión que vale la pena destacar: las predicciones de backtest y de forecast viven en la misma tabla. Lo que las distingue es que `actual_units IS NULL` para el forecast (no hay ground truth todavía) y tiene valor para el backtest. Esto evitó duplicar schema y queries.

**Capa de aplicación (Streamlit).** Cuatro vistas independientes que comparten un solo helper de queries (`app/components/db_helpers.py`). Cada query está cacheada por 5 minutos para no golpear RDS en cada interacción del usuario — Streamlit re-ejecuta el script entero en cada click, así que sin cache estaríamos haciendo decenas de queries por minuto.

**Infraestructura (CloudFormation).** Un solo template (`infra/core.yaml`) que despliega VPC, subnets, RDS, ECR, ECS Fargate, ALB y Secrets Manager. El comando es uno y se puede correr cuantas veces quieras — es idempotente.

---

## 4. Decisiones de Diseño y Trade-offs

Cada decisión técnica del proyecto fue una elección entre opciones razonables. Aquí dejamos las cinco más importantes con su justificación honesta.

### 4.1 Pre-cómputo offline en lugar de inferencia en vivo

**La decisión:** las predicciones se generan offline en el pipeline de inference y se persisten en RDS. Streamlit solo lee.

**Por qué:** un modelo de forecasting mensual no necesita inferencia en tiempo real. El equipo de planeación toma decisiones una vez al mes, no una vez por minuto. Pre-computar evita latencia, simplifica la arquitectura (no hace falta endpoint SageMaker en producción), reduce costos y nos deja cachear sin remordimiento.

**Lo que sacrificamos:** las predicciones se actualizan solo cuando alguien re-ejecuta el pipeline. Para ciclos mensuales esto está bien; si el caso de uso fuera "necesito una predicción ahora mismo para este SKU específico" sería insuficiente. No es nuestro caso.

### 4.2 Una sola tabla de predicciones para backtest y forecast

**La decisión:** las predicciones del período de validación (con ground truth) y las del mes futuro (sin ground truth) viven en la misma tabla `predictions`, distinguidas por si `actual_units` es NULL o no.

**Por qué:** el modelo de datos es el mismo: `(shop, item, fecha) → predicción`. Separarlas en dos tablas duplicaba schema y queries sin razón.

**Lo que pide a cambio:** cuando alguien escribe una query nueva tiene que ser explícito sobre qué quiere — backtest, forecast o las dos. La vista 1 filtra por `IS NULL` (forecast), la vista 3 filtra por `IS NOT NULL` (backtest). Tuvimos un bug temprano donde las predicciones de forecast quedaron como `NaN` literal en lugar de NULL en PostgreSQL, lo cual rompía esa distinción. Lo encontramos y arreglamos antes del demo.

### 4.3 SQLAlchemy Core en lugar de ORM

**La decisión:** SQLAlchemy Core con `Table`, `Column` y `text()` con parámetros bindeables, no SQLAlchemy ORM con clases mapeadas.

**Por qué:** las queries del producto son agregaciones y joins explícitos, no operaciones sobre objetos complejos. Core es más cercano a SQL puro, más fácil de leer cuando lo abres tres meses después y sin sorpresas de carga lazy. El ORM agregaba complejidad sin pagarla en valor.

### 4.4 Features avanzadas en memoria, no en una capa Gold persistida

**La decisión:** los lags y rolling means (lag_2, lag_4, lag_8, roll_mean_4, roll_mean_8) se calculan en memoria al inicio del training. No los persistimos como una capa Gold separada.

**Por qué:** la arquitectura medallón Bronze/Silver/Gold dicta que las features completas deberían vivir en un parquet Gold listo para que el training solo lea. Lo correcto es hacerlo. Lo pragmático fue no hacerlo: el dataset de entrada (`monthly_with_lags.parquet`) ya trae el lag 1 precomputado del proyecto antecedente, y construir un Gold persistido a 48 horas del deadline implicaba migrar y re-validar lógica que no agregaba valor al MVP.

**Trade-off explícito:** esto queda como deuda técnica documentada. En producción se separa el cómputo de features en un step de ETL persistido, para que el training solo consuma Gold. Lo tenemos identificado, sabemos cómo hacerlo, no lo hicimos por tiempo.

### 4.5 Ownership distribuido pero pragmático

**Cómo nos repartimos el trabajo:** Antonio diseñó la infraestructura, los loaders y las vistas 1 y 2 de la app. Gustavo construyó el pipeline ML completo y las vistas 3 y 4. Algunas piezas que originalmente le tocaban a Antonio (`etl/features.py`, `config.py`, schema completo de feedback) las terminó haciendo Gustavo durante el desarrollo para no bloquearnos.

**Por qué importa:** el riesgo crítico del proyecto era el modelo. Si el LightGBM no le ganaba al naive, no había producto. Concentrar ese riesgo en una persona y dejar a la otra avanzar la infraestructura en paralelo redujo dependencias. Cuando llegó el momento de integrar (carga de datos a RDS, vistas con datos reales), las dos piezas encajaron porque desde el inicio acordamos los contratos de datos: nombres de tablas, columnas, formatos de parquet.

---

## 5. Evaluación del Modelo

### 5.1 Métricas globales

| Métrica | Modelo LightGBM | Baseline Naive (lag_1) | Mejora |
|---|---|---|---|
| MAE | **0.30** | 1.18 | 74% |
| RMSE | **0.72** | 2.16 | 67% |

**Cómo leerlo:** el modelo se equivoca en promedio por 0.30 unidades por predicción. El baseline naive (predecir el valor del mes anterior) se equivoca por 1.18 unidades. La mejora es sustancial — el negocio puede confiar en el modelo más que en una heurística trivial.

**Detalle que vale la pena entender:** el MAE es muy bajo (0.30) pero el RMSE es relativamente más alto (0.72). Esto pasa porque RMSE penaliza errores grandes más que errores pequeños. La diferencia entre los dos números nos dice que el modelo es muy preciso en la mayoría de los casos (productos que venden 0–2 unidades al mes) pero comete errores más grandes en algunos productos de alto volumen. Para el caso de uso de 1C esto es aceptable — la mayoría del catálogo es de baja rotación y ahí el modelo es excelente.

### 5.2 Métricas por categoría (top 10 por volumen)

| Categoría | Observaciones | MAE Modelo | MAE Naive | Modelo gana |
|---|---|---|---|---|
| Music - CD of local production | 7,846 | 0.0481 | 0.42 | ✓ |
| Games PC - Standard Edition | 6,060 | 0.2332 | 1.44 | ✓ |
| Movie - DVD | 5,705 | 0.0805 | 0.60 | ✓ |
| Games - XBOX 360 | 3,180 | 0.186 | 1.12 | ✓ |
| Games - PS3 | 3,150 | 0.171 | 1.17 | ✓ |
| Games - PS4 | 1,727 | 0.239 | 1.49 | ✓ |
| Movies - Blu-Ray | 1,588 | 0.071 | 0.66 | ✓ |
| Gifts - Games (compact) | 1,454 | 0.254 | 1.26 | ✓ |
| Gifts - Board Games | 1,301 | 0.093 | 0.73 | ✓ |
| Games PC - Additional publications | 1,089 | 0.176 | 1.23 | ✓ |

### 5.3 ¿Dónde sí falla el modelo?

Esta sección importa porque el demo del consejo va a preguntar exactamente esto, y si no la abordamos nosotros la van a sacar ellos.

**El número grande:** el modelo gana al naive en **53 de 57 categorías evaluadas (93%)**.

**Las 4 categorías donde no gana:**

- **"Delivery of goods"** — pierde por márgenes irrelevantes (MAE 138.78 vs naive 140.36). Pero esto no es un producto físico, es un cargo operativo. No es donde el negocio toma decisiones de compra.
- **"Payment cards - Live!"** — aquí sí pierde por margen real (MAE 24.4 vs naive 10.9). Son tarjetas de juego prepagadas con comportamiento altamente errático que el modelo no logra capturar con las features actuales.
- **Las otras dos categorías** — tienen 1 y 2 observaciones respectivamente. Estadísticamente irrelevantes, no hay material para aprender.

**El patrón:** las categorías donde el modelo pierde son todas de muy bajo volumen o de naturaleza operativa. En las categorías donde el negocio realmente toma decisiones de compra (todas con cientos o miles de observaciones), el modelo es consistentemente mejor que el baseline.

### 5.4 Fortalezas y limitaciones

**Lo que el modelo hace bien:**

- Entrena en 25 segundos con 200K observaciones. Esto significa que el equipo de datos puede iterar rápido y re-entrenar mensualmente sin problemas.
- Las predicciones están acotadas a no-negativas (clipping a min 0). No es posible vender unidades negativas, así que filtramos eso explícitamente.
- La validación es temporalmente honesta — el split por percentil 80% de fechas garantiza que no estamos prediciendo el pasado con información del futuro.

**Lo que sabemos que está limitado:**

- El forecast del mes siguiente solo cubre **8,675 combinaciones tienda-producto**: las que tuvieron actividad el mes anterior. Productos sin actividad reciente no reciben pronóstico. Es una limitación razonable pero acota el catálogo cubierto.
- El baseline que reportamos en evaluación (`monthly_units_lag_1`, el valor del mes anterior) es ligeramente distinto al baseline interno del training (último valor del train set). El de evaluación es más realista para producción y es el que usamos para todas las comparaciones públicas.
- No usamos features externas — calendario de festividades rusos, lanzamientos de productos, precios de la competencia. Hay margen claro de mejora ahí.

---

## 6. Pantallas del Producto

> _Las cuatro vistas operan con datos reales en `forecast-app-alb-33822663.us-east-1.elb.amazonaws.com`. Pendiente: incluir screenshots tras el redespliegue final del ECR._

**Vista 1 — Forecast Exploration.** Filtros por categoría y por tienda. Tres KPIs en la parte superior: unidades proyectadas para el siguiente período, unidades reales del último período, y cambio Year-over-Year. Una gráfica histórica con dos líneas (actual vs forecast). Una tabla expandible con el detalle del backtest mensual mostrando predicted vs actual.

**Vista 2 — Batch Export.** Una sola pantalla. Botón "Generate Export", confirmación con conteo de filas (55,999), y descarga directa del CSV. Diseñada para que el Director de Compras la use sin pensarla.

**Vista 3 — Model Evaluation.** Cuatro metric cards arriba con MAE y RMSE del modelo y del naive. Frase explícita debajo: "El modelo le gana al naive en 53 de 57 categorías." Tabla ordenable de las 57 categorías con sus métricas y volumen. Scatter chart de predicted vs actual con filtros por categoría y tienda.

**Vista 4 — Business Feedback.** Formulario con selectbox de las 60 tiendas reales, búsqueda de producto por item_id (con preview de nombre y categoría antes de enviar para evitar reportes accidentales), comentario libre y campo de autor. Tabla de issues reportados con filtro por status (open / reviewed / resolved). El feedback se persiste a RDS al instante.

---

## 7. Lo Que Se Quedó Fuera del MVP

Sostener un MVP entregable a 48 horas del deadline implicó dejar fuera deliberadamente cosas que sabemos que valen la pena. Las dejamos documentadas para que la siguiente versión las recoja:

**Capa Gold persistida.** Las features avanzadas se calculan en memoria. La versión correcta persiste un parquet Gold con todas las features y el training solo lee de ahí. La diferencia para el usuario final es nula; la diferencia para el equipo de datos en producción es grande.

**Estrategia para items inactivos.** Un item sin ventas en el mes anterior no recibe pronóstico. En producción se podría predecir 0 (con confianza alta cuando lleva muchos meses sin venderse) o usar la media de su categoría (cuando recién dejó de venderse).

**Re-entrenamiento automático.** Hoy alguien tiene que ejecutar `python -m training` manualmente. La versión madura es un job programado en Step Functions o EventBridge que dispare entrenamiento + evaluación + carga a RDS de manera mensual.

**Workflow de revisión del feedback.** La tabla `feedback` recibe inserciones pero no hay flujo para que un revisor cambie status `open → reviewed → resolved` desde la app. La estructura de datos lo soporta; falta la UI.

**Features externas.** Calendario de festividades rusos, lanzamientos de producto, precios de la competencia. Cada uno por separado tiene potencial de mejora medible.

**Versionado del modelo en RDS.** Cada carga de predicciones reemplaza la anterior. No hay tabla `model_versions` que permita comparar predicciones de modelos distintos en el mismo período. Cuando llegue el momento de hacer A/B testing de modelos, este será el primer cambio que toque hacer.

**Tests de integración end-to-end.** Tenemos tests unitarios por step (training, evaluation, inference, loaders, helpers de la app). No tenemos un test que ejecute el pipeline entero de extremo a extremo y valide que los conteos finales son los esperados. Para CI/CD esto es necesario.

Cada uno de estos puntos es un siguiente paso claro y dimensionable. Ninguno requiere semanas, varios se resuelven en días.

---

## 8. Despliegue

### 8.1 Cómo se desplegó el stack

Toda la infraestructura está en `infra/core.yaml` y se levanta con un solo comando:

```bash
aws cloudformation deploy \
  --template-file infra/core.yaml \
  --stack-name forecast-app \
  --capabilities CAPABILITY_NAMED_IAM \
  --region us-east-1 \
  --parameter-overrides \
    VpcId="$VPC_ID" \
    SubnetIds="$SUBNET_IDS" \
    ImageUri="<ECR-URI>:latest" \
    DBPassword="<masked>"
```

El template construye:

- VPC con dos subnets públicas en us-east-1
- Security groups acotados — RDS solo expuesto al ECS task, ALB expuesto a internet en el puerto 80
- RDS PostgreSQL 17.4 (db.t3.micro, 20 GB) con la password gestionada en Secrets Manager
- ECR repository para la imagen Docker de la app
- ECS Fargate cluster + service corriendo Streamlit en el puerto 8501
- Application Load Balancer distribuyendo tráfico al ECS service
- CloudWatch log groups para logs de la app y de los tasks

### 8.2 Cómo se actualiza el código

Cuando hay cambios (por ejemplo, las vistas 3 y 4 nuevas):

1. Build local de la imagen con `docker build`
2. Tag y push a ECR
3. `aws ecs update-service --force-new-deployment` para que ECS reemplace los tasks viejos por los nuevos
4. ECS hace rolling deployment sin downtime — los usuarios no se enteran

### 8.3 Carga inicial de datos

Después de levantar el stack, el flujo para poblar la base es directo:

```bash
# Configurar credenciales en variables de entorno (no en archivos del repo):
export RDS_HOST=forecast-app-db.<id>.us-east-1.rds.amazonaws.com
export RDS_PORT=5432
export RDS_DBNAME=forecasting
export RDS_USER=postgres
export RDS_PASSWORD=<de Secrets Manager>

# Pipeline completo:
uv run python -m training       # entrena modelo (25 s)
uv run python -m evaluation     # genera métricas (5 s)
uv run python -m inference      # genera predicciones (10 s)
uv run python -m db             # carga a RDS (7 s)
```

Tiempo total para tener todo listo desde cero: aproximadamente 2 minutos.

---

## 9. Conclusiones

El producto funciona y entrega valor concreto: pronósticos accionables con respaldo cuantitativo, una interfaz que cuatro tipos de usuarios pueden usar para sus problemas distintos, y una arquitectura que el equipo de TI de 1C puede operar y extender sin nuestra presencia.

Las decisiones técnicas — pre-cómputo offline, una sola tabla de predicciones, SQLAlchemy Core, features en memoria — fueron pragmáticas y conscientes. Cada vez que sacrificamos elegancia arquitectónica fue por velocidad de entrega del MVP, y cada sacrificio queda escrito como deuda técnica con su solución dimensionada. No estamos pretendiendo que el sistema sea perfecto; estamos siendo claros sobre qué hicimos bien y qué dejamos para después.

El modelo le gana al baseline en el 93% de las categorías. Más importante todavía: gana en las categorías donde el negocio realmente toma decisiones, y solo "pierde" en categorías marginales donde tampoco sería razonable esperar buenos pronósticos.

Para la siguiente versión el camino es claro: implementar la capa Gold persistida, agregar features externas (festividades, lanzamientos), e instaurar un job programado de re-entrenamiento. Cada uno se mide en días, no en semanas. El producto está listo para entrar a uso real y para crecer desde ahí.

---

## Anexo A — Estructura del repositorio

```
data-product-forecasting/
├── etl/                # ETL: bronze, silver, features
├── training/           # Pipeline de entrenamiento
├── evaluation/         # Métricas globales y por categoría
├── inference/          # Generación de predicciones
├── db/                 # Schema y loaders a RDS
├── data/               # rds.py: capa de conexión SQLAlchemy
├── app/                # Streamlit: main, pages, components
├── infra/              # CloudFormation templates
├── artifacts/          # Modelos y predicciones (gitignored)
├── config.py           # Configuración centralizada
├── pyproject.toml      # uv + dependencias
└── Dockerfile          # Imagen para ECS Fargate
```

## Anexo B — Comandos de verificación

```bash
# Verificar conectividad a RDS
uv run python scripts/check_rds.py

# Ejecutar todos los tests
uv run pytest -v

# Levantar la app local (requiere env vars de RDS)
uv run streamlit run app/main.py

# Validar conteos en RDS
uv run python -c "
from sqlalchemy import text
from data.rds import _get_engine
with _get_engine().connect() as c:
    print('Predicciones:', c.execute(text('SELECT COUNT(*) FROM predictions')).scalar())
    print('Métricas:', c.execute(text('SELECT COUNT(*) FROM metrics')).scalar())
    print('Productos:', c.execute(text('SELECT COUNT(*) FROM products')).scalar())
    print('Tiendas:', c.execute(text('SELECT COUNT(*) FROM shops')).scalar())
"
```
