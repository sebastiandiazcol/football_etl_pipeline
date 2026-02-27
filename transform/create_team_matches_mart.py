import os
import sys
import sqlite3
import pandas as pd

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(base_dir)

from utils.logger import setup_logger

logger = setup_logger("CreateTeamMatchesMart")

def create_team_matches_mart():
    """
    Transforma la tabla fact_matches (1 fila = 1 partido) 
    en fact_team_matches (2 filas por partido: una para el local y otra para el visitante).
    Esto elimina la necesidad de DAX complejo en Power BI y resuelve relaciones ambiguas.
    """
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sqlite_db_path = os.path.join(base_dir, "data", "03_gold.db")
    
    logger.info(f"Conectando a {sqlite_db_path}...")
    conn = sqlite3.connect(sqlite_db_path)
    
    # Leer la tabla original de partidos
    try:
        df_matches = pd.read_sql("SELECT * FROM fact_matches", conn)
    except Exception as e:
        logger.error(f"Error leyendo fact_matches: {e}")
        return
        
    if df_matches.empty:
        logger.warning("La tabla fact_matches esta vacia. No hay nada que procesar.")
        return
        
    logger.info(f"Procesando {len(df_matches)} partidos para expandir a formato Team-Level (Unpivot)...")
    
    # ==========================================
    # 1. Crear la vista desde el Equipo LOCAL
    # ==========================================
    df_home = df_matches.copy()
    df_home['team_id'] = df_home['home_team_id']
    df_home['opponent_id'] = df_home['away_team_id']
    df_home['is_home'] = 1
    df_home['goals_for'] = df_home['home_score']
    df_home['goals_against'] = df_home['away_score']
    
    # ==========================================
    # 2. Crear la vista desde el Equipo VISITANTE
    # ==========================================
    df_away = df_matches.copy()
    df_away['team_id'] = df_away['away_team_id']
    df_away['opponent_id'] = df_matches['home_team_id'] # Usamos df_matches original para no cruzar mal
    df_away['is_home'] = 0
    df_away['goals_for'] = df_away['away_score']
    df_away['goals_against'] = df_away['home_score']
    
    # ==========================================
    # 3. Unir ambas vistas (Apilarlas)
    # ==========================================
    df_team_matches = pd.concat([df_home, df_away], ignore_index=True)
    
    # ==========================================
    # 4. Enriquecimiento: Calcular Puntos Ganados
    # ==========================================
    def calculate_points(row):
        if row['goals_for'] > row['goals_against']:
            return 3
        elif row['goals_for'] == row['goals_against']:
            return 1
        else:
            return 0
            
    df_team_matches['points'] = df_team_matches.apply(calculate_points, axis=1)
    
    # Resultado del partido (W: Win, D: Draw, L: Loss)
    def match_result(row):
        if row['goals_for'] > row['goals_against']: return 'W'
        elif row['goals_for'] == row['goals_against']: return 'D'
        else: return 'L'
        
    df_team_matches['match_result'] = df_team_matches.apply(match_result, axis=1)
    
    # ==========================================
    # 5. Limpieza Final
    # ==========================================
    # Quitamos las columnas viejas que causaban problemas en Power BI
    cols_to_drop = ['home_team_id', 'away_team_id', 'home_score', 'away_score']
    df_team_matches = df_team_matches.drop(columns=[col for col in cols_to_drop if col in df_team_matches.columns])
    
    # Ordenamos por fecha para que se vea bonito en la base de datos
    df_team_matches = df_team_matches.sort_values(by=['match_date', 'match_id'])
    
    # Guardar la nueva tabla maestra en SQLite
    df_team_matches.to_sql('fact_team_matches', conn, if_exists='replace', index=False)
    
    logger.info(f"Tabla fact_team_matches creada exitosamente con {len(df_team_matches)} filas.")
    conn.close()

if __name__ == "__main__":
    create_team_matches_mart()
