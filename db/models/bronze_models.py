# db/models/bronze_models.py
from sqlalchemy import Column, Integer, String, DateTime, Text
from datetime import datetime
from db.database import BaseBronze

class RawMatchData(BaseBronze):
    __tablename__ = "raw_match_data"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    match_id = Column(String, index=True, nullable=False) # ID del partido de 365Scores
    endpoint_source = Column(String) # Ej: "game_details" o "stats"
    raw_json = Column(Text, nullable=False) # El JSON crudo guardado como texto
    scraped_at = Column(DateTime, default=datetime.utcnow)
    processed_to_silver = Column(Integer, default=0) # 0 = No, 1 = Sí (Para control del ETL)