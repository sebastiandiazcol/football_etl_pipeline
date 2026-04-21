# Football Data Analytics & Betting ETL Pipeline

Motor de procesamiento de datos de fútbol de alto rendimiento diseñado para la extracción masiva, transformación analítica y modelado estadístico. Construido bajo la **Arquitectura Medallion** (Bronze, Silver, Gold), este pipeline transforma datos JSON crudos de proveedores deportivos (ej. 365Scores) en un Esquema Estrella optimizado para Business Intelligence (Power BI) y Ciencia de Datos (Python).

## 📋 Arquitectura del Proyecto

El proyecto divide estrictamente el procesamiento de datos en capas progresivas de calidad:

1. **Capa BRONZE (`01_bronze.db`):** Almacenamiento inmutable de la data cruda (JSON) extraída de la API. Garantiza que nunca se pierda el dato original.
2. **Capa SILVER (`02_silver.db`):** Base de datos relacional de áreas temáticas. Limpia inconsistencias y organiza métricas puras por jugador y equipo antes de agregaciones complejas.
3. **Capa GOLD (`03_gold.db`):** Data Warehouse modelado en Esquema Relacional de Estrella (Star Schema). Lleno de ingeniería de variables (xG, promedios móviles, historial) listo para ser consumido por analistas.

## 📂 Estructura del Repositorio

```text
football_etl_pipeline/
│
├── db/
│   ├── database.py               # Motores SQLAlchemy y configuracion de sesiones
│   └── models/
│       ├── bronze_models.py      # Esquema inmutable JSON
│       ├── silver_models.py      # Tablas relacionales intermedias
│       └── gold_models.py        # Esquema Estrella final con ingeniería de variables
│
├── transform/
│   ├── bronze_to_silver.py       # ETL: Desanidado JSON y limpieza
│   ├── silver_to_gold.py         # ETL: Carga de Hechos, Upserts de Dimensiones y Promedios Moviles
│   └── sqlite_to_sqlserver.py    # Integración y migración fluida hacia SQL Server (Docker)
│
├── tools/
│   └── prepare_match.py          # Asistente CLI principal para extracción manual
│
├── data/                         # Bases de datos SQLite (Generadas automáticamente)
│   ├── 01_bronze.db
│   ├── 02_silver.db
│   └── 03_gold.db
│
├── main.py                       # Orquestador del pipeline completo
├── README.md
└── DATA_DICTIONARY.md            # Diccionario semántico de tablas en Gold
```

## 🚀 Requisitos e Instalación

Este proyecto utiliza `uv` como gestor de paquetes de alto rendimiento.

1. Clonar el repositorio.
2. Instalar las dependencias en el entorno virtual:

```powershell
uv pip install sqlalchemy requests pandas pyodbc
```

## ⚙️ Uso del Pipeline ETL (CLI)

La forma principal y más sencilla de interactuar con el pipeline es a través del **Preparador de Partidos** (`tools/prepare_match.py`), un asistente interactivo que te permite buscar equipos por nombre (conectándose a la API para encontrar su ID), para luego descargar y procesar automáticamente sus partidos.

```powershell
uv run python tools/prepare_match.py
```

El script te guiará paso a paso:
1. Buscará a tu equipo.
2. Determinará sus últimos partidos.
3. Disparará la descarga (Bronze).
4. Modelará el relacional (Silver).
5. Calculará Promedios Móviles y Mapeos Avanzados (Gold).
6. Volcará automáticamente todo hacia una instancia de Microsoft SQL Server utilizando integración nativa ODBC.

*(Alternativamente, puedes usar tu instalación global de Python ejecutando `python tools/prepare_match.py`).*

## 📊 Modelo de Datos y Apuestas Deportivas (Capa GOLD)

El core del sistema. Además de extraer, el proceso `silver_to_gold` enriquece la base de datos transformándola en un poderoso motor analítico de apuestas.

**Dimensiones:**
* `dim_team`, `dim_player`, `dim_competition`, `dim_referee` (Con actualización inteligente UPSERT).
* `dim_date`: Dimensión calendario generada automáticamente entre 2020 y 2030.

**Hechos (Bases Desnormalizadas listas para BI):**
* `fact_team_match`: Todas las estadísticas a nivel equipo (puntos en juego, tiros, goles por tiempo). Identifica banderas de `BTTS` (Ambos Marcan), `Over 2.5` y calcula promedios móviles automáticos (rendimiento del equipo en sus últimos 3 o 5 juegos). 
* `fact_player_match`: Rendimiento atómico del jugador (Player Props). Faltas, tarjetas, precisión en pases, y su propio historial móvil (`roll3` y `roll5`) de tiros para predecir si un jugador disparará al arco en el próximo encuentro.

*(Para revisar cada columna específica, consulta [DATA_DICTIONARY.md](DATA_DICTIONARY.md)).*

## 📈 Integracion con Power BI (SQL Server Local/Docker)

Para evitar las limitaciones y bloqueos comunes de SQLite, el pipeline integra un volcador masivo hacia **Microsoft SQL Server**.

### 1. Levantar contenedor Docker
```powershell
docker run -e "ACCEPT_EULA=Y" -e "MSSQL_SA_PASSWORD=SuperSecret123!" -p 1433:1433 -d --name sql_futbol mcr.microsoft.com/mssql/server:2022-latest
```

### 2. Sincronización Transparente
No debes hacer nada. Tras cada ejecución interactiva, el script lee `03_gold.db` y envía un `UPSERT` masivo de nuevas filas hacia `localhost:1433`.

### 3. Conexión desde Power BI
Haz clic en "Obtener Datos -> SQL Server":
* **Servidor**: `localhost`
* **Base de Datos**: `FootballGold`
* Usuario: `sa` / Contraseña: `SuperSecret123!`

Disfruta de análisis instantáneo sin escribir una línea de código ni sufrir de relaciones rotas.