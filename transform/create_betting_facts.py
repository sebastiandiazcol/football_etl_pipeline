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
    
    # Rellenar nulos de partido completo
    df_betting_team = df_betting_team.fillna(0)
    
    # === DATOS HT (Primer Tiempo) ===
    stats_ht_query = "SELECT match_id, team_id, stat_name, value_numeric FROM fact_match_stats WHERE period = 'Primer_Tiempo'"
    df_stats_ht = pd.read_sql(stats_ht_query, con)
    df_stats_ht['stat_mapped'] = df_stats_ht['stat_name'].map(stat_mapping)
    df_stats_ht = df_stats_ht.dropna(subset=['stat_mapped'])
    df_pivot_ht = df_stats_ht.pivot_table(index=['match_id', 'team_id'], columns='stat_mapped', values='value_numeric', fill_value=0).reset_index()
    
    rename_ht_for = {col: f"{col}_ht_for" for col in stat_mapping.values()}
    df_pivot_ht_for = df_pivot_ht.rename(columns=rename_ht_for)
    df_betting_team = pd.merge(df_betting_team, df_pivot_ht_for, on=['match_id', 'team_id'], how='left')
    
    rename_ht_against = {col: f"{col}_ht_conceded" for col in stat_mapping.values()}
    df_pivot_ht_against = df_pivot_ht.rename(columns={'team_id': 'opponent_id'})
    df_pivot_ht_against.rename(columns=rename_ht_against, inplace=True)
    df_betting_team = pd.merge(df_betting_team, df_pivot_ht_against, on=['match_id', 'opponent_id'], how='left')
    
    # === GOLES (HT) y FIRST TO SCORE ===
    events_goals_query = "SELECT match_id, team_id, game_minute FROM fact_events WHERE event_type_name = 'Gol'"
    df_goals = pd.read_sql(events_goals_query, con)
    
    df_goals_ht = df_goals[df_goals['game_minute'] <= 50].groupby(['match_id', 'team_id']).size().reset_index(name='goals_ht_for')
    df_betting_team = pd.merge(df_betting_team, df_goals_ht, on=['match_id', 'team_id'], how='left')
    
    df_goals_ht_against = df_goals_ht.rename(columns={'team_id': 'opponent_id', 'goals_ht_for': 'goals_ht_conceded'})
    df_betting_team = pd.merge(df_betting_team, df_goals_ht_against, on=['match_id', 'opponent_id'], how='left')
    
    df_first_goal = df_goals.sort_values(by=['match_id', 'game_minute']).groupby('match_id').first().reset_index()
    df_first_goal = df_first_goal.rename(columns={'team_id': 'first_goal_team_id', 'game_minute': 'first_goal_minute'})
    df_betting_team = pd.merge(df_betting_team, df_first_goal[['match_id', 'first_goal_team_id', 'first_goal_minute']], on='match_id', how='left')
    
    df_betting_team['scored_first'] = np.where((df_betting_team['first_goal_team_id'] == df_betting_team['team_id']), 1, 0)
    df_betting_team['conceded_first'] = np.where((df_betting_team['first_goal_team_id'] == df_betting_team['opponent_id']), 1, 0)
    
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
    # 3. CONSTRUCCIÓN DE LA TABLA DE ÁRBITROS (REFEREE STATS)
    # ==========================================
    
    referee_query = """
    SELECT match_id, match_date, referee_name, home_team_id, away_team_id
    FROM fact_matches
    WHERE referee_name IS NOT NULL
    """
    df_referees = pd.read_sql(referee_query, con)
    
    events_query = """
    SELECT match_id, event_type_name
    FROM fact_events
    WHERE event_type_name IN ('Tarjeta amarilla', 'Tarjeta roja')
    """
    df_events = pd.read_sql(events_query, con)
    df_events['is_yellow'] = np.where(df_events['event_type_name'] == 'Tarjeta amarilla', 1, 0)
    df_events['is_red'] = np.where(df_events['event_type_name'] == 'Tarjeta roja', 1, 0)
    
    df_cards = df_events.groupby('match_id').agg(
        yellow_cards=('is_yellow', 'sum'),
        red_cards=('is_red', 'sum')
    ).reset_index()
    
    df_ref_matches = pd.merge(df_referees, df_cards, on='match_id', how='left').fillna(0)
    
    # Agrupar por arbitro para obtener el promedio
    df_mart_referee = df_ref_matches.groupby('referee_name').agg(
        matches_refereed=('match_id', 'count'),
        avg_yellow_cards=('yellow_cards', 'mean'),
        avg_red_cards=('red_cards', 'mean'),
        total_yellow_cards=('yellow_cards', 'sum'),
        total_red_cards=('red_cards', 'sum')
    ).reset_index()
    
    # ==========================================
    # 4. CONSTRUCCIÓN DE LA TABLA DE TENDENCIAS (ROLLING AVERAGES)
    # ==========================================
    
    # Ordenar los partidos por fecha
    df_betting_team_sorted = pd.merge(
        df_betting_team, 
        df_matches[['match_id']], 
        on='match_id'
    )
    # Necesitamos la fecha del partido para ordenar correctamente (unimos con fact_matches)
    matches_dates = pd.read_sql("SELECT match_id, match_date FROM fact_matches", con)
    df_betting_team_sorted = pd.merge(df_betting_team_sorted, matches_dates, on='match_id', how='left')
    df_betting_team_sorted['match_date'] = pd.to_datetime(df_betting_team_sorted['match_date'])
    df_betting_team_sorted = df_betting_team_sorted.sort_values(by=['team_id', 'match_date'])
    
    # Calcular promedios moviles (últimos 3 y 5 partidos)
    # Como queremos predecir, el rolling debe estar desplazado en 1 (shift) para no incluir el partido actual
    rolling_cols = ['goals_for', 'goals_conceded', 'corners_for', 'corners_conceded', 'shots_on_target_for']
    
    # Filtrar solo si existen (depende de los datos extraidos)
    rolling_cols = [c for c in rolling_cols if c in df_betting_team_sorted.columns]
    
    df_trends = df_betting_team_sorted[['match_id', 'team_id', 'match_date']].copy()
    
    for col in rolling_cols:
        # Últimos 3 partidos
        df_trends[f'{col}_roll3'] = df_betting_team_sorted.groupby('team_id')[col].transform(lambda x: x.shift(1).rolling(3, min_periods=1).mean())
        # Últimos 5 partidos
        df_trends[f'{col}_roll5'] = df_betting_team_sorted.groupby('team_id')[col].transform(lambda x: x.shift(1).rolling(5, min_periods=1).mean())
    
    df_trends = df_trends.fillna(0)
    
    # ==========================================
    # 5. GUARDAR EN LA BASE DE DATOS
    # ==========================================
    
    df_betting_team.to_sql('fact_betting_team', con, if_exists='replace', index=False)
    df_betting_player.to_sql('fact_betting_player', con, if_exists='replace', index=False)
    df_mart_referee.to_sql('mart_referee_stats', con, if_exists='replace', index=False)
    df_trends.to_sql('mart_betting_trends', con, if_exists='replace', index=False)
    
    # Indices para optimizar Power BI
    cursor = con.cursor()
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_bet_team_match ON fact_betting_team(match_id, team_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_bet_player_match ON fact_betting_player(match_id, player_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_trends_match ON mart_betting_trends(match_id, team_id);")
    con.commit()
    con.close()
    
    print(f"Tablas de apuestas creadas exitosamente:")
    print(f"- fact_betting_team: {len(df_betting_team)} registros analizados.")
    print(f"- fact_betting_player: {len(df_betting_player)} actuaciones de jugadores.")
    print(f"- mart_referee_stats: {len(df_mart_referee)} árbitros promediados.")
    print(f"- mart_betting_trends: Promedios móviles calculados.")

if __name__ == "__main__":
    create_betting_tables()