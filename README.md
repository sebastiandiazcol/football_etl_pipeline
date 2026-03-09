# Football Data Analytics & Betting ETL Pipeline

Motor de procesamiento de datos de fútbol de alto rendimiento diseñado para la extracción masiva, transformación analítica y modelado estadístico. Construido bajo la **Arquitectura Medallion** (Bronze, Silver, Gold), este pipeline transforma datos JSON crudos de proveedores deportivos (ej. 365Scores) en un Esquema Estrella optimizado para Business Intelligence (Power BI) y Ciencia de Datos (Python).

## 📋 Arquitectura del Proyecto

El proyecto divide estrictamente el procesamiento de datos en capas progresivas de calidad:

1. **Capa BRONZE (`01_bronze.db`):** Almacenamiento inmutable de la data cruda (JSON) extraída de la API. Garantiza que nunca se pierda el dato original.
2. **Capa SILVER (`02_silver.db`):** Base de datos relacional altamente normalizada (3NF). Limpia inconsistencias, extrae periodos de juego (Primer y Segundo Tiempo) y maneja relaciones complejas (Alineaciones, Eventos, Tiros, Estadísticas).
3. **Capa GOLD (`03_gold.db`):** Data Warehouse modelado en Esquema Estrella (Star Schema). Diseñado para ser consumido directamente por analistas de datos y herramientas de BI.
4. **Capa de ENRIQUECIMIENTO (Apuestas y Ciencia de Datos):** Scripts estadísticos en Python que pre-calculan métricas avanzadas (xG, Diferenciales, Player Props) y las inyectan en Gold.

## 📂 Estructura del Repositorio

```text
football_etl_pipeline/
│
├── analysis/
│   └── shot_map.py               # Analitica espacial interactiva (Mapas de tiros verticales)
│
├── db/
│   ├── database.py               # Motores SQLAlchemy y configuracion de sesiones
│   └── models/
│       ├── bronze_models.py      # Esquema inmutable JSON
│       ├── silver_models.py      # Tablas normalizadas con borrado en cascada
│       └── gold_models.py        # Esquema Estrella (DimTeams, FactShots, etc.)
│
├── transform/
│   ├── bronze_to_silver.py       # ETL: Desanidado JSON y limpieza de tipos de datos
│   ├── silver_to_gold.py         # ETL: Carga de Hechos y Upsert Inteligente de Dimensiones
│   ├── create_dim_date.py        # Generador de Dimension Calendario para Time Intelligence
│   ├── create_betting_facts.py   # Ingenieria de variables para Apuestas Deportivas
│   └── create_powerbi_mart.py    # Generador del Data Mart de Player Props para Power BI
│
├── utils/
│   └── logger.py                 # Trazabilidad y monitoreo del pipeline
│
├── data/                         # Bases de datos SQLite (Generadas automaticamente)
│   ├── 01_bronze.db
│   ├── 02_silver.db
│   └── 03_gold.db
│
├── main.py                       # Orquestador Principal (CLI)
└── README.md

```

## 🚀 Requisitos e Instalación

Este proyecto utiliza `uv` como gestor de paquetes de alto rendimiento.

1. Clonar el repositorio.
2. Instalar las dependencias en el entorno virtual:

```powershell
uv pip install sqlalchemy requests pandas matplotlib mplsoccer mplcursors

```

## ⚙️ Uso del Pipeline ETL (CLI)

La forma principal y más sencilla de interactuar con el pipeline es a través del **Preparador de Partidos** (`tools/prepare_match.py`), un asistente interactivo que te permite buscar equipos por nombre (conectándose a la API de 365scores para encontrar su ID), para luego descargar y procesar automáticamente sus últimos partidos.

Para iniciar el asistente interactivo, ejecuta en tu terminal:

```powershell
python tools/prepare_match.py
```
*(También puedes usar `uv run tools/prepare_match.py` si prefieres usar el gestor de paquetes virtual).*

El script te irá guiando paso a paso. El orquestador interno `main.py` manejará toda la ejecución del pipeline (Bronze -> Silver -> Gold) por detrás una vez que confirmes los equipos.

## 📊 Modelo de Datos (Capa GOLD)

El Esquema Estrella resultante en `03_gold.db` esta compuesto por:

**Tablas de Dimensiones (Filtros):**

