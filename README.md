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
│   └── create_betting_facts.py   # Ingenieria de variables para Apuestas Deportivas
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

El orquestador `main.py` maneja la ejecucion del pipeline. Se puede procesar un solo partido o hacer extracción masiva histórica por equipo.

**Procesar un partido especifico:**

```powershell
uv run main.py --mode process_match --match 4663209

```

**Extraccion masiva (Scraping Historico):**
Busca los ultimos N partidos finalizados de un equipo y ejecuta el pipeline completo (Bronze -> Silver -> Gold) para cada uno.

```powershell
uv run main.py --mode process_team --team 131 --matches 10

```

*(Nota: El ID 131 corresponde al Real Madrid).*

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

Para extraer "Value Bets" y predecir rendimientos, el pipeline cuenta con un script de ingenieria de caracteristicas que desnormaliza la informacion en tablas listas para el analisis cuantitativo.

Ejecutar generador de apuestas:

```powershell
uv run transform/create_betting_facts.py

```

Esto genera dos tablas analiticas en la capa Gold:

1. **`fact_betting_team`:** Calcula exactamente las estadisticas "A Favor" y "Concedidas" (Tiros, Corners, Amarillas) e identifica si se cumplieron mercados como Ambos Marcan (BTTS) y Over/Under 2.5.
2. **`fact_betting_player`:** Resume las estadisticas vitales del jugador por partido (Tiros Totales, Tiros a Puerta/SOT, xG Acumulado) para el mercado de *Player Props*.

## 🗺️ Ciencia de Datos y Analisis Espacial

El proyecto incluye scripts de visualizacion avanzada en Python, aislando los calculos matematicos del motor de Power BI.

Ejecutar el mapa interactivo de tiros:

```powershell
uv run analysis/shot_map.py

```

Este script utiliza `mplsoccer` para dibujar un medio campo vertical (Vertical Half Pitch), mapeando los disparos a traves de coordenadas corregidas (X/Y invertidas) y escalando el tamano de los puntos segun la metrica xG. Incluye tooltips interactivos con `mplcursors`.

## 📈 Integracion con Power BI

La base de datos esta preparada para conectividad directa (DirectQuery o Importacion) en Power BI.

1. Abrir Power BI Desktop.
2. Obtener Datos -> Origen de datos ODBC o Script de Python.
3. Conectar al archivo `data/03_gold.db`.
4. En la vista del modelo, relacionar las dimensiones (`dim_teams`, `dim_players`, `dim_date`) con las tablas de hechos y las tablas de apuestas (`fact_betting_team`, `fact_betting_player`). El modelo no requiere DAX complejo gracias al trabajo previo del pipeline ETL.

---