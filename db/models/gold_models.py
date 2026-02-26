# db/models/gold_models.py
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Boolean
from db.database import BaseGold

class DimTeam(BaseGold):
    __tablename__ = "dim_teams"
    team_id = Column(Integer, primary_key=True)
    team_name = Column(String, nullable=False)

class DimPlayer(BaseGold):
    __tablename__ = "dim_players"
    player_id = Column(Integer, primary_key=True)
    player_name = Column(String, nullable=False)

class DimCompetition(BaseGold):
    __tablename__ = "dim_competitions"
    competition_id = Column(Integer, primary_key=True)
    competition_name = Column(String, nullable=False)

class FactMatch(BaseGold):
    __tablename__ = "fact_matches"
    match_id = Column(Integer, primary_key=True)
    match_date = Column(DateTime, index=True)
    season_num = Column(Integer)
    competition_id = Column(Integer, ForeignKey("dim_competitions.competition_id"))
    home_team_id = Column(Integer, ForeignKey("dim_teams.team_id"))
    away_team_id = Column(Integer, ForeignKey("dim_teams.team_id"))
    home_score = Column(Integer)
    away_score = Column(Integer)
    total_goals = Column(Integer)
    is_draw = Column(Integer)
    winning_team_id = Column(Integer, nullable=True)

class FactMatchStat(BaseGold):
    __tablename__ = "fact_match_stats"
    id = Column(Integer, primary_key=True, autoincrement=True)
    match_id = Column(Integer, ForeignKey("fact_matches.match_id"), index=True)
    team_id = Column(Integer, ForeignKey("dim_teams.team_id"), index=True)
    period = Column(String)
    stat_name = Column(String, index=True)
    category_name = Column(String)
    value_numeric = Column(Float)

class FactShot(BaseGold):
    __tablename__ = "fact_shots"
    id = Column(Integer, primary_key=True, autoincrement=True)
    match_id = Column(Integer, ForeignKey("fact_matches.match_id"), index=True)
    team_id = Column(Integer, ForeignKey("dim_teams.team_id"), index=True)
    player_id = Column(Integer, ForeignKey("dim_players.player_id"), index=True)
    shot_minute = Column(Float)
    xg = Column(Float)
    xgot = Column(Float)
    outcome_name = Column(String)
    position_x = Column(Float)
    position_y = Column(Float)

class FactLineup(BaseGold):
    __tablename__ = "fact_lineups"
    id = Column(Integer, primary_key=True, autoincrement=True)
    match_id = Column(Integer, ForeignKey("fact_matches.match_id"), index=True)
    team_id = Column(Integer, ForeignKey("dim_teams.team_id"), index=True)
    player_id = Column(Integer, ForeignKey("dim_players.player_id"), index=True)
    jersey_number = Column(Integer)
    status_text = Column(String)
    formation_line = Column(Integer, nullable=True)
    field_line = Column(Float, nullable=True)
    field_side = Column(Float, nullable=True)
    minutes_played = Column(Integer, nullable=True)

class FactEvent(BaseGold):
    __tablename__ = "fact_events"
    id = Column(Integer, primary_key=True, autoincrement=True)
    match_id = Column(Integer, ForeignKey("fact_matches.match_id"), index=True)
    team_id = Column(Integer, ForeignKey("dim_teams.team_id"), index=True)
    event_order = Column(Integer)
    game_minute = Column(Float)
    event_type_name = Column(String)
    event_sub_type = Column(String)
    primary_player_id = Column(Integer, ForeignKey("dim_players.player_id"), nullable=True, index=True)
    secondary_player_id = Column(Integer, ForeignKey("dim_players.player_id"), nullable=True)
    is_major = Column(Boolean, default=False)