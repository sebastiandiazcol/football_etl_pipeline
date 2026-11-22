# db/models/silver_models.py
from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime
from db.database import BaseSilver

class MatchSilver(BaseSilver):
    __tablename__ = "silver_matches"
    
    match_id = Column(Integer, primary_key=True, index=True)
    url = Column(String, unique=True, nullable=False)
    match_date = Column(DateTime, index=True)
    competition_id = Column(Integer, index=True)
    competition_name = Column(String)
    season_num = Column(Integer)
    round_num = Column(Integer)
    round_name = Column(String)
    home_team_id = Column(Integer, index=True)
    home_team_name = Column(String)
    away_team_id = Column(Integer, index=True)
    away_team_name = Column(String)
    home_score = Column(Float)
    away_score = Column(Float)
    status_text = Column(String)
    venue_name = Column(String, nullable=True)
    referee_name = Column(String, nullable=True)
    date_scraped = Column(DateTime, default=datetime.utcnow)

    # RELACIONES DE BORRADO EN CASCADA
    stats = relationship("MatchStatSilver", back_populates="match", cascade="all, delete-orphan")
    events = relationship("MatchEventSilver", back_populates="match", cascade="all, delete-orphan")
    lineups = relationship("MatchLineupSilver", back_populates="match", cascade="all, delete-orphan")
    shots = relationship("MatchShotSilver", back_populates="match", cascade="all, delete-orphan")

class MatchStatSilver(BaseSilver):
    __tablename__ = "silver_match_stats"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    match_id = Column(Integer, ForeignKey("silver_matches.match_id"), nullable=False, index=True)
    team_id = Column(Integer, index=True)
    team_type = Column(String)
    period = Column(String, index=True)
    stat_id = Column(Integer)
    stat_name = Column(String, index=True)
    category_name = Column(String)
    value_string = Column(String)
    value_numeric = Column(Float)
    
    match = relationship("MatchSilver", back_populates="stats")

class MatchEventSilver(BaseSilver):
    __tablename__ = "silver_match_events"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    match_id = Column(Integer, ForeignKey("silver_matches.match_id"), nullable=False, index=True)
    team_id = Column(Integer, index=True)
    event_order = Column(Integer)
    game_minute = Column(Float)
    event_type_id = Column(Integer)
    event_type_name = Column(String)
    event_sub_type = Column(String)
    primary_player_id = Column(Integer, nullable=True)
    primary_player_name = Column(String, nullable=True)
    secondary_player_id = Column(Integer, nullable=True)
    secondary_player_name = Column(String, nullable=True)
    is_major = Column(Boolean, default=False)
    
    match = relationship("MatchSilver", back_populates="events")

class MatchLineupSilver(BaseSilver):
    __tablename__ = "silver_match_lineups"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    match_id = Column(Integer, ForeignKey("silver_matches.match_id"), nullable=False, index=True)
    team_id = Column(Integer, index=True)
    player_id = Column(Integer, index=True)
    player_name = Column(String)
    jersey_number = Column(Integer)
    status_text = Column(String)
    formation_line = Column(Integer, nullable=True)
    field_line = Column(Float, nullable=True)
    field_side = Column(Float, nullable=True)
    minutes_played = Column(Integer, nullable=True)
    fouls_committed = Column(Integer, nullable=True)
    fouls_received = Column(Integer, nullable=True)
    passes_completed = Column(Integer, nullable=True)
    key_passes = Column(Integer, nullable=True)
    xa = Column(Float, nullable=True)
    interceptions = Column(Integer, nullable=True)
    clearances = Column(Integer, nullable=True)
    
    match = relationship("MatchSilver", back_populates="lineups")

class MatchShotSilver(BaseSilver):
    __tablename__ = "silver_match_shots"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    match_id = Column(Integer, ForeignKey("silver_matches.match_id"), index=True)
    team_id = Column(Integer, index=True)
    player_id = Column(Integer, index=True)
    player_name = Column(String)
    shot_minute = Column(Float)
    xg = Column(Float)
    xgot = Column(Float)
    body_part = Column(String)
    goal_description = Column(String)
    outcome_name = Column(String)
    position_x = Column(Float)
    position_y = Column(Float)
    
    match = relationship("MatchSilver", back_populates="shots")