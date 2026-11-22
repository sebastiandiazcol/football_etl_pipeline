# analysis/probabilities.py
"""
Módulo de Cálculo de Probabilidades Estadísticas Puras para Fútbol.
Implementa:
- Modelo de Poisson y Matriz Bivariada de Marcadores
- Probabilidades de Mercados 1X2, Over/Under, BTTS y Doble Oportunidad
- Cálculo de Cuotas Justas Matemáticas (Fair Odds = 1 / P)
- Estadísticas Frecuentistas y Descriptivas (medias, varianzas, proporciones empíricas)
- Análisis de Props de Jugadores (tiros a puerta, faltas, tarjetas)
"""

import math
from typing import Dict, List, Tuple, Optional, Any
import numpy as np
import pandas as pd


def poisson_pmf(k: int, lam: float) -> float:
    """Calcula la probabilidad de observar k ocurrencias bajo Poisson(lam)."""
    if lam <= 0:
        return 1.0 if k == 0 else 0.0
    return (math.pow(lam, k) * math.exp(-lam)) / math.factorial(k)


def calculate_fair_odd(prob: float, min_odd: float = 1.01, max_odd: float = 100.0) -> float:
    """Calcula la cuota justa matemática (1 / P), acotada para visualización."""
    if prob <= 0:
        return max_odd
    odd = 1.0 / prob
    return round(min(max(odd, min_odd), max_odd), 2)


def compute_poisson_match_probabilities(
    lambda_home: float,
    lambda_away: float,
    max_goals: int = 7
) -> Dict[str, Any]:
    """
    Calcula la matriz completa de probabilidades exactas y mercados derivados
    mediante el modelo clásico de distribución de Poisson.
    """
    lambda_home = max(float(lambda_home), 0.1)
    lambda_away = max(float(lambda_away), 0.1)

    # 1. Matriz de probabilidades de marcador (X, Y)
    matrix = np.zeros((max_goals + 1, max_goals + 1))
    for x in range(max_goals + 1):
        p_x = poisson_pmf(x, lambda_home)
        for y in range(max_goals + 1):
            p_y = poisson_pmf(y, lambda_away)
            matrix[x, y] = p_x * p_y

    # Normalizar para que la matriz sume exactamente 1.0 considerando la cola
    total_prob = matrix.sum()
    if total_prob > 0:
        matrix = matrix / total_prob

    # 2. Probabilidades 1X2
    p_home_win = float(np.sum(np.tril(matrix, -1)))
    p_draw = float(np.sum(np.diag(matrix)))
    p_away_win = float(np.sum(np.triu(matrix, 1)))

    # 3. Mercados Over / Under
    ou_lines = [0.5, 1.5, 2.5, 3.5, 4.5]
    ou_results = {}
    for line in ou_lines:
        over_p = 0.0
        for x in range(max_goals + 1):
            for y in range(max_goals + 1):
                if (x + y) > line:
                    over_p += matrix[x, y]
        under_p = max(1.0 - over_p, 0.0)
        ou_results[f"Over {line}"] = {
            "prob": round(float(over_p) * 100, 1),
            "fair_odd": calculate_fair_odd(float(over_p))
        }
        ou_results[f"Under {line}"] = {
            "prob": round(float(under_p) * 100, 1),
            "fair_odd": calculate_fair_odd(float(under_p))
        }

    # 4. Ambos Equipos Marcan (BTTS)
    p_home_scores = 1.0 - poisson_pmf(0, lambda_home)
    p_away_scores = 1.0 - poisson_pmf(0, lambda_away)
    p_btts_yes = float(p_home_scores * p_away_scores)
    p_btts_no = max(1.0 - p_btts_yes, 0.0)

    # 5. Doble Oportunidad
    p_1x = p_home_win + p_draw
    p_12 = p_home_win + p_away_win
    p_x2 = p_draw + p_away_win

    # 6. Marcadores más probables
    scores_list = []
    for x in range(min(max_goals + 1, 5)):
        for y in range(min(max_goals + 1, 5)):
            p = float(matrix[x, y])
            scores_list.append({
                "score": f"{x} - {y}",
                "prob": round(p * 100, 1),
                "fair_odd": calculate_fair_odd(p)
            })
    scores_list = sorted(scores_list, key=lambda s: s["prob"], reverse=True)[:6]

    return {
        "lambda_home": round(lambda_home, 2),
        "lambda_away": round(lambda_away, 2),
        "matrix": matrix,
        "1x2": {
            "home_win": {"prob": round(p_home_win * 100, 1), "fair_odd": calculate_fair_odd(p_home_win)},
            "draw": {"prob": round(p_draw * 100, 1), "fair_odd": calculate_fair_odd(p_draw)},
            "away_win": {"prob": round(p_away_win * 100, 1), "fair_odd": calculate_fair_odd(p_away_win)},
        },
        "btts": {
            "yes": {"prob": round(p_btts_yes * 100, 1), "fair_odd": calculate_fair_odd(p_btts_yes)},
            "no": {"prob": round(p_btts_no * 100, 1), "fair_odd": calculate_fair_odd(p_btts_no)},
        },
        "double_chance": {
            "1X": {"prob": round(p_1x * 100, 1), "fair_odd": calculate_fair_odd(p_1x)},
            "12": {"prob": round(p_12 * 100, 1), "fair_odd": calculate_fair_odd(p_12)},
            "X2": {"prob": round(p_x2 * 100, 1), "fair_odd": calculate_fair_odd(p_x2)},
        },
        "over_under": ou_results,
        "top_scores": scores_list,
    }


