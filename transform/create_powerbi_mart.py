import sys
import os

# Añadir el directorio raíz al path para poder importar 'db'
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pandas as pd
from db.database import engine_gold

def create_powerbi_mart():
    """
    Crea un Data Mart para PowerBI enfocado en propiedades de jugadores, 
    cruzando estadísticas de tiros, minutos jugados y detalles del partido.
    """
    # 1. Extracción
    # Se leen las tablas necesarias directamente de la capa Gold
    df_shots = pd.read_sql("SELECT * FROM fact_shots", con=engine_gold)
    df_lineups = pd.read_sql("SELECT * FROM fact_lineups", con=engine_gold)
    df_players = pd.read_sql("SELECT * FROM dim_players", con=engine_gold)
    df_matches = pd.read_sql("SELECT * FROM fact_matches", con=engine_gold)
    df_teams = pd.read_sql("SELECT * FROM dim_teams", con=engine_gold)

    if df_shots.empty or df_lineups.empty or df_matches.empty:
        print("Faltan datos en las tablas de Gold. Por favor asegúrate de haber poblado las tablas previamente.")
        return

    # 2 & 3. Agregación de Tiros
    # Determinamos condicionalmente si es un tiro a puerta y si es gol
    # Los nombres pueden variar ('Gol', 'Goal', 'Atajado', 'Saved', etc.), los adaptamos a las descripciones más comunes
    df_shots['is_shot_on_target'] = df_shots['outcome_name'].isin(['Gol', 'Goal', 'Atajado', 'Saved', 'Poste']).astype(int)
    df_shots['is_goal'] = df_shots['outcome_name'].isin(['Gol', 'Goal']).astype(int)
    
    # Agrupamos por match_id y player_id
    shots_agg = df_shots.groupby(['match_id', 'player_id']).agg(
        total_shots=('id', 'count'),
        shots_on_target=('is_shot_on_target', 'sum'),
        goals=('is_goal', 'sum'),
        total_xg=('xg', 'sum')
    ).reset_index()

    # 4. Cruce Base (Merge)
    # Tabla principal (lineups/minutos) + Tabla secundaria (tiros)
    df_base = pd.merge(df_lineups, shots_agg, on=['match_id', 'player_id'], how='left')
    
    # Rellenar nulos con 0 para los jugadores que no realizaron tiros
    fill_cols = ['total_shots', 'shots_on_target', 'goals', 'total_xg', 'fouls_committed', 'fouls_received', 'passes_completed', 'key_passes', 'xa', 'interceptions', 'clearances']
    df_base[fill_cols] = df_base[fill_cols].fillna(0)

    # 5. Enriquecimiento (Contexto)
    # Primero enriquecemos partidos para traer 'home_team' y 'away_team' basados en el ID
    df_matches_enrich = pd.merge(df_matches, df_teams.rename(columns={'team_id': 'home_team_id', 'team_name': 'home_team'}), on='home_team_id', how='left')
    df_matches_enrich = pd.merge(df_matches_enrich, df_teams.rename(columns={'team_id': 'away_team_id', 'team_name': 'away_team'}), on='away_team_id', how='left')
    
    # JOIN con la tabla de partidos para traer match_date, home_team, away_team
    cols_partidos = ['match_id', 'match_date', 'home_team', 'away_team']
    df_base = pd.merge(df_base, df_matches_enrich[cols_partidos], on='match_id', how='left')

    # JOIN con la tabla de jugadores para traer el nombre
    df_base = pd.merge(df_base, df_players[['player_id', 'player_name']], on='player_id', how='left')
    
    # JOIN con la tabla de equipos para traer el team_name al que pertenece el jugador en ese partido
    df_base = pd.merge(df_base, df_teams[['team_id', 'team_name']], on='team_id', how='left')

    # 6. Ingeniería de Características (Features)
    # Crea una nueva columna is_home que evalúe si el equipo del jugador es igual al equipo local
    df_base['is_home'] = (df_base['team_name'] == df_base['home_team']).astype(int)
    
    # Crea un booleano para los jugadores titulares
    df_base['is_starter'] = (df_base['status_text'].str.lower() == 'starting').astype(int)

    # 7. Carga
    # Selecciona solo las columnas útiles y renombra/ordena
    col_seleccionadas = [
        'match_id', 'match_date', 'player_name', 'team_name', 
        'home_team', 'away_team', 'is_home', 'is_starter', 'minutes_played', 
        'fouls_committed', 'fouls_received', 'passes_completed',
        'key_passes', 'xa', 'interceptions', 'clearances',
        'total_shots', 'shots_on_target', 'goals', 'total_xg'
    ]
    df_final = df_base[col_seleccionadas]
    
    # Guárdalo como una nueva tabla física llamada powerbi_mart_player_props en 03_gold.db
    # usando if_exists='replace'
    df_final.to_sql('powerbi_mart_player_props', con=engine_gold, if_exists='replace', index=False)
    print(f"Tabla powerbi_mart_player_props cargada exitosamente en 03_gold.db. Total de filas: {len(df_final)}")

if __name__ == "__main__":
    create_powerbi_mart()
