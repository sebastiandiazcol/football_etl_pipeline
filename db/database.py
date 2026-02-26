# db/database.py
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.ext.declarative import declarative_base

# 1. Asegurarnos de que exista la carpeta data/
os.makedirs("data", exist_ok=True)

# 2. URLs de las tres bases de datos (SQLite locales)
BRONZE_DB_URL = "sqlite:///data/01_bronze.db"
SILVER_DB_URL = "sqlite:///data/02_silver.db"
GOLD_DB_URL   = "sqlite:///data/03_gold.db"

# 3. Creación de los Engines
engine_bronze = create_engine(BRONZE_DB_URL, echo=False)
engine_silver = create_engine(SILVER_DB_URL, echo=False)
engine_gold   = create_engine(GOLD_DB_URL, echo=False)

# 4. Creación de las Sesiones
SessionBronze = scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=engine_bronze))
SessionSilver = scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=engine_silver))
SessionGold   = scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=engine_gold))

# 5. Bases Declarativas independientes para evitar colisiones de tablas
BaseBronze = declarative_base()
BaseSilver = declarative_base()
BaseGold   = declarative_base()

def init_db():
    """Inicializa las tablas en todas las capas si no existen."""
    import db.models.bronze_models
    import db.models.silver_models
    import db.models.gold_models
    
    BaseBronze.metadata.create_all(bind=engine_bronze)
    BaseSilver.metadata.create_all(bind=engine_silver)
    BaseGold.metadata.create_all(bind=engine_gold)