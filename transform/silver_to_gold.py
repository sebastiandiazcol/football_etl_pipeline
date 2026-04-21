# transform/silver_to_gold.py
# ETL Completo: Silver → Gold (Snowflake Schema para Power BI + Apuestas)
# Consolida 15 tablas en 7 tablas limpias.

import hashlib
import pandas as pd
from sqlalchemy.orm import Session
from sqlalchemy import text

from db.models.silver_models import (
    MatchSilver, MatchStatSilver, MatchShotSilver,
    MatchLineupSilver, MatchEventSilver
)
from db.models.gold_models import (
    DimTeam, DimPlayer, DimCompetition, DimReferee, DimDate,
    FactTeamMatch, FactPlayerMatch
)
from db.database import engine_gold, engine_silver
from utils.logger import setup_logger

logger = setup_logger("SilverToGold")

# ============================================================
# MAPEO DE NOMBRES DE ESTADÍSTICAS (API 365scores → Columnas Gold)
# ============================================================
STAT_MAP = {
    'Remates a Puerta':   'shots_on_target',
    'Remates Fuera':      'shots_off_target',
    'Saques de Esquina':  'corners',
    'Faltas':             'fouls',
    'Tarjetas Amarillas': 'yellow_cards',
    'Tarjetas Rojas':     'red_cards',
    'Posesión':           'possession',
}

PERIOD_MAP = {
    'Partido_Completo': '',      # sufijo vacío para FT
    'Primer_Tiempo':    '_ht',
    'Segundo_Tiempo':   '_2h',
}