def estimate_lambdas_from_history(
    df_home: pd.DataFrame,
    df_away: pd.DataFrame,
    home_team_id: int,
    away_team_id: int,
    condition_weight: float = 0.65
) -> Tuple[float, float]:
    """
    Estima los parámetros lambda_home y lambda_away usando los datos históricos.
    condition_weight: ponderación para el desempeño específico (Local en casa vs Fuera).
    """
    # Goles Local
    home_matches = df_home[df_home['team_id'] == home_team_id]
    away_matches = df_away[df_away['team_id'] == away_team_id]

    if home_matches.empty or away_matches.empty:
        return 1.45, 1.15

    # Ataque y defensa general
    home_gf_all = home_matches['goals_for'].mean() if not home_matches.empty else 1.3
    home_ga_all = home_matches['goals_against'].mean() if not home_matches.empty else 1.1
    away_gf_all = away_matches['goals_for'].mean() if not away_matches.empty else 1.1
    away_ga_all = away_matches['goals_against'].mean() if not away_matches.empty else 1.3

    # Rendimiento específico por localía
    home_at_home = home_matches[home_matches['is_home'] == 1]
    away_at_away = away_matches[away_matches['is_home'] == 0]

    home_gf_spec = home_at_home['goals_for'].mean() if len(home_at_home) >= 2 else home_gf_all
    home_ga_spec = home_at_home['goals_against'].mean() if len(home_at_home) >= 2 else home_ga_all

    away_gf_spec = away_at_away['goals_for'].mean() if len(away_at_away) >= 2 else away_gf_all
    away_ga_spec = away_at_away['goals_against'].mean() if len(away_at_away) >= 2 else away_ga_all

    # Estimación ponderada
    home_attack = (condition_weight * home_gf_spec) + ((1.0 - condition_weight) * home_gf_all)
    away_defense = (condition_weight * away_ga_spec) + ((1.0 - condition_weight) * away_ga_all)
    lambda_home = (home_attack + away_defense) / 2.0

    away_attack = (condition_weight * away_gf_spec) + ((1.0 - condition_weight) * away_gf_all)
    home_defense = (condition_weight * home_ga_spec) + ((1.0 - condition_weight) * home_ga_all)
    lambda_away = (away_attack + home_defense) / 2.0

    return max(round(lambda_home, 2), 0.2), max(round(lambda_away, 2), 0.2)


