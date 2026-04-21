# Diccionario de Datos - Capa Analítica (Gold)

Este documento describe la estructura y el propósito de las tablas principales ubicadas en la base de datos analítica `03_gold.db`, así como su réplica alojada en SQL Server. Están desnormalizadas y optimizadas para Inteligencia de Negocios y Ciencia de Datos.

---

## 📅 Tablas de Dimensiones (Filtros y Ejes Analíticos)

Estas tablas contienen los catálogos y atributos descriptivos que permiten cruzar, filtrar y segmentar las métricas de los partidos y jugadores mediante el modelo Estrella.

### `dim_team`
*   **Propósito:** Catálogo oficial de equipos con los que el pipeline ha interactuado.
*   **Columnas Clave:**
    *   `team_id` (INT): Identificador único del equipo proveniente de la API original.
    *   `team_name` (STRING): Nombre de la institución.
    *   `country` (STRING): País al que pertenece el club.

### `dim_player`
*   **Propósito:** Catálogo histórico de jugadores y sus metadatos biográficos.
*   **Columnas Clave:**
    *   `player_id` (INT): Identificador único permanente del jugador.
    *   `player_name` (STRING): Nombre deportivo o completo.
    *   `position_name` (STRING): Posición principal (Ej. Defender, Forward, Midfielder).
    *   `jersey_number` (INT): Dorsal más comúnmente usado.

### `dim_competition`
*   **Propósito:** Catálogo de competiciones (Ligas, Copas).
*   **Columnas Clave:** `competition_id`, `competition_name` (Ej. Premier League, Serie A).

### `dim_referee`
*   **Propósito:** Base de datos de árbitros extraída dinámicamente de los partidos.
*   **Columnas Clave:** `referee_id` (Generado por hash text), `referee_name`.

### `dim_date`
*   **Propósito:** Dimensión de tiempo continua (`Time Intelligence`) para posibilitar cruces MTD, YTD, cruces semestrales o por días particulares de la semana.
*   **Columnas Clave:** `date_id`, `Year`, `Month`, `Day`, `Weekday_Name`.

---

## 📈 Tablas de Hechos "Marts" (Métricas Enriquecidas)

Ya no existen tablas atómicas aisladas, la capa Gold ahora condensa todo el detalle del partido, las métricas ofensivas y defensivas, los resultados de mercados de apuestas y los historiales de forma mediante Promedios Móviles.

### `fact_team_match`
El nivel de detalle es un equipo dentro de un partido específico. Por cada partido jugado, existen dos filas (el local y el visitante).

**Resumen del Partido:**
* `match_id` (INT) / `team_id` (INT) / `opponent_id` (INT).
* `is_home` (INT): Booleano identificando si el equipo jugó de local (1) o visitante (0).
* `team_score` / `opponent_score`: Goles marcados por el equipo vs el oponente.
* `match_date_id` (INT) / `match_date`: Llaves con la dimensión tiempo.

**Métricas y Rendimiento:**
* `possession_for` (FLOAT), `shots_on_target_for` (INT), `corners_for` (INT).
* `fouls_for` (INT), `yellow_cards_for` (INT), `red_cards_for` (INT).

**Indicadores Predictivos (Betting Flags):**
* `is_btts` (FLOAT): 1 si "Ambos Equipos Anotan", 0 caso contrario.
* `is_over_2_5` (FLOAT): 1 si hubo 3 goles o más en el partido.
* `scored_first` (FLOAT) / `conceded_first` (FLOAT): Quién rompió el arco en cero.

**Tendencias Modulares (Rolling Averages):**
* Resumen en vivo de cómo llega el equipo al partido evaluando sus desempeños a corto y mediano plazo (Rachas).
* `team_goals_scored_roll5` (FLOAT): Promedio de goles marcados por el equipo en sus últimos 5 partidos ligueros de la muestra.
* `team_goals_conceded_roll5` (FLOAT): Promedio encajado en sus últimos 5 partidos.
* `team_shots_on_target_roll5` (FLOAT): Tiros al arco como indicador de ofensividad en forma.
* *Nota: La lógica para `roll3` existe en el mismo formato de igual manera pero con los últimos 3 partidos.*

---

### `fact_player_match`
Nivel de granularidad a nivel jugador por partido. Concentrado en métricas individuales. Es la tabla vital en el análisis del mercado de "Player Props" o rendimiento Fantasy.

**Participación General:**
* `match_id` / `player_id`.
* `is_starter` (INT): 1 si arrancó de titular desde el pitazo, 0 si ingresó de cambio.
* `minutes_played` (INT).

**Aportes Individuales:**
* `goals` (INT) / `assists` (INT).
* `shots_on_target` (INT), `shots_off_target` (INT), `total_shots` (INT).
* `passes_completed` (INT) / `passes_total` (INT).
* `key_passes` (INT): Oportunidades creadas para compañeros cruzando líneas.

**Aspecto Defensivo y Físico:**
* `tackles` (INT) / `interceptions` (INT) / `clearances` (INT).
* `fouls_committed` (INT).
* `yellow_cards` / `red_cards`.

**Historial a Nivel Jugador (Forma):**
* Al igual que equipos, se le asocia al jugador el rendimiento que tuvo en sus duelos previos a este.
* `player_shots_on_target_roll3` (FLOAT): Mide qué tan fino / ofensivo ha estado un atacante (Ideal para decidir apuestas Over/Under SOT).
* `player_goals_roll3` (FLOAT): Tendencia goleadora.
* `player_fouls_roll3` (FLOAT): Promedio agresividad / amonestaciones inminentes.

---

*Desarrollado en Python, SQLAlchemy y optimizado para implementaciones corporativas en SQL Server.*
