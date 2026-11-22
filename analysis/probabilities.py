# analysis/probabilities.py
"""
Motor Integral de Mercados de Apuestas y Probabilidades Estadísticas Puras.
Inspirado en los principios de diseño de dashboard (Wordless, First Glance, Salience).

Modela exhaustivamente:
- 3 Períodos Temporales: Partido Completo (FT), Primer Tiempo (1T), Segundo Tiempo (2T).
- Goles Marcados y Concedidos por equipo y combinados.
- Mercados Océano Rojo (Líquidos: 1X2, Over/Under, BTTS, HT/FT, DNB, Doble Oportunidad).
- Mercados Océano Azul (Ineficiencias: Tiros a Puerta SOT, Córners 1T/2T, Tarjetas, Faltas, Team Totals).
- Detección automática de "Alta Probabilidad" (>= 68%) y "Cuota Justa" (1 / P).
"""

import math
from typing import Dict, List, Tuple, Optional, Any
import numpy as np
import pandas as pd


def poisson_pmf(k: int, lam: float) -> float:
    """Calcula P(X = k) para Poisson(lam)."""
    if lam <= 0:
        return 1.0 if k == 0 else 0.0
    return (math.pow(lam, k) * math.exp(-lam)) / math.factorial(k)


def calculate_fair_odd(prob: float, min_odd: float = 1.01, max_odd: float = 100.0) -> float:
    """Calcula cuota justa (1 / P) acotada entre min_odd y max_odd."""
    if prob <= 0:
        return max_odd
    return round(min(max(1.0 / prob, min_odd), max_odd), 2)


def estimate_period_lambdas(
    df_home: pd.DataFrame,
    df_away: pd.DataFrame,
    home_id: int,
    away_id: int,
    period: str = "ft",
    weight: float = 0.65
) -> Tuple[float, float]:
    """
    Estima lambda_home y lambda_away para un período ('ft', 'ht', '2h').
    Cruza lo marcado por el local y lo concedido por el visitante.
    """
    for_col = "goals_for" if period == "ft" else f"goals_{period}_for"
    ag_col = "goals_against" if period == "ft" else f"goals_{period}_against"

    h_m = df_home[df_home['team_id'] == home_id]
    a_m = df_away[df_away['team_id'] == away_id]

    if h_m.empty or a_m.empty or for_col not in h_m.columns:
        default_lam = 1.35 if period == "ft" else 0.65
        return default_lam, default_lam * 0.85

    # Medias generales
    h_gf_all = h_m[for_col].mean() if not h_m[for_col].isna().all() else 1.3
    h_ga_all = h_m[ag_col].mean() if not h_m[ag_col].isna().all() else 1.1
    a_gf_all = a_m[for_col].mean() if not a_m[for_col].isna().all() else 1.1
    a_ga_all = a_m[ag_col].mean() if not a_m[ag_col].isna().all() else 1.3

    # Medias específicas por localía
    h_home = h_m[h_m['is_home'] == 1]
    a_away = a_m[a_m['is_home'] == 0]

    h_gf_spec = h_home[for_col].mean() if len(h_home) >= 2 and not h_home[for_col].isna().all() else h_gf_all
    h_ga_spec = h_home[ag_col].mean() if len(h_home) >= 2 and not h_home[ag_col].isna().all() else h_ga_all
    a_gf_spec = a_away[for_col].mean() if len(a_away) >= 2 and not a_away[for_col].isna().all() else a_gf_all
    a_ga_spec = a_away[ag_col].mean() if len(a_away) >= 2 and not a_away[ag_col].isna().all() else a_ga_all

    lam_home = (weight * h_gf_spec + (1 - weight) * h_gf_all + weight * a_ga_spec + (1 - weight) * a_ga_all) / 2.0
    lam_away = (weight * a_gf_spec + (1 - weight) * a_gf_all + weight * h_ga_spec + (1 - weight) * h_ga_all) / 2.0

    min_lam = 0.10 if period != "ft" else 0.20
    return max(round(float(lam_home), 2), min_lam), max(round(float(lam_away), 2), min_lam)