class SilverToGoldETL:
    def __init__(self, db_silver: Session, db_gold: Session):
        self.db_silver = db_silver
        self.db_gold = db_gold

    # ===========================================================
    # DIMENSIONES
    # ===========================================================
    def _upsert_dimensions(self, match_silver: MatchSilver):
        """Upsert dim_team, dim_player, dim_competition, dim_referee para un partido."""
        # dim_competition
        if match_silver.competition_id:
            comp = self.db_gold.query(DimCompetition).filter_by(
                competition_id=match_silver.competition_id
            ).first()
            if not comp:
                self.db_gold.add(DimCompetition(
                    competition_id=match_silver.competition_id,
                    competition_name=match_silver.competition_name
                ))

        # dim_team
        for team_id, team_name in [
            (match_silver.home_team_id, match_silver.home_team_name),
            (match_silver.away_team_id, match_silver.away_team_name),
        ]:
            if team_id:
                team = self.db_gold.query(DimTeam).filter_by(team_id=team_id).first()
                if not team:
                    self.db_gold.add(DimTeam(team_id=team_id, team_name=team_name))

        # dim_player (de lineups, events, shots)
        match_id = match_silver.match_id
        player_dict = {}

        for l in self.db_silver.query(MatchLineupSilver).filter_by(match_id=match_id).all():
            if l.player_id:
                player_dict[l.player_id] = l.player_name

        for e in self.db_silver.query(MatchEventSilver).filter_by(match_id=match_id).all():
            if e.primary_player_id:
                player_dict[e.primary_player_id] = e.primary_player_name
            if e.secondary_player_id:
                player_dict[e.secondary_player_id] = e.secondary_player_name

        for s in self.db_silver.query(MatchShotSilver).filter_by(match_id=match_id).all():
            if s.player_id:
                player_dict[s.player_id] = s.player_name

        for p_id, p_name in player_dict.items():
            if not p_id or p_name == 'Unknown':
                continue
            player = self.db_gold.query(DimPlayer).filter_by(player_id=p_id).first()
            if not player:
                self.db_gold.add(DimPlayer(player_id=p_id, player_name=p_name))
            elif player.player_name == 'Unknown' or player.player_name != p_name:
                player.player_name = p_name

        self.db_gold.commit()

    # ===========================================================
    # PROCESO PRINCIPAL: Partido Completo Silver → Gold
    # ===========================================================
    def process_match_to_gold(self, match_id: int):
        """Procesa un partido de Silver a Gold: fact_team_match + fact_player_match."""
        match_s = self.db_silver.query(MatchSilver).filter_by(match_id=match_id).first()
        if not match_s:
            logger.error(f"[{match_id}] No se encontró el partido en Silver.")
            return

        try:
            # 1. Upsert dimensiones
            self._upsert_dimensions(match_s)

            # 2. Eliminar datos Gold previos de este partido
            self.db_gold.query(FactTeamMatch).filter_by(match_id=match_id).delete()
            self.db_gold.query(FactPlayerMatch).filter_by(match_id=match_id).delete()
            self.db_gold.commit()

            # 3. Construir fact_team_match (2 filas: home + away)
            self._build_fact_team_match(match_s)

            # 4. Construir fact_player_match
            self._build_fact_player_match(match_s)

            self.db_gold.commit()
            logger.info(f"[{match_id}] Migración a GOLD exitosa.")

        except Exception as e:
            self.db_gold.rollback()
            logger.error(f"Error migrando partido {match_id} a GOLD: {e}")
            import traceback
            logger.error(traceback.format_exc())

    # ===========================================================
    # FACT_TEAM_MATCH: Construir las 2 filas por partido
    # ===========================================================
    def _build_fact_team_match(self, match_s: MatchSilver):
        """Crea 2 filas en fact_team_match (home perspective + away perspective)."""
        match_id = match_s.match_id
        home_score = int(match_s.home_score) if match_s.home_score is not None else 0
        away_score = int(match_s.away_score) if match_s.away_score is not None else 0
        date_key = int(match_s.match_date.strftime('%Y%m%d')) if match_s.match_date else None

        # --- Referee ---
        referee_id = None
        if match_s.referee_name:
            referee_id = int(hashlib.md5(match_s.referee_name.encode()).hexdigest()[:8], 16)

        # --- Pivotar stats de los 3 periodos ---
        stats_dict = self._get_pivoted_stats(match_id)

        # --- xG del shotmap ---
        xg_home, xg_away = self._get_xg_from_shots(match_id, match_s.home_team_id, match_s.away_team_id)

        # --- Información de goles del primer/segundo tiempo (de stats goles o events) ---
        ht_goals = self._get_ht_goals(match_id, match_s.home_team_id, match_s.away_team_id, home_score, away_score)

        # --- Primer gol del partido ---
        first_goal_info = self._get_first_goal_info(match_id)

        # --- Construir base común ---
        base = {
            'match_id': match_id,
            'date_key': date_key,
            'competition_id': match_s.competition_id,
            'referee_id': referee_id,
            'season_num': match_s.season_num,
        }

        # --- Perspectiva HOME ---
        goals_ht_home_for = ht_goals['home_ht']
        goals_ht_home_against = ht_goals['away_ht']
        goals_2h_home_for = home_score - goals_ht_home_for
        goals_2h_home_against = away_score - goals_ht_home_against

        home_row = FactTeamMatch(
            **base,
            team_id=match_s.home_team_id,
            opponent_id=match_s.away_team_id,
            is_home=1,
            goals_for=home_score,
            goals_against=away_score,
            total_goals=home_score + away_score,
            goals_ht_for=goals_ht_home_for,
            goals_ht_against=goals_ht_home_against,
            total_goals_ht=goals_ht_home_for + goals_ht_home_against,
            goals_2h_for=goals_2h_home_for,
            goals_2h_against=goals_2h_home_against,
            total_goals_2h=goals_2h_home_for + goals_2h_home_against,
            **self._stats_for_team(stats_dict, match_s.home_team_id, match_s.away_team_id),
            xg_for=xg_home,
            xg_against=xg_away,
            overperformance=round(home_score - xg_home, 2),
            **self._betting_flags(home_score, away_score, goals_ht_home_for, goals_ht_home_against),
            **self._first_goal_flags(first_goal_info, match_s.home_team_id),
        )
        self.db_gold.add(home_row)

        # --- Perspectiva AWAY ---
        goals_ht_away_for = ht_goals['away_ht']
        goals_ht_away_against = ht_goals['home_ht']
        goals_2h_away_for = away_score - goals_ht_away_for
        goals_2h_away_against = home_score - goals_ht_away_against

        away_row = FactTeamMatch(
            **base,
            team_id=match_s.away_team_id,
            opponent_id=match_s.home_team_id,
            is_home=0,
            goals_for=away_score,
            goals_against=home_score,
            total_goals=home_score + away_score,
            goals_ht_for=goals_ht_away_for,
            goals_ht_against=goals_ht_away_against,
            total_goals_ht=goals_ht_away_for + goals_ht_away_against,
            goals_2h_for=goals_2h_away_for,
            goals_2h_against=goals_2h_away_against,
            total_goals_2h=goals_2h_away_for + goals_2h_away_against,
            **self._stats_for_team(stats_dict, match_s.away_team_id, match_s.home_team_id),
            xg_for=xg_away,
            xg_against=xg_home,
            overperformance=round(away_score - xg_away, 2),
            **self._betting_flags(away_score, home_score, goals_ht_away_for, goals_ht_away_against),
            **self._first_goal_flags(first_goal_info, match_s.away_team_id),
        )
        self.db_gold.add(away_row)

    # ===========================================================
    # PIVOTAR STATS: De filas (EAV) a columnas planas
    # ===========================================================
    def _get_pivoted_stats(self, match_id: int) -> dict:
        """
        Lee silver_match_stats y las pivotea en un dict:
        result[(team_id, period_suffix, stat_key)] = value
        """
        result = {}
        stats = self.db_silver.query(MatchStatSilver).filter_by(match_id=match_id).all()

        for s in stats:
            stat_key = STAT_MAP.get(s.stat_name)
            if not stat_key:
                continue
            period_suffix = PERIOD_MAP.get(s.period, '')
            val = s.value_numeric if s.value_numeric is not None else 0.0

            # Para posesión, quitar el % si viene como 55.0
            if stat_key == 'possession':
                val = float(val)

            result[(s.team_id, period_suffix, stat_key)] = val

        return result

    def _stats_for_team(self, stats_dict: dict, team_id: int, opponent_id: int) -> dict:
        """
        Retorna un dict con columnas de stats para un equipo (for/against) en los 3 periodos.
        """
        out = {}
        stat_keys = ['shots_on_target', 'shots_off_target', 'corners', 'fouls', 'yellow_cards', 'red_cards', 'possession']

        for period_suffix in ['', '_ht', '_2h']:
            for stat_key in stat_keys:
                val_for = stats_dict.get((team_id, period_suffix, stat_key), 0)
                val_against = stats_dict.get((opponent_id, period_suffix, stat_key), 0)

                if stat_key == 'possession':
                    col_name = f'possession{period_suffix}_for'
                    out[col_name] = float(val_for)
                else:
                    col_for = f'{stat_key}{period_suffix}_for'
                    col_against = f'{stat_key}{period_suffix}_against'
                    out[col_for] = int(val_for)
                    out[col_against] = int(val_against)

        # Total shots = on target + off target
        for period_suffix in ['', '_ht', '_2h']:
            sot_for = out.get(f'shots_on_target{period_suffix}_for', 0)
            soft_for = out.get(f'shots_off_target{period_suffix}_for', 0)
            sot_ag = out.get(f'shots_on_target{period_suffix}_against', 0)
            soft_ag = out.get(f'shots_off_target{period_suffix}_against', 0)
            out[f'total_shots{period_suffix}_for'] = sot_for + soft_for
            out[f'total_shots{period_suffix}_against'] = sot_ag + soft_ag

        return out

    # ===========================================================
    # xG del shotmap
    # ===========================================================
    def _get_xg_from_shots(self, match_id: int, home_id: int, away_id: int) -> tuple:
        """Suma xG por equipo desde silver_match_shots."""
        shots = self.db_silver.query(MatchShotSilver).filter_by(match_id=match_id).all()
        xg_home = sum(s.xg or 0 for s in shots if s.team_id == home_id)
        xg_away = sum(s.xg or 0 for s in shots if s.team_id == away_id)
        return round(xg_home, 2), round(xg_away, 2)

    # ===========================================================
    # Goles del Primer Tiempo
    # ===========================================================
    def _get_ht_goals(self, match_id, home_id, away_id, home_ft, away_ft) -> dict:
        """
        Obtiene goles del primer tiempo. Intentamos deducirlos de eventos (goles con minuto <= 45).
        Si no hay eventos, intentamos de stats ('Goles' del periodo 'Primer_Tiempo').
        """
        # Intentar desde events
        events = self.db_silver.query(MatchEventSilver).filter_by(match_id=match_id).all()
        goal_events = [e for e in events if e.event_type_name and 'gol' in e.event_type_name.lower()
                       and e.event_sub_type and 'gol' in e.event_sub_type.lower()
                       and (e.game_minute or 0) <= 50]
        
        if goal_events:
            home_ht = sum(1 for e in goal_events if e.team_id == home_id)
            away_ht = sum(1 for e in goal_events if e.team_id == away_id)
            return {'home_ht': home_ht, 'away_ht': away_ht}

        # Fallback: stats del Primer_Tiempo → Goles
        stats = self.db_silver.query(MatchStatSilver).filter_by(
            match_id=match_id, period='Primer_Tiempo'
        ).all()
        
        goles_stats = [s for s in stats if s.stat_name and 'gol' in s.stat_name.lower()]
        if goles_stats:
            home_ht = int(next((s.value_numeric for s in goles_stats if s.team_id == home_id), 0) or 0)
            away_ht = int(next((s.value_numeric for s in goles_stats if s.team_id == away_id), 0) or 0)
            return {'home_ht': home_ht, 'away_ht': away_ht}

        # Si no hay info, retornamos 0
        return {'home_ht': 0, 'away_ht': 0}

    # ===========================================================
    # Primer Gol del Partido
    # ===========================================================
    def _get_first_goal_info(self, match_id: int) -> dict:
        """Busca el primer gol del partido en events."""
        events = self.db_silver.query(MatchEventSilver).filter_by(match_id=match_id).all()
        goal_events = sorted(
            [e for e in events if e.event_type_name and 'gol' in e.event_type_name.lower()
             and e.event_sub_type and 'gol' in e.event_sub_type.lower()],
            key=lambda e: (e.game_minute or 999, e.event_order or 999)
        )

        if goal_events:
            first = goal_events[0]
            return {
                'team_id': first.team_id,
                'minute': first.game_minute
            }
        return {'team_id': None, 'minute': None}

    def _first_goal_flags(self, first_goal_info: dict, team_id: int) -> dict:
        """Retorna scored_first, conceded_first, first_goal_minute."""
        fg_team = first_goal_info.get('team_id')
        fg_minute = first_goal_info.get('minute')

        if fg_team is None:
            return {'scored_first': 0, 'conceded_first': 0, 'first_goal_minute': None}
        
        return {
            'scored_first': 1 if fg_team == team_id else 0,
            'conceded_first': 0 if fg_team == team_id else 1,
            'first_goal_minute': fg_minute,
        }

    # ===========================================================
    # FLAGS DE APUESTAS
    # ===========================================================
    def _betting_flags(self, goals_for, goals_against, ht_for, ht_against) -> dict:
        """Calcula todos los mercados de apuestas (FT + HT)."""
        total = goals_for + goals_against
        total_ht = ht_for + ht_against

        # 1X2 FT
        if goals_for > goals_against:
            result, points, win, draw_flag, loss_flag = 'W', 3, 1, 0, 0
        elif goals_for == goals_against:
            result, points, win, draw_flag, loss_flag = 'D', 1, 0, 1, 0
        else:
            result, points, win, draw_flag, loss_flag = 'L', 0, 0, 0, 1

        # 1X2 HT
        if ht_for > ht_against:
            result_ht = 'W'
        elif ht_for == ht_against:
            result_ht = 'D'
        else:
            result_ht = 'L'

        return {
            'match_result': result,
            'points': points,
            'win': win,
            'draw': draw_flag,
            'loss': loss_flag,
            'is_btts': 1 if goals_for > 0 and goals_against > 0 else 0,
            'is_over_0_5': 1 if total > 0 else 0,
            'is_over_1_5': 1 if total > 1 else 0,
            'is_over_2_5': 1 if total > 2 else 0,
            'is_over_3_5': 1 if total > 3 else 0,
            'is_over_4_5': 1 if total > 4 else 0,
            'clean_sheet': 1 if goals_against == 0 else 0,
            'result_ht': result_ht,
            'is_btts_ht': 1 if ht_for > 0 and ht_against > 0 else 0,
            'is_over_0_5_ht': 1 if total_ht > 0 else 0,
            'is_over_1_5_ht': 1 if total_ht > 1 else 0,
            'clean_sheet_ht': 1 if ht_against == 0 else 0,
        }

    # ===========================================================
    # FACT_PLAYER_MATCH: Players Props
    # ===========================================================
    def _build_fact_player_match(self, match_s: MatchSilver):
        """Construye fact_player_match: lineups + shots agregados."""
        match_id = match_s.match_id
        date_key = int(match_s.match_date.strftime('%Y%m%d')) if match_s.match_date else None

        # -- Lineups base --
        lineups = self.db_silver.query(MatchLineupSilver).filter_by(match_id=match_id).all()

        # -- Shots agregados por jugador --
        shots = self.db_silver.query(MatchShotSilver).filter_by(match_id=match_id).all()
        shots_agg = {}
        for s in shots:
            if not s.player_id:
                continue
            if s.player_id not in shots_agg:
                shots_agg[s.player_id] = {'total_shots': 0, 'sot': 0, 'goals': 0, 'xg': 0.0}
            shots_agg[s.player_id]['total_shots'] += 1
            if s.outcome_name and s.outcome_name.lower() in ('gol', 'goal', 'atajado', 'saved', 'poste'):
                shots_agg[s.player_id]['sot'] += 1
            if s.outcome_name and s.outcome_name.lower() in ('gol', 'goal'):
                shots_agg[s.player_id]['goals'] += 1
            shots_agg[s.player_id]['xg'] += (s.xg or 0)

        # -- Construir filas --
        for l in lineups:
            if not l.player_id:
                continue

            shot_data = shots_agg.get(l.player_id, {'total_shots': 0, 'sot': 0, 'goals': 0, 'xg': 0.0})

            is_home = 1 if l.team_id == match_s.home_team_id else 0
            is_starter = 1 if l.status_text and l.status_text.lower() == 'starting' else 0

            row = FactPlayerMatch(
                match_id=match_id,
                date_key=date_key,
                player_id=l.player_id,
                team_id=l.team_id,
                jersey_number=l.jersey_number,
                is_home=is_home,
                is_starter=is_starter,
                minutes_played=l.minutes_played or 0,
                goals=shot_data['goals'],
                total_shots=shot_data['total_shots'],
                shots_on_target=shot_data['sot'],
                xg=round(shot_data['xg'], 2),
                passes_completed=l.passes_completed or 0,
                key_passes=l.key_passes or 0,
                xa=l.xa or 0.0,
                fouls_committed=l.fouls_committed or 0,
                fouls_received=l.fouls_received or 0,
                interceptions=l.interceptions or 0,
                clearances=l.clearances or 0,
            )
            self.db_gold.add(row)


