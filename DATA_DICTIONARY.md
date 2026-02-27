# Diccionario de Datos - Capa Analítica (Gold)

Este documento describe la estructura y el propósito de las tablas principales ubicadas en la base de datos analítica `03_gold.db`, las cuales están optimizadas para ser consumidas directamente en Power BI o entornos de Data Science.

---

## 📅 Tablas de Dimensiones (Filtros y Ejes Analíticos)

Estas tablas contienen los catálogos y descripciones que permiten cruzar, filtrar y segmentar las métricas mediante un esquema estrella (Star Schema).

### `dim_teams`
*   **Propósito:** Catálogo de equipos de los que se tiene registro.
*   **Columnas Clave:**
    *   `team_id` (INT): Identificador único del equipo.
    *   `team_name` (STRING): Nombre oficial del equipo.

### `dim_players`
*   **Propósito:** Catálogo histórico de jugadores y sus metadatos vitales.
*   **Columnas Clave:**
    *   `player_id` (INT): Identificador único del jugador.
    *   `player_name` (STRING): Nombre completo.
    *   `position_name` (STRING): Posición natural (Ej. Defender, Forward).
    *   `jersey_number` (INT): Número habitual.

### `dim_competitions`
*   **Propósito:** Catálogo de Ligas y Copas extraídas.
*   **Columnas Clave:** `competition_id`, `competition_name` (Ej. Premier League, Serie A).

### `dim_date`
*   **Propósito:** Dimensión de calendario (`Time Intelligence`) para posibilitar cruces por mes, año o día de la semana.
*   **Columnas Clave:** `date_id`, `Year`, `Month`, `Day`, `Weekday_Name`.

---

## 📈 Tablas de Hechos (Métricas Base)

Almacenan los eventos atómicos ocurridos dentro de los partidos (Transacciones).

### `fact_matches`
*   **Propósito:** Resumen general del resultado final de cada partido.
*   **Columnas Clave:**
    *   `match_id` (INT): ID único del partido.
    *   `home_score` / `away_score` (INT): Goles marcados por local y visitante.
    *   `total_goals` (INT): Suma de goles en el partido.
    *   `referee_name` (STRING): Árbitro designado para el encuentro.

### `fact_lineups`
*   **Propósito:** Registro de los jugadores que participaron en un partido específico, sus posiciones en el campo y minutos jugados.
*   **Columnas Clave:**
    *   `status_text` (STRING): Indicador de titularidad ("Starting" o "Substitute").
    *   `minutes_played` (INT): Tiempo exacto en cancha.

### `fact_events`
*   **Propósito:** Bitácora cronológica minuto a minuto de todo lo sucedido en el juego.
*   **Columnas Clave:**
    *   `event_type_name` (STRING): Tipo de acción (Gol, Tarjeta amarilla, Tarjeta roja, Sustitución).
    *   `game_minute` (FLOAT): Minuto exacto de la incidencia.

### `fact_shots`
*   **Propósito:** Catálogo espacial (X/Y) y probabilístico de cada remate intentado en la base de datos.
*   **Columnas Clave:**
    *   `xg` (FLOAT): Expected Goals. Probabilidad matemática (0 a 1) de que el tiro terminara en gol.
    *   `outcome_name` (STRING): Destino final del tiro (Atajado, Gol, Poste, Fuera).

---

## 🎯 Data Marts de Apuestas y Analítica Avanzada (Betting Hub)

Estas tablas son generadas por ingeniería de características (`create_betting_facts.py` y `create_powerbi_mart.py`) cruzando los hechos y dimensiones para calcular directamente variables predictivas e indicadores de apuestas deportivas.

### 1. `powerbi_mart_player_props` 
**La joya de la corona para analizar el rendimiento de jugadores.** Desnormaliza dimensiones y calcula promedios móviles para análisis de "Player Props" y estado de forma.
*   **Métricas Atómicas:**
    *   `minutes_played` (INT): Minutos disputados.
    *   `is_starter` (INT): Booleano (1=Titular, 0=Suplente).
    *   `total_shots` / `shots_on_target` / `goals` / `total_xg`: Mapeo ofensivo principal.
*   **Ingeniería Defensiva/Creativa:**
    *   `passes_completed` (INT): Pases exitosos.
    *   `key_passes` (INT): Pases que desencadenaron un tiro claro ("Pases Clave").
    *   `xa` (FLOAT): Asistencias Esperadas.
    *   `interceptions` / `clearances`: Tareas defensivas puras.
    *   `fouls_committed` / `fouls_received`: Faltas tácticas e infracciones sufridas.
*   **Métricas Predictivas (Estado de Forma):**
    *   `{metrica}_roll3` y `{metrica}_roll5` (FLOAT): Promedio de las últimas 3 y 5 actuaciones del jugador (Ej. `shots_on_target_roll3`). Informa "apuestas en caliente".

### 2. `fact_betting_team`
Data tabular por equipo y partido con indicadores para resolver mercados tradicionales de apuestas (Goles, Córners, Tarjetas).
*   **Banderas de Mercado (Booleanos 1=Ganador, 0=Perdedor):**
    *   `is_btts`: Ambos Equipos Marcan (Both Teams to Score).
    *   `is_over_1_5` / `is_over_2_5` / `is_over_3_5`: Mercados de totales de goles.
*   **Indicadores Cronológicos y de Mitades (Half-Time):**
    *   `goals_ht_for` / `goals_ht_conceded`: Goles al descanso.
    *   `scored_first` / `conceded_first` (Booleano): Indicador de quién abrió el marcador.
    *   `first_goal_minute` (INT): Minuto exacto donde se rompió el 0-0.
*   **Ineficiencias Matemáticas ("Suerte"):**
    *   `overperformance_for` (FLOAT): Goles reales menos Expected Goals (xG). Indica si el equipo está teniendo más suerte/efectividad estadística de la merecida matemáticamente.

### 3. `mart_betting_trends`
Analítica de Series de Tiempo que agrupa el progreso y momento actual del equipo de forma móvil (sin importar el contrincante).
*   **Tendencias Generales:** Promedios de los últimos 3 y 5 partidos para todas las métricas (Goles, Tiros al arco, Córners). Funciona con la sintaxis `{metrica}_roll3`.
*   **Desdoblamiento de Localía (Splits):**
    *   `{metrica}_roll3_home`: Aisla las estadísticas considerando SOLO si el equipo jugó en calidad de "Local" en sus últimos 3 lances.
    *   `{metrica}_roll3_away`: Aislamiento estadístico como visitante (Away).

### 4. `mart_referee_stats`
Perfilador y ranqueador generalizado de Árbitros.
*   **Métricas:**
    *   `avg_yellow_cards` / `avg_red_cards` (FLOAT): Media de amonestaciones mostradas por el colegiado por partido.
    *   `matches_refereed` (INT): Robustez del árbitro en la base de datos (Volumen de partidos analizados de dicho réferi).
    *   `total_yellow_cards` / `total_red_cards` (INT).

---

*Desarrollado en Python con SQLite3/Pandas y concebido para despliegues de grado empresarial.*
