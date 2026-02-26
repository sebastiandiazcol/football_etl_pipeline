# transform/create_betting_facts.py
import sqlite3
import pandas as pd
import numpy as np

def create_betting_tables(db_path="data/03_gold.db"):
    print("Iniciando ingenieria de variables para Apuestas Deportivas...")
    con = sqlite3.connect(db_path)
    
    # ==========================================
    # 1. CONSTRUCCIÓN DE LA TABLA DE EQUIPOS
    # ==========================================
    
    # Extraer partidos base
    matches_query = """
    SELECT match_id, home_team_id, away_team_id, home_score, away_score, total_goals
    FROM fact_matches
    """
    df_matches = pd.read_sql(matches_query, con)
    
    # Extraer estadísticas y pivotearlas
    stats_query = """
    SELECT match_id, team_id, stat_name, value_numeric
    FROM fact_match_stats
    WHERE period = 'Partido_Completo'
    """
    df_stats = pd.read_sql(stats_query, con)
    
    # Diccionario de traduccion de estadisticas de 365Scores a estandar analitico
    stat_mapping = {
        'Tiros a puerta': 'shots_on_target',
        'Tiros fuera': 'shots_off_target',
        'Tiros de esquina': 'corners',
        'Tarjetas amarillas': 'yellow_cards',
        'Tarjetas rojas': 'red_cards',
        'Faltas': 'fouls',
        'Posesión del balón': 'possession'
    }
    
    df_stats['stat_mapped'] = df_stats['stat_name'].map(stat_mapping)
    df_stats = df_stats.dropna(subset=['stat_mapped'])
    
    # Pivotear: Convertir filas de estadisticas en columnas
    df_pivot = df_stats.pivot_table(
        index=['match_id', 'team_id'], 
        columns='stat_mapped', 
        values='value_numeric', 
        fill_value=0
    ).reset_index()
    
    # Preparar el DataFrame final de equipos desdoblando Local y Visitante
    team_records = []
    
    for _, row in df_matches.iterrows():
        match_id = row['match_id']
        home_id = row['home_team_id']
        away_id = row['away_team_id']
        
        # Logica Local
        team_records.append({
            'match_id': match_id, 'team_id': home_id, 'opponent_id': away_id,
            'is_home': 1, 'goals_for': row['home_score'], 'goals_conceded': row['away_score'],
            'total_goals': row['total_goals']
        })
        # Logica Visitante
        team_records.append({
            'match_id': match_id, 'team_id': away_id, 'opponent_id': home_id,
            'is_home': 0, 'goals_for': row['away_score'], 'goals_conceded': row['home_score'],
            'total_goals': row['total_goals']
        })
        
    df_betting_team = pd.DataFrame(team_records)
    
    # Unir las estadisticas "A Favor" (For)
    df_betting_team = pd.merge(df_betting_team, df_pivot, on=['match_id', 'team_id'], how='left')
    
    # Renombrar columnas a formato "_for"
    rename_for = {col: f"{col}_for" for col in stat_mapping.values()}
    df_betting_team.rename(columns=rename_for, inplace=True)
    
    # Unir las estadisticas "Concedidas" (Against) cruzando con el opponent_id
    df_pivot_against = df_pivot.rename(columns={'team_id': 'opponent_id'})
    rename_against = {col: f"{col}_conceded" for col in stat_mapping.values()}
    df_pivot_against.rename(columns=rename_against, inplace=True)
    
    df_betting_team = pd.merge(df_betting_team, df_pivot_against, on=['match_id', 'opponent_id'], how='left')
    
    # Rellenar nulos con 0 por si un equipo no hizo tiros o corners
    df_betting_team = df_betting_team.fillna(0)
    
    # CREACION DE BANDERAS DE MERCADOS DE APUESTAS (Booleanos 1 o 0)
    df_betting_team['is_btts'] = np.where((df_betting_team['goals_for'] > 0) & (df_betting_team['goals_conceded'] > 0), 1, 0)
    df_betting_team['is_over_1_5'] = np.where(df_betting_team['total_goals'] > 1.5, 1, 0)
    df_betting_team['is_over_2_5'] = np.where(df_betting_team['total_goals'] > 2.5, 1, 0)
    df_betting_team['is_over_3_5'] = np.where(df_betting_team['total_goals'] > 3.5, 1, 0)
    df_betting_team['win'] = np.where(df_betting_team['goals_for'] > df_betting_team['goals_conceded'], 1, 0)
    df_betting_team['draw'] = np.where(df_betting_team['goals_for'] == df_betting_team['goals_conceded'], 1, 0)
    df_betting_team['loss'] = np.where(df_betting_team['goals_for'] < df_betting_team['goals_conceded'], 1, 0)
    
    # ==========================================
    # 2. CONSTRUCCIÓN DE LA TABLA DE JUGADORES (PLAYER PROPS)
    # ==========================================
    
    shots_query = """
    SELECT match_id, team_id, player_id, outcome_name, xg
    FROM fact_shots
    """
    df_shots = pd.read_sql(shots_query, con)
    
    if not df_shots.empty:
        # Definir que es un tiro a puerta (SOT)
        sot_outcomes = ['Gol', 'Atajado'] # 365Scores clasifica atajadas y goles como tiros a puerta
        
        df_shots['is_shot'] = 1
        df_shots['is_sot'] = np.where(df_shots['outcome_name'].isin(sot_outcomes), 1, 0)
        df_shots['is_goal'] = np.where(df_shots['outcome_name'] == 'Gol', 1, 0)
        df_shots['xg'] = df_shots['xg'].fillna(0)
        
        # Agrupar por jugador y partido
        df_betting_player = df_shots.groupby(['match_id', 'team_id', 'player_id']).agg(
            total_shots=('is_shot', 'sum'),
            shots_on_target=('is_sot', 'sum'),
            goals_scored=('is_goal', 'sum'),
            total_xg=('xg', 'sum')
        ).reset_index()
    else:
        df_betting_player = pd.DataFrame(columns=['match_id', 'team_id', 'player_id', 'total_shots', 'shots_on_target', 'goals_scored', 'total_xg'])

    # ==========================================
    # 3. GUARDAR EN LA BASE DE DATOS
    # ==========================================
    
    df_betting_team.to_sql('fact_betting_team', con, if_exists='replace', index=False)
    df_betting_player.to_sql('fact_betting_player', con, if_exists='replace', index=False)
    
    # Indices para optimizar Power BI
    cursor = con.cursor()
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_bet_team_match ON fact_betting_team(match_id, team_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_bet_player_match ON fact_betting_player(match_id, player_id);")
    con.commit()
    con.close()
    
    print(f"Tablas de apuestas creadas exitosamente:")
    print(f"- fact_betting_team: {len(df_betting_team)} registros analizados.")
    print(f"- fact_betting_player: {len(df_betting_player)} actuaciones de jugadores analizadas.")

if __name__ == "__main__":
    create_betting_tables()