def compute_period_markets(
    lambda_home: float,
    lambda_away: float,
    period_label: str = "Partido Completo (FT)",
    lines_ou: List[float] = [0.5, 1.5, 2.5, 3.5],
    max_g: int = 6
) -> Dict[str, Any]:
    """Calcula probabilidades exactas y mercados derivados para un período específico."""
    mat = np.zeros((max_g + 1, max_g + 1))
    for x in range(max_g + 1):
        px = poisson_pmf(x, lambda_home)
        for y in range(max_g + 1):
            py = poisson_pmf(y, lambda_away)
            mat[x, y] = px * py

    tot = mat.sum()
    if tot > 0:
        mat = mat / tot

    # 1X2
    p_1 = float(np.sum(np.tril(mat, -1)))
    p_x = float(np.sum(np.diag(mat)))
    p_2 = float(np.sum(np.triu(mat, 1)))

    # Doble Oportunidad
    p_1x = p_1 + p_x
    p_12 = p_1 + p_2
    p_x2 = p_x + p_2

    # Draw No Bet (DNB)
    p_dnb_home = p_1 / (p_1 + p_2) if (p_1 + p_2) > 0 else 0.5
    p_dnb_away = p_2 / (p_1 + p_2) if (p_1 + p_2) > 0 else 0.5

    # BTTS
    p_home_scores = 1.0 - poisson_pmf(0, lambda_home)
    p_away_scores = 1.0 - poisson_pmf(0, lambda_away)
    p_btts_yes = float(p_home_scores * p_away_scores)
    p_btts_no = max(1.0 - p_btts_yes, 0.0)

    # Over / Under Totales
    ou_dict = {}
    for line in lines_ou:
        over_p = float(sum(mat[x, y] for x in range(max_g + 1) for y in range(max_g + 1) if (x + y) > line))
        under_p = max(1.0 - over_p, 0.0)
        ou_dict[f"Over {line}"] = {"prob": round(over_p * 100, 1), "fair_odd": calculate_fair_odd(over_p)}
        ou_dict[f"Under {line}"] = {"prob": round(under_p * 100, 1), "fair_odd": calculate_fair_odd(under_p)}

    # Goles por Equipo (Team Totals)
    home_team_ou = {}
    away_team_ou = {}
    for line in [0.5, 1.5, 2.5]:
        p_h_over = float(sum(poisson_pmf(x, lambda_home) for x in range(int(line) + 1, max_g + 1)))
        p_a_over = float(sum(poisson_pmf(y, lambda_away) for y in range(int(line) + 1, max_g + 1)))
        home_team_ou[f"Local Over {line}"] = {"prob": round(p_h_over * 100, 1), "fair_odd": calculate_fair_odd(p_h_over)}
        home_team_ou[f"Local Under {line}"] = {"prob": round((1.0 - p_h_over) * 100, 1), "fair_odd": calculate_fair_odd(1.0 - p_h_over)}
        away_team_ou[f"Visitante Over {line}"] = {"prob": round(p_a_over * 100, 1), "fair_odd": calculate_fair_odd(p_a_over)}
        away_team_ou[f"Visitante Under {line}"] = {"prob": round((1.0 - p_a_over) * 100, 1), "fair_odd": calculate_fair_odd(1.0 - p_a_over)}

    # Portería a cero y Ganar a cero
    clean_sheet_home = poisson_pmf(0, lambda_away)
    clean_sheet_away = poisson_pmf(0, lambda_home)
    win_to_nil_home = float(sum(mat[x, 0] for x in range(1, max_g + 1)))
    win_to_nil_away = float(sum(mat[0, y] for y in range(1, max_g + 1)))

    # Marcadores más probables
    scores = []
    for x in range(min(max_g + 1, 5)):
        for y in range(min(max_g + 1, 5)):
            p = float(mat[x, y])
            scores.append({"score": f"{x} - {y}", "prob": round(p * 100, 1), "fair_odd": calculate_fair_odd(p)})
    scores = sorted(scores, key=lambda s: s["prob"], reverse=True)[:5]

    return {
        "period": period_label,
        "lambda_home": round(lambda_home, 2),
        "lambda_away": round(lambda_away, 2),
        "matrix": mat,
        "1x2": {
            "1": {"prob": round(p_1 * 100, 1), "fair_odd": calculate_fair_odd(p_1)},
            "X": {"prob": round(p_x * 100, 1), "fair_odd": calculate_fair_odd(p_x)},
            "2": {"prob": round(p_2 * 100, 1), "fair_odd": calculate_fair_odd(p_2)},
        },
        "double_chance": {
            "1X": {"prob": round(p_1x * 100, 1), "fair_odd": calculate_fair_odd(p_1x)},
            "12": {"prob": round(p_12 * 100, 1), "fair_odd": calculate_fair_odd(p_12)},
            "X2": {"prob": round(p_x2 * 100, 1), "fair_odd": calculate_fair_odd(p_x2)},
        },
        "dnb": {
            "1 (Local DNB)": {"prob": round(p_dnb_home * 100, 1), "fair_odd": calculate_fair_odd(p_dnb_home)},
            "2 (Visitante DNB)": {"prob": round(p_dnb_away * 100, 1), "fair_odd": calculate_fair_odd(p_dnb_away)},
        },
        "btts": {
            "Sí": {"prob": round(p_btts_yes * 100, 1), "fair_odd": calculate_fair_odd(p_btts_yes)},
            "No": {"prob": round(p_btts_no * 100, 1), "fair_odd": calculate_fair_odd(p_btts_no)},
        },
        "over_under": ou_dict,
        "home_totals": home_team_ou,
        "away_totals": away_team_ou,
        "clean_sheet": {
            "Local Portería a Cero": {"prob": round(clean_sheet_home * 100, 1), "fair_odd": calculate_fair_odd(clean_sheet_home)},
            "Visitante Portería a Cero": {"prob": round(clean_sheet_away * 100, 1), "fair_odd": calculate_fair_odd(clean_sheet_away)},
        },
        "win_to_nil": {
            "Local Gana a Cero": {"prob": round(win_to_nil_home * 100, 1), "fair_odd": calculate_fair_odd(win_to_nil_home)},
            "Visitante Gana a Cero": {"prob": round(win_to_nil_away * 100, 1), "fair_odd": calculate_fair_odd(win_to_nil_away)},
        },
        "top_scores": scores
    }


