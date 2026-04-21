# db/models/gold_models.py
# Modelo Copo de Nieve (Snowflake Schema) para Power BI + Análisis de Apuestas
# 7 tablas: 2 hechos + 5 dimensiones

from sqlalchemy import Column, Integer, String, Float, Date, Index
from db.database import BaseGold


# ============================================================
# DIMENSIONES
# ============================================================

class DimTeam(BaseGold):
    __tablename__ = "dim_team"
    team_id = Column(Integer, primary_key=True)
    team_name = Column(String, nullable=False)


class DimPlayer(BaseGold):
    __tablename__ = "dim_player"
    player_id = Column(Integer, primary_key=True)
    player_name = Column(String, nullable=False)


class DimCompetition(BaseGold):
    __tablename__ = "dim_competition"
    competition_id = Column(Integer, primary_key=True)
    competition_name = Column(String, nullable=False)


class DimReferee(BaseGold):
    __tablename__ = "dim_referee"
    referee_id = Column(Integer, primary_key=True)  # hash del nombre
    referee_name = Column(String, nullable=False)
    matches_refereed = Column(Integer, default=0)
    avg_yellow_cards = Column(Float, default=0.0)
    avg_red_cards = Column(Float, default=0.0)
    total_yellow_cards = Column(Integer, default=0)
    total_red_cards = Column(Integer, default=0)


class DimDate(BaseGold):
    __tablename__ = "dim_date"
    date_key = Column(Integer, primary_key=True)  # ej: 20241027
    date_actual = Column(Date)
    year = Column(Integer)
    quarter = Column(Integer)
    month = Column(Integer)
    month_name = Column(String)
    day = Column(Integer)
    day_name = Column(String)
    is_weekend = Column(Integer)


# ============================================================
# HECHOS - TABLA PRINCIPAL: EQUIPO POR PARTIDO
# Grano: 1 fila por equipo por partido (2 filas por partido)
# ============================================================

class FactTeamMatch(BaseGold):
    __tablename__ = "fact_team_match"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # --- Claves / Dimensiones ---
    match_id = Column(Integer, nullable=False, index=True)
    date_key = Column(Integer, index=True)          # FK → dim_date
    team_id = Column(Integer, nullable=False, index=True)   # FK → dim_team
    opponent_id = Column(Integer, nullable=False, index=True)  # FK → dim_team
    competition_id = Column(Integer, index=True)     # FK → dim_competition
    referee_id = Column(Integer, nullable=True)       # FK → dim_referee
    season_num = Column(Integer)
    is_home = Column(Integer)  # 1=Local, 0=Visitante

    # --- Goles: Partido Completo (FT) ---
    goals_for = Column(Integer, default=0)
    goals_against = Column(Integer, default=0)
    total_goals = Column(Integer, default=0)

    # --- Goles: Primer Tiempo (HT) ---
    goals_ht_for = Column(Integer, default=0)
    goals_ht_against = Column(Integer, default=0)
    total_goals_ht = Column(Integer, default=0)

    # --- Goles: Segundo Tiempo (2H) ---
    goals_2h_for = Column(Integer, default=0)
    goals_2h_against = Column(Integer, default=0)
    total_goals_2h = Column(Integer, default=0)

    # --- Stats: Partido Completo (FT) — A Favor / En Contra ---
    shots_on_target_for = Column(Integer, default=0)
    shots_on_target_against = Column(Integer, default=0)
    shots_off_target_for = Column(Integer, default=0)
    shots_off_target_against = Column(Integer, default=0)
    total_shots_for = Column(Integer, default=0)
    total_shots_against = Column(Integer, default=0)
    corners_for = Column(Integer, default=0)
    corners_against = Column(Integer, default=0)
    fouls_for = Column(Integer, default=0)
    fouls_against = Column(Integer, default=0)
    yellow_cards_for = Column(Integer, default=0)
    yellow_cards_against = Column(Integer, default=0)
    red_cards_for = Column(Integer, default=0)
    red_cards_against = Column(Integer, default=0)
    possession_for = Column(Float, default=0.0)

    # --- Stats: Primer Tiempo (HT) — A Favor / En Contra ---
    shots_on_target_ht_for = Column(Integer, default=0)
    shots_on_target_ht_against = Column(Integer, default=0)
    shots_off_target_ht_for = Column(Integer, default=0)
    shots_off_target_ht_against = Column(Integer, default=0)
    total_shots_ht_for = Column(Integer, default=0)
    total_shots_ht_against = Column(Integer, default=0)
    corners_ht_for = Column(Integer, default=0)
    corners_ht_against = Column(Integer, default=0)
    fouls_ht_for = Column(Integer, default=0)
    fouls_ht_against = Column(Integer, default=0)
    yellow_cards_ht_for = Column(Integer, default=0)
    yellow_cards_ht_against = Column(Integer, default=0)
    red_cards_ht_for = Column(Integer, default=0)
    red_cards_ht_against = Column(Integer, default=0)
    possession_ht_for = Column(Float, default=0.0)

    # --- Stats: Segundo Tiempo (2H) — A Favor / En Contra ---
    shots_on_target_2h_for = Column(Integer, default=0)
    shots_on_target_2h_against = Column(Integer, default=0)
    shots_off_target_2h_for = Column(Integer, default=0)
    shots_off_target_2h_against = Column(Integer, default=0)
    total_shots_2h_for = Column(Integer, default=0)
    total_shots_2h_against = Column(Integer, default=0)
    corners_2h_for = Column(Integer, default=0)
    corners_2h_against = Column(Integer, default=0)
    fouls_2h_for = Column(Integer, default=0)
    fouls_2h_against = Column(Integer, default=0)
    yellow_cards_2h_for = Column(Integer, default=0)
    yellow_cards_2h_against = Column(Integer, default=0)
    red_cards_2h_for = Column(Integer, default=0)
    red_cards_2h_against = Column(Integer, default=0)
    possession_2h_for = Column(Float, default=0.0)

    # --- xG (Expected Goals) ---
    xg_for = Column(Float, default=0.0)
    xg_against = Column(Float, default=0.0)
    overperformance = Column(Float, default=0.0)  # goals_for - xg_for

    # --- Mercados de Apuestas: Partido Completo (FT) ---
    match_result = Column(String)   # W / D / L
    points = Column(Integer, default=0)  # 3 / 1 / 0
    win = Column(Integer, default=0)
    draw = Column(Integer, default=0)
    loss = Column(Integer, default=0)
    is_btts = Column(Integer, default=0)  # Both Teams To Score
    is_over_0_5 = Column(Integer, default=0)
    is_over_1_5 = Column(Integer, default=0)
    is_over_2_5 = Column(Integer, default=0)
    is_over_3_5 = Column(Integer, default=0)
    is_over_4_5 = Column(Integer, default=0)
    clean_sheet = Column(Integer, default=0)  # 1 si no recibió gol
    scored_first = Column(Integer, default=0)
    conceded_first = Column(Integer, default=0)
    first_goal_minute = Column(Float, nullable=True)

    # --- Mercados de Apuestas: Primer Tiempo (HT) ---
    result_ht = Column(String, nullable=True)   # W / D / L del HT
    is_btts_ht = Column(Integer, default=0)
    is_over_0_5_ht = Column(Integer, default=0)
    is_over_1_5_ht = Column(Integer, default=0)
    clean_sheet_ht = Column(Integer, default=0)

    # --- Rolling Averages (Tendencias) ---
    goals_for_roll3 = Column(Float, default=0.0)
    goals_for_roll5 = Column(Float, default=0.0)
    goals_against_roll3 = Column(Float, default=0.0)
    goals_against_roll5 = Column(Float, default=0.0)
    xg_for_roll3 = Column(Float, default=0.0)
    xg_for_roll5 = Column(Float, default=0.0)
    shots_on_target_for_roll3 = Column(Float, default=0.0)
    total_shots_for_roll3 = Column(Float, default=0.0)
    corners_for_roll3 = Column(Float, default=0.0)

    # Índices compuestos para optimizar consultas de Power BI
    __table_args__ = (
        Index('idx_ftm_match_team', 'match_id', 'team_id', unique=True),
        Index('idx_ftm_team_date', 'team_id', 'date_key'),
    )


