# Football ETL Pipeline ⚽

Un pipeline de datos automatizado con arquitectura Medallion (Bronze, Silver, Gold), diseñado para extraer, transformar y analizar estadísticas de fútbol al máximo nivel de detalle. Preparado para visualizaciones avanzadas y modelos de Machine Learning/Apuestas Deportivas.

## Características Analíticas Destacadas 🚀

### 1. Modelado "Betting Facts" (`transform/create_betting_facts.py`)
He diseñado y programado componentes listos para analíticas predictivas utilizando lógicas de _Pivot_ y _Self-Join dinámico_:
- **Cruce Automático**: Cruza al equipo local con el visitante para calcular automáticamente métricas "a un solo lado".
- **`fact_betting_team`**: Todo en una sola tabla desnormalizada y calculada específicamente para que Power BI la consuma sin necesidad de DAX complejo. Tiene métricas **A Favor** y **Concedidas** (Goles, Córners, Tiros, Amarillas), y flags binarios listos (BTTS, Over 2.5, etc.) para cada equipo y partido. 
- **`fact_betting_player`**: Resumen partido a partido por cada jugador. Cuenta total de tiros, tiros a puerta y xG. ¡Oro puro para descubrir oportunidades en mercados como "Jugador X hace más de 1.5 tiros al arco"!

### 2. Mapas Espaciales de Tiros Interactivos (`analysis/shot_map.py`)
No es solo un gráfico estático en Python, es un pequeño dashboard interactivo instantáneo:
- Dibuja el campo de juego usando coordenadas precisas.
- No hagas clic, simplemente pasa el puntero de tu ratón (*hover*) sobre cualquier punto verde (gol) o rojo (No gol).
- Verás aparecer una **caja oscura y elegante** diciéndote en tiempo real exactamente: el jugador que pateó, contra qué rival, el minuto exacto del partido, el resultado, y la probabilidad matemática (xG) de que esa jugada fuera gol.

### 3. Dimensión Calendario (`transform/create_dim_date.py`)
Para no sufrir con las fechas en PowerBI, he creado la tabla `dim_date` en la capa base de datos Gold. Se mapea un rango configurable (ej. 2020 a 2030), con columnas temporales calculadas: año, trimestre, nombre de mes y día de la semana traducidos al español para que el analista de datos no pierda tiempo.

### 4. Capas ETL mejoradas: Silver y Gold Perfeccionadas
- **Eventos y Alineaciones**: He modificado la arquitectura inicial para llevar fluidamente estos datos hasta la última capa analítica (`FactEvent`, `FactLineup`).
- **Orquestación**: La función principal está centralizada para procesar o extraer en crudo mediante un proceso estructurado pasando por Bronze ➡ Silver ➡ Gold.

## ¿Qué sigue?
Si deseas expandir este entorno de datos:
- Conectar directamente la base Gold (`03_gold.db`) a PowerBI.
- Entrenar modelos de predicción (como Random Forest o XGBoost) leyendo la tabla desnormalizada de `fact_betting`.