def compute_empirical_team_stats(df_team: pd.DataFrame, team_id: int) -> Dict[str, Any]:
    """Calcula métricas estadísticas descriptivas y frecuencias reales observadas."""
    df = df_team[df_team['team_id'] == team_id].copy()
    if df.empty:
        return {}

    n = len(df)
    wins = len(df[df['goals_for'] > df['goals_against']])
    draws = len(df[df['goals_for'] == df['goals_against']])
    losses = len(df[df['goals_for'] < df['goals_against']])

    clean_sheets = len(df[df['goals_against'] == 0])
    failed_to_score = len(df[df['goals_for'] == 0])
    btts_count = len(df[(df['goals_for'] > 0) & (df['goals_against'] > 0)])
    over_2_5_count = len(df[(df['goals_for'] + df['goals_against']) > 2.5])
    over_1_5_count = len(df[(df['goals_for'] + df['goals_against']) > 1.5])

    def stat_summary(col):
        if col in df.columns and df[col].notna().any():
            s = df[col].dropna()
            return {
                "mean": round(float(s.mean()), 2),
                "std": round(float(s.std(ddof=0)), 2),
                "median": round(float(s.median()), 2),
                "min": int(s.min()),
                "max": int(s.max())
            }
        return {"mean": 0.0, "std": 0.0, "median": 0.0, "min": 0, "max": 0}

    return {
        "sample_size": n,
        "record": {"wins": wins, "draws": draws, "losses": losses},
        "rates": {
            "win_pct": round(wins / n * 100, 1),
            "draw_pct": round(draws / n * 100, 1),
            "loss_pct": round(losses / n * 100, 1),
            "clean_sheet_pct": round(clean_sheets / n * 100, 1),
            "failed_to_score_pct": round(failed_to_score / n * 100, 1),
            "btts_pct": round(btts_count / n * 100, 1),
            "over_1_5_pct": round(over_1_5_count / n * 100, 1),
            "over_2_5_pct": round(over_2_5_count / n * 100, 1),
        },
        "metrics": {
            "goals_for": stat_summary("goals_for"),
            "goals_against": stat_summary("goals_against"),
            "total_goals": stat_summary("total_goals"),
            "shots_on_target_for": stat_summary("shots_on_target_for"),
            "shots_off_target_for": stat_summary("shots_off_target_for"),
            "corners_for": stat_summary("corners_for"),
            "fouls_for": stat_summary("fouls_for"),
            "yellow_cards_for": stat_summary("yellow_cards_for"),
            "possession_for": stat_summary("possession_for"),
            "xg_for": stat_summary("xg_for"),
        }
    }


def compute_player_props_summary(df_players: pd.DataFrame, team_id: Optional[int] = None) -> pd.DataFrame:
    """Calcula estadísticas y tasas de acierto por jugador para Player Props."""
    if df_players.empty:
        return pd.DataFrame()

    df = df_players.copy()
    # Si viene col team_id la filtramos si se especifica
    if team_id and 'team_id' in df.columns:
        df = df[df['team_id'] == team_id]

    if df.empty or 'player_name' not in df.columns:
        return pd.DataFrame()

    grouped = df.groupby(['player_id', 'player_name']).agg(
        matches=('match_id', 'count'),
        starts=('is_starter', lambda s: (s == 1).sum() if 'is_starter' in df.columns else 0),
        total_mins=('minutes_played', 'sum') if 'minutes_played' in df.columns else ('match_id', 'count'),
        goals=('goals', 'sum') if 'goals' in df.columns else ('match_id', lambda x: 0),
        shots_on_target=('shots_on_target', 'sum') if 'shots_on_target' in df.columns else ('match_id', lambda x: 0),
        fouls=('fouls_committed', 'sum') if 'fouls_committed' in df.columns else ('match_id', lambda x: 0),
        yellow_cards=('yellow_cards', 'sum') if 'yellow_cards' in df.columns else ('match_id', lambda x: 0),
    ).reset_index()

    # Tasas promedio por partido
    grouped['sot_per_game'] = (grouped['shots_on_target'] / grouped['matches']).round(2)
    grouped['fouls_per_game'] = (grouped['fouls'] / grouped['matches']).round(2)
    grouped['cards_per_game'] = (grouped['yellow_cards'] / grouped['matches']).round(2)

    # Filtrar jugadores con al menos 2 partidos
    grouped = grouped[grouped['matches'] >= 1].sort_values(by=['shots_on_target', 'goals'], ascending=False)
    return grouped