# ============================================================
# HECHOS - TABLA SECUNDARIA: JUGADOR POR PARTIDO (PLAYER PROPS)
# Grano: 1 fila por jugador por partido
# ============================================================

class FactPlayerMatch(BaseGold):
    __tablename__ = "fact_player_match"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # --- Claves / Dimensiones ---
    match_id = Column(Integer, nullable=False, index=True)
    date_key = Column(Integer, index=True)             # FK → dim_date
    player_id = Column(Integer, nullable=False, index=True)  # FK → dim_player
    team_id = Column(Integer, nullable=False, index=True)    # FK → dim_team
    jersey_number = Column(Integer, nullable=True)
    is_home = Column(Integer, default=0)
    is_starter = Column(Integer, default=0)  # 1=Titular

    # --- Stats Principales ---
    minutes_played = Column(Integer, default=0)
    goals = Column(Integer, default=0)
    total_shots = Column(Integer, default=0)
    shots_on_target = Column(Integer, default=0)
    xg = Column(Float, default=0.0)
    passes_completed = Column(Integer, default=0)
    key_passes = Column(Integer, default=0)
    xa = Column(Float, default=0.0)
    fouls_committed = Column(Integer, default=0)
    fouls_received = Column(Integer, default=0)
    interceptions = Column(Integer, default=0)
    clearances = Column(Integer, default=0)

    # --- Rolling Averages (Tendencias) ---
    goals_roll3 = Column(Float, default=0.0)
    goals_roll5 = Column(Float, default=0.0)
    total_shots_roll3 = Column(Float, default=0.0)
    total_shots_roll5 = Column(Float, default=0.0)
    sot_roll3 = Column(Float, default=0.0)
    sot_roll5 = Column(Float, default=0.0)
    key_passes_roll3 = Column(Float, default=0.0)
    fouls_committed_roll3 = Column(Float, default=0.0)
    passes_completed_roll3 = Column(Float, default=0.0)

    # Índices compuestos para optimizar
    __table_args__ = (
        Index('idx_fpm_match_player', 'match_id', 'player_id', unique=True),
        Index('idx_fpm_player_date', 'player_id', 'date_key'),
    )