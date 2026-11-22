# db/database.py
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.ext.declarative import declarative_base

# 1. Rutas absolutas para que funcione desde cualquier directorio o Web App
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

# 2. URLs de las tres bases de datos (SQLite locales)
bronze_path = os.path.join(DATA_DIR, "01_bronze.db").replace('\\', '/')
silver_path = os.path.join(DATA_DIR, "02_silver.db").replace('\\', '/')
gold_path   = os.path.join(DATA_DIR, "03_gold.db").replace('\\', '/')

BRONZE_DB_URL = f"sqlite:///{bronze_path}"
SILVER_DB_URL = f"sqlite:///{silver_path}"
GOLD_DB_URL   = f"sqlite:///{gold_path}"

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