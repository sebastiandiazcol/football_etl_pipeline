# db/models/gold_models.py
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Date
from db.database import BaseGold

class DimTeam(BaseGold):
    """Dimensión de Equipos: Un registro único por equipo."""
    __tablename__ = "dim_teams"
    team_id = Column(Integer, primary_key=True)
    team_name = Column(String, nullable=False)

class DimPlayer(BaseGold):
    """Dimensión de Jugadores: Un registro único por jugador."""
    __tablename__ = "dim_players"
    player_id = Column(Integer, primary_key=True)
    player_name = Column(String, nullable=False)

class DimCompetition(BaseGold):
    """Dimensión de Competiciones (Ligas/Torneos)."""
    __tablename__ = "dim_competitions"
    competition_id = Column(Integer, primary_key=True)
    competition_name = Column(String, nullable=False)


class FactMatch(BaseGold):
    """
    Hechos de Partidos. 
    AQUÍ CONSOLIDAMOS TU REGLA DE MARCADOR FINAL Y ESTADO.
    """
    __tablename__ = "fact_matches"
    
    match_id = Column(Integer, primary_key=True)
    match_date = Column(DateTime, index=True)
    season_num = Column(Integer)
    
    # Relaciones con Dimensiones
    competition_id = Column(Integer, ForeignKey("dim_competitions.competition_id"))
    home_team_id = Column(Integer, ForeignKey("dim_teams.team_id"))
    away_team_id = Column(Integer, ForeignKey("dim_teams.team_id"))
    
    # Regla de Negocio Consolidada (Goles Oficiales / Conciliados)
    home_score = Column(Integer) 
    away_score = Column(Integer)
    
    # Indicadores analíticos rápidos
    total_goals = Column(Integer) # home_score + away_score
    is_draw = Column(Integer) # 1 si es empate, 0 si no
    winning_team_id = Column(Integer, nullable=True) # ID del ganador, o Null si empate

class FactMatchStat(BaseGold):
    """
    Hechos de Estadísticas.
    Solo IDs y el valor numérico limpio. ¡Power BI amará esta tabla!
    """
    __tablename__ = "fact_match_stats"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    match_id = Column(Integer, ForeignKey("fact_matches.match_id"), index=True)
    team_id = Column(Integer, ForeignKey("dim_teams.team_id"), index=True)
    
    period = Column(String) # "Partido_Completo", "Primer_Tiempo"
    stat_name = Column(String, index=True) # "Posesión", "Remates"
    category_name = Column(String) # "Ataque", "Defensa"
    
    # EL VALOR LISTO PARA DAX
    value_numeric = Column(Float)

class FactShot(BaseGold):
    """
    Hechos de Tiros (El mapa espacial).
    Ideal para visualizaciones de Python (Matplotlib/Seaborn) o Scatter Charts en Power BI.
    """
    __tablename__ = "fact_shots"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    match_id = Column(Integer, ForeignKey("fact_matches.match_id"), index=True)
    team_id = Column(Integer, ForeignKey("dim_teams.team_id"), index=True)
    player_id = Column(Integer, ForeignKey("dim_players.player_id"), index=True)
    
    shot_minute = Column(Float)
    xg = Column(Float)
    xgot = Column(Float)
    outcome_name = Column(String) # "Gol", "Atajado", etc.
    
    position_x = Column(Float)
    position_y = Column(Float)