def compute_ht_ft_matrix(model_ht: Dict, model_2h: Dict) -> List[Dict[str, Any]]:
    """Calcula la matriz combinada de Descanso / Final (HT / FT)."""
    p_ht = model_ht["1x2"]
    p_2h = model_2h["1x2"]

    results = []
    labels = [("1/1", "1", "1"), ("1/X", "1", "X"), ("1/2", "1", "2"),
              ("X/1", "X", "1"), ("X/X", "X", "X"), ("X/2", "X", "2"),
              ("2/1", "2", "1"), ("2/X", "2", "X"), ("2/2", "2", "2")]

    for code, h_res, _2h_res in labels:
        p = (p_ht[h_res]["prob"] / 100.0) * (p_2h[_2h_res]["prob"] / 100.0)
        results.append({
            "Opción": code,
            "Probabilidad (%)": round(p * 100, 1),
            "Cuota Justa": calculate_fair_odd(p)
        })

    return sorted(results, key=lambda x: x["Probabilidad (%)"], reverse=True)


def compute_blue_ocean_props(
    df_home: pd.DataFrame,
    df_away: pd.DataFrame,
    home_id: int,
    away_id: int
) -> Dict[str, Any]:
    """
    Calcula probabilidades empíricas y cuotas justas para mercados Océano Azul:
    Tiros al arco, Córners (FT, 1T, 2T), Faltas y Tarjetas.
    """
    h_m = df_home[df_home['team_id'] == home_id]
    a_m = df_away[df_away['team_id'] == away_id]

    def get_stat_means(col, default_val):
        h_val = float(h_m[col].mean()) if col in h_m.columns and not h_m[col].isna().all() else default_val
        a_val = float(a_m[col].mean()) if col in a_m.columns and not a_m[col].isna().all() else default_val
        return h_val, a_val

    # 1. Tiros al Arco (SOT)
    h_sot_for, _ = get_stat_means("shots_on_target_for", 4.5)
    _, a_sot_against = get_stat_means("shots_on_target_against", 4.0)
    lam_h_sot = (h_sot_for + a_sot_against) / 2.0

    a_sot_for, _ = get_stat_means("shots_on_target_for", 4.0)
    _, h_sot_against = get_stat_means("shots_on_target_against", 4.5)
    lam_a_sot = (a_sot_for + h_sot_against) / 2.0
    lam_tot_sot = lam_h_sot + lam_a_sot

    def poisson_over(lam, line):
        k_line = math.floor(line)
        p_over = 1.0 - sum(poisson_pmf(k, lam) for k in range(k_line + 1))
        return max(p_over, 0.0)

    sot_markets = []
    for line in [6.5, 7.5, 8.5, 9.5, 10.5]:
        p = poisson_over(lam_tot_sot, line)
        sot_markets.append({
            "Mercado": f"Tiros al Arco Totales Over {line}",
            "Tipo": "Océano Azul",
            "Prob": round(p * 100, 1),
            "Cuota": calculate_fair_odd(p),
            "Media Estimada": round(lam_tot_sot, 1)
        })

    # Tiros Local / Visitante
    for line in [3.5, 4.5, 5.5]:
        p = poisson_over(lam_h_sot, line)
        sot_markets.append({
            "Mercado": f"Local Tiros al Arco Over {line}",
            "Tipo": "Océano Azul",
            "Prob": round(p * 100, 1),
            "Cuota": calculate_fair_odd(p),
            "Media Estimada": round(lam_h_sot, 1)
        })
    for line in [2.5, 3.5, 4.5]:
        p = poisson_over(lam_a_sot, line)
        sot_markets.append({
            "Mercado": f"Visitante Tiros al Arco Over {line}",
            "Tipo": "Océano Azul",
            "Prob": round(p * 100, 1),
            "Cuota": calculate_fair_odd(p),
            "Media Estimada": round(lam_a_sot, 1)
        })

    # 2. Córners FT, 1T, 2T
    h_corn_for, _ = get_stat_means("corners_for", 5.0)
    _, a_corn_ag = get_stat_means("corners_against", 4.5)
    lam_tot_corn = (h_corn_for + a_corn_ag) + ((a_corn_ag + h_corn_for) * 0.45)
    lam_tot_corn = max(lam_tot_corn, 8.5)

    h_corn_1t, _ = get_stat_means("corners_ht_for", 2.4)
    _, a_corn_1t_ag = get_stat_means("corners_ht_against", 2.2)
    lam_corn_1t = max((h_corn_1t + a_corn_1t_ag) * 1.05, 4.0)

    corner_markets = []
    for line in [7.5, 8.5, 9.5, 10.5, 11.5]:
        p = poisson_over(lam_tot_corn, line)
        corner_markets.append({
            "Mercado": f"Córners Totales FT Over {line}",
            "Tipo": "Océano Azul",
            "Prob": round(p * 100, 1),
            "Cuota": calculate_fair_odd(p),
            "Media": round(lam_tot_corn, 1)
        })
    for line in [3.5, 4.5, 5.5]:
        p = poisson_over(lam_corn_1t, line)
        corner_markets.append({
            "Mercado": f"Córners Primer Tiempo (1T) Over {line}",
            "Tipo": "Océano Azul",
            "Prob": round(p * 100, 1),
            "Cuota": calculate_fair_odd(p),
            "Media": round(lam_corn_1t, 1)
        })

    # 3. Faltas y Tarjetas
    h_fouls, _ = get_stat_means("fouls_for", 12.0)
    a_fouls, _ = get_stat_means("fouls_for", 12.0)
    lam_tot_fouls = h_fouls + a_fouls

    h_cards, _ = get_stat_means("yellow_cards_for", 2.2)
    a_cards, _ = get_stat_means("yellow_cards_for", 2.2)
    lam_tot_cards = h_cards + a_cards

    discipline_markets = []
    for line in [3.5, 4.5, 5.5]:
        p = poisson_over(lam_tot_cards, line)
        discipline_markets.append({
            "Mercado": f"Tarjetas Totales FT Over {line}",
            "Tipo": "Océano Azul",
            "Prob": round(p * 100, 1),
            "Cuota": calculate_fair_odd(p),
            "Media": round(lam_tot_cards, 1)
        })
    for line in [21.5, 23.5, 25.5]:
        p = poisson_over(lam_tot_fouls, line)
        discipline_markets.append({
            "Mercado": f"Faltas Totales FT Over {line}",
            "Tipo": "Océano Azul",
            "Prob": round(p * 100, 1),
            "Cuota": calculate_fair_odd(p),
            "Media": round(lam_tot_fouls, 1)
        })

    return {
        "shots_on_target": sot_markets,
        "corners": corner_markets,
        "discipline": discipline_markets,
        "means": {
            "sot_total": round(lam_tot_sot, 1),
            "corners_total": round(lam_tot_corn, 1),
            "corners_1t": round(lam_corn_1t, 1),
            "cards_total": round(lam_tot_cards, 1),
            "fouls_total": round(lam_tot_fouls, 1),
        }
    }