# ============================================================
# POST-PROCESAMIENTO: Rolling Averages + dim_referee + dim_date
# (Se ejecuta después de cargar TODOS los partidos)
# ============================================================

def compute_rolling_averages():
    """
    Calcula rolling averages para fact_team_match y fact_player_match.
    Se ejecuta una sola vez sobre toda la base de Gold.
    Lee con Pandas, calcula rolling, y escribe de vuelta.
    """
    logger.info("Calculando Rolling Averages...")

    # ============ fact_team_match ============
    df_team = pd.read_sql("SELECT * FROM fact_team_match ORDER BY team_id, date_key", con=engine_gold)

    if not df_team.empty:
        df_team = df_team.sort_values(by=['team_id', 'date_key', 'match_id'])

        roll_cols_team = {
            'goals_for': ['goals_for_roll3', 'goals_for_roll5'],
            'goals_against': ['goals_against_roll3', 'goals_against_roll5'],
            'xg_for': ['xg_for_roll3', 'xg_for_roll5'],
            'shots_on_target_for': ['shots_on_target_for_roll3', None],
            'total_shots_for': ['total_shots_for_roll3', None],
            'corners_for': ['corners_for_roll3', None],
        }

        for src_col, (roll3_col, roll5_col) in roll_cols_team.items():
            if src_col in df_team.columns:
                df_team[roll3_col] = df_team.groupby('team_id')[src_col].transform(
                    lambda x: x.shift(1).rolling(3, min_periods=1).mean()
                )
                if roll5_col:
                    df_team[roll5_col] = df_team.groupby('team_id')[src_col].transform(
                        lambda x: x.shift(1).rolling(5, min_periods=1).mean()
                    )

        df_team = df_team.fillna(0)
        df_team = df_team.round(2)

        # Escribir de vuelta - DELETE+APPEND para preservar estructura e indices
        with engine_gold.begin() as conn:
            conn.execute(text("DELETE FROM fact_team_match"))
        df_team.to_sql('fact_team_match', con=engine_gold, if_exists='append', index=False)
        logger.info(f"  fact_team_match: {len(df_team)} filas con rolling averages.")

    # ============ fact_player_match ============
    df_player = pd.read_sql("SELECT * FROM fact_player_match ORDER BY player_id, date_key", con=engine_gold)

    if not df_player.empty:
        df_player = df_player.sort_values(by=['player_id', 'date_key', 'match_id'])

        roll_cols_player = {
            'goals': ['goals_roll3', 'goals_roll5'],
            'total_shots': ['total_shots_roll3', 'total_shots_roll5'],
            'shots_on_target': ['sot_roll3', 'sot_roll5'],
            'key_passes': ['key_passes_roll3', None],
            'fouls_committed': ['fouls_committed_roll3', None],
            'passes_completed': ['passes_completed_roll3', None],
        }

        for src_col, (roll3_col, roll5_col) in roll_cols_player.items():
            if src_col in df_player.columns:
                df_player[roll3_col] = df_player.groupby('player_id')[src_col].transform(
                    lambda x: x.shift(1).rolling(3, min_periods=1).mean()
                )
                if roll5_col:
                    df_player[roll5_col] = df_player.groupby('player_id')[src_col].transform(
                        lambda x: x.shift(1).rolling(5, min_periods=1).mean()
                    )

        df_player = df_player.fillna(0)
        df_player = df_player.round(2)

        # DELETE+APPEND para preservar estructura e indices
        with engine_gold.begin() as conn:
            conn.execute(text("DELETE FROM fact_player_match"))
        df_player.to_sql('fact_player_match', con=engine_gold, if_exists='append', index=False)
        logger.info(f"  fact_player_match: {len(df_player)} filas con rolling averages.")