* `dim_teams`: Catalogo de equipos.
* `dim_players`: Catalogo de jugadores (Con actualizacion inteligente UPSERT).
* `dim_competitions`: Ligas y torneos.
* `dim_date`: Calendario continuo para analisis temporal (YTD, promedios moviles).

**Tablas de Hechos (Metricas):**

* `fact_matches`: Resumen del partido, resultado final e indicadores de victoria.
* `fact_match_stats`: Estadisticas puras granulares (Posesion, Faltas) segmentadas por Primer/Segundo Tiempo.
* `fact_events`: Minuto a minuto de tarjetas, sustituciones y goles.
* `fact_lineups`: Alineaciones titulares, minutos jugados y posicion en el campo.
* `fact_shots`: Mapa de coordenadas X/Y de cada disparo, con probabilidad matematica de gol (`xg`).

## 🎯 Modulo de Apuestas Deportivas (Sports Betting Module)

Para extraer "Value Bets" y predecir rendimientos, el pipeline cuenta con un script de ingenieria de caracteristicas que desnormaliza la informacion en tablas listas para el analisis cuantitativo (***Esto se ejecuta automáticamente al usar el asistente `prepare_match.py`***).

Esto genera dos tablas analiticas en la capa Gold:

1. **`fact_betting_team`:** Calcula exactamente las estadisticas "A Favor" y "Concedidas" (Tiros, Corners, Amarillas). Identifica si se cumplieron mercados como Ambos Marcan (BTTS) y Over/Under 2.5, **incluyendo mercados de Mitades (Half-Time Data)** y modelado de tiempos de anotacion (First To Score).
2. **`fact_betting_player`:** Resume las estadisticas vitales del jugador por partido (Tiros Totales, Tiros a Puerta/SOT, xG Acumulado) para el mercado de *Player Props*.
3. **`mart_referee_stats`:** Agrupacion historica de la tendencia de tarjetas (Amarillas/Rojas) por Árbitro.
4. **`mart_betting_trends`:** Promedios moviles (Rolling Averages) de rendimiento de los ultimos 3 y 5 partidos del equipo calculados dinamicamente para evaluar la forma reciente del equipo.
5. **`powerbi_mart_player_props`:** Data Mart desnormalizado y enriquecido para analisis directo. Ademas de tiros y goles, incluye ingenieria de caracteristicas defensivas y creativas (Faltas, Pases, Pases Clave, xA, Intercepciones, Despejes) y banderas de titularidad (`is_starter`).

## 📈 Integracion con Power BI (Vía SQL Server / Docker)

Para evitar los comunes errores de tipos de datos del Driver ODBC de SQLite (Ej: `0x80040E1D`), este proyecto incluye un módulo automatizado que migra la base de datos `03_gold.db` en su totalidad a una instancia de **Microsoft SQL Server** ejecutándose en un contenedor de **Docker**. Esta es la opción más robusta ("Enterprise") para modelos de Power BI grandes.

### 1. Configurar Docker
Docker nos permite tener un SQL Server aislado en nuestra máquina sin complejas instalaciones. Los datos persisten de manera segura por reinicios usando volúmenes de Docker.
Ejecuta esto en tu terminal por única vez para crear el servidor local:

```powershell
docker run -e "ACCEPT_EULA=Y" -e "MSSQL_SA_PASSWORD=SuperSecret123!" -p 1433:1433 -d --name sql_futbol mcr.microsoft.com/mssql/server:2022-latest
```

### 2. Migración de los Datos a SQL Server
Cada vez que proceses y busques nuevos equipos o partidos a través del asistente `tools/prepare_match.py`, la capa Bronze, Silver y Gold de SQLite se actualizarán localmente y **automáticamente el asistente empujará esas nuevas métricas** a SQL Server por detrás creando/actualizando la base de datos `FootballGold`.
*(Nota: El asistente usa `pyodbc` y `sqlalchemy` para leer de `03_gold.db` y realizar el volcado masivo)*.

### 3. Conexión a Power BI
1. Abrir Power BI Desktop.
2. Hacer click en **Obtener Datos -> SQL Server**.
3. **Servidor:** `localhost`
4. **Base de Datos:** `FootballGold`
5. En autenticación elige **Base de Datos** con usuario `sa` y la contraseña de Docker (`SuperSecret123!`).

Con esta integración gozarás del máximo rendimiento sin escribir una sola consulta y todo mantendrá sus relaciones del *Star Schema* (Modelo en Estrella) purista, sin romper los filtros visuales.

---