def get_all_high_probability_picks(
    model_ft: Dict,
    model_ht: Dict,
    model_2h: Dict,
    blue_ocean: Dict,
    threshold: float = 68.0
) -> List[Dict[str, Any]]:
    """
    Filtra y compila todas las selecciones de Alta Probabilidad (>= threshold %)
    a través de todos los períodos y variables.
    """
    picks = []

    def check_and_add(name, period, ocean_type, prob, fair_odd, context=""):
        if prob >= threshold:
            picks.append({
                "Selección": name,
                "Período": period,
                "Tipo": ocean_type,
                "Probabilidad (%)": prob,
                "Cuota Justa": fair_odd,
                "Detalle": context
            })

    # 1X2 y Doble Oportunidad
    for per_name, mod in [("FT", model_ft), ("1T", model_ht), ("2T", model_2h)]:
        for opt, data in mod["1x2"].items():
            check_and_add(f"Resultado {opt}", per_name, "🔴 Océano Rojo", data["prob"], data["fair_odd"])
        for opt, data in mod["double_chance"].items():
            check_and_add(f"Doble Oportunidad {opt}", per_name, "🔴 Océano Rojo", data["prob"], data["fair_odd"])
        for opt, data in mod["dnb"].items():
            check_and_add(f"DNB {opt}", per_name, "🔴 Océano Rojo", data["prob"], data["fair_odd"])
        for opt, data in mod["btts"].items():
            check_and_add(f"Ambos Marcan - {opt}", per_name, "🔴 Océano Rojo", data["prob"], data["fair_odd"])
        for line, data in mod["over_under"].items():
            check_and_add(f"Goles {line}", per_name, "🔴 Océano Rojo", data["prob"], data["fair_odd"])
        for line, data in mod["home_totals"].items():
            check_and_add(line, per_name, "🔵 Océano Azul", data["prob"], data["fair_odd"])
        for line, data in mod["away_totals"].items():
            check_and_add(line, per_name, "🔵 Océano Azul", data["prob"], data["fair_odd"])

    # Blue ocean props
    for cat in ["shots_on_target", "corners", "discipline"]:
        for item in blue_ocean.get(cat, []):
            check_and_add(item["Mercado"], "FT / Props", "🔵 Océano Azul", item["Prob"], item["Cuota"], f"Media: {item.get('Media', item.get('Media Estimada'))}")

    # Ordenar de mayor a menor probabilidad
    return sorted(picks, key=lambda x: x["Probabilidad (%)"], reverse=True)


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
    over_0_5_ht_count = len(df[df['total_goals_ht'] > 0.5]) if 'total_goals_ht' in df.columns else 0

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
            "over_0_5_ht_pct": round(over_0_5_ht_count / n * 100, 1),
        },
        "metrics": {
            "goals_for": stat_summary("goals_for"),
            "goals_against": stat_summary("goals_against"),
            "goals_ht_for": stat_summary("goals_ht_for"),
            "goals_ht_against": stat_summary("goals_ht_against"),
            "goals_2h_for": stat_summary("goals_2h_for"),
            "goals_2h_against": stat_summary("goals_2h_against"),
            "shots_on_target_for": stat_summary("shots_on_target_for"),
            "shots_on_target_against": stat_summary("shots_on_target_against"),
            "corners_for": stat_summary("corners_for"),
            "corners_against": stat_summary("corners_against"),
            "fouls_for": stat_summary("fouls_for"),
            "yellow_cards_for": stat_summary("yellow_cards_for"),
            "possession_for": stat_summary("possession_for"),
        }
    }


def compute_player_props_summary(df_players: pd.DataFrame, team_id: Optional[int] = None) -> pd.DataFrame:
    """Calcula estadísticas y tasas de acierto por jugador para Player Props."""
    if df_players.empty:
        return pd.DataFrame()

    df = df_players.copy()
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

    grouped['sot_per_game'] = (grouped['shots_on_target'] / grouped['matches']).round(2)
    grouped['fouls_per_game'] = (grouped['fouls'] / grouped['matches']).round(2)
    grouped['cards_per_game'] = (grouped['yellow_cards'] / grouped['matches']).round(2)

    grouped = grouped[grouped['matches'] >= 1].sort_values(by=['shots_on_target', 'goals'], ascending=False)
    return grouped