def compute_dim_referee():
    """Calcula dim_referee a partir de fact_team_match."""
    logger.info("Calculando dim_referee...")

    df = pd.read_sql("SELECT * FROM fact_team_match WHERE referee_id IS NOT NULL", con=engine_gold)
    if df.empty:
        logger.info("  No hay datos con referee_id.")
        return

    # Necesitamos el nombre del árbitro desde Silver
    df_matches = pd.read_sql("SELECT match_id, referee_name FROM silver_matches WHERE referee_name IS NOT NULL", con=engine_silver)
    df = df.merge(df_matches, on='match_id', how='left')

    agg = df.groupby('referee_id').agg(
        referee_name=('referee_name', 'first'),
        matches_refereed=('match_id', 'nunique'),
        total_yellow_cards=('yellow_cards_for', 'sum'),
        total_red_cards=('red_cards_for', 'sum'),
    ).reset_index()

    agg['avg_yellow_cards'] = (agg['total_yellow_cards'] / agg['matches_refereed']).round(2)
    agg['avg_red_cards'] = (agg['total_red_cards'] / agg['matches_refereed']).round(2)

    # DELETE+APPEND para preservar estructura e indices
    with engine_gold.begin() as conn:
        conn.execute(text("DELETE FROM dim_referee"))
    agg.to_sql('dim_referee', con=engine_gold, if_exists='append', index=False)
    logger.info(f"  dim_referee: {len(agg)} arbitros.")


def generate_dim_date(start_year=2020, end_year=2030):
    """Genera la dimensión calendario (dim_date)."""
    logger.info("Generando dim_date...")

    df = pd.DataFrame({"date": pd.date_range(f"{start_year}-01-01", f"{end_year}-12-31")})
    df["date_key"] = df["date"].dt.strftime('%Y%m%d').astype(int)
    df["date_actual"] = df["date"].dt.date
    df["year"] = df["date"].dt.year
    df["quarter"] = df["date"].dt.quarter
    df["month"] = df["date"].dt.month

    meses = {1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril', 5: 'Mayo', 6: 'Junio',
             7: 'Julio', 8: 'Agosto', 9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre'}
    dias = {0: 'Lunes', 1: 'Martes', 2: 'Miercoles', 3: 'Jueves', 4: 'Viernes', 5: 'Sabado', 6: 'Domingo'}

    df["month_name"] = df["month"].map(meses)
    df["day"] = df["date"].dt.day
    df["day_name"] = df["date"].dt.dayofweek.map(dias)
    df["is_weekend"] = df["date"].dt.dayofweek.isin([5, 6]).astype(int)

    df = df[["date_key", "date_actual", "year", "quarter", "month", "month_name", "day", "day_name", "is_weekend"]]
    # DELETE+APPEND para preservar estructura e indices
    with engine_gold.begin() as conn:
        conn.execute(text("DELETE FROM dim_date"))
    df.to_sql("dim_date", con=engine_gold, if_exists="append", index=False)
    logger.info(f"  dim_date: {len(df)} registros ({start_year}-{end_year}).")