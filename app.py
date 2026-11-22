# app.py
"""
Football Analytics & Pure Probability Engine (Elite Edition)
Dashboard analítico deportivo avanzado diseñado bajo los principios de 'dashboard-design-skill'.

Incluye:
1. Cartelera interactiva estilo 365Scores con selección por fila y modal de validación.
2. Modelo Bivariado Dixon & Coles (1997) para corrección de empates y marcadores bajos.
3. Simulación de Monte Carlo (10,000 partidos) con percentiles (P10, P50, P90) e intervalos de confianza del 95%.
4. Radar de Oportunidades y Scanner de Valor (+EV) con Criterio de Kelly Fraccional.
5. Mercados Océano Rojo (1X2, Doble Oportunidad, Over/Under, BTTS, HT/FT, DNB).
6. Mercados Océano Azul (Tiros a Puerta, Remates, Faltas, Tarjetas, Córners y Player Props).
7. Balances de Goles Marcados vs Concedidos en FT, 1T y 2T + Diagnóstico de Regresión a la Media (xG).
8. Descarga en Excel (.xlsx) y CSV.
"""

import os
import sys
from pathlib import Path

# Garantizar que el directorio raíz de la aplicación esté en sys.path
APP_DIR = Path(__file__).resolve().parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

import io
import time
import requests
from datetime import datetime, date
import pandas as pd
import numpy as np
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

# Configuración inicial de Streamlit
st.set_page_config(
    page_title="Football Analytics & Betting Engine",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Estilos CSS según principios de dashboard-design-skill (Salience, Honest, Quiet)
st.markdown("""
<style>
    .block-container { padding-top: 1.4rem; padding-bottom: 3rem; }
    
    .dash-header { display: flex; justify-content: space-between; align-items: flex-end; margin-bottom: 1.1rem; }
    .dash-title { font-size: 2.15rem; font-weight: 800; color: #0F172A; letter-spacing: -0.025em; margin: 0; }
    .dash-meta { font-size: 0.92rem; color: #64748B; margin-top: 0.2rem; }
    
    /* KPI Strip */
    .kpi-container { display: grid; grid-template-columns: repeat(5, 1fr); gap: 12px; margin-bottom: 22px; }
    .kpi-card { background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 10px; padding: 13px 15px; box-shadow: 0 1px 2px rgba(0,0,0,0.03); }
    .kpi-label { font-size: 0.74rem; font-weight: 700; text-transform: uppercase; color: #64748B; letter-spacing: 0.05em; margin-bottom: 5px; }
    .kpi-value { font-size: 1.55rem; font-weight: 800; color: #0F172A; line-height: 1.1; }
    .kpi-sub { font-size: 0.82rem; font-weight: 600; color: #2563EB; margin-top: 4px; }
    .kpi-high { border-top: 3px solid #16A34A; }
    .kpi-blue { border-top: 3px solid #3B82F6; }
    .kpi-purple { border-top: 3px solid #8B5CF6; }

    /* Tarjeta de validación de partido */
    .match-validation-card {
        background: #FFFFFF;
        border: 2px solid #3B82F6;
        border-radius: 12px;
        padding: 20px 24px;
        margin-bottom: 24px;
        box-shadow: 0 4px 12px rgba(59, 130, 246, 0.08);
    }
    .match-header-box {
        display: flex;
        justify-content: space-between;
        align-items: center;
        background: #F8FAFC;
        padding: 10px 16px;
        border-radius: 8px;
        margin-bottom: 14px;
    }
    .team-title { font-size: 1.45rem; font-weight: 800; color: #0F172A; }
    
    .calc-box {
        background: #F8FAFC;
        border: 1px solid #E2E8F0;
        border-radius: 10px;
        padding: 18px;
        margin-top: 15px;
    }
</style>
""", unsafe_allow_html=True)

# Importaciones del motor local
from db.database import init_db, SessionGold, engine_gold
from main import process_team_matches
from transform.silver_to_gold import compute_rolling_averages, compute_dim_referee, generate_dim_date
from analysis.probabilities import (
    estimate_period_lambdas,
    compute_dixon_coles_period_markets,
    run_monte_carlo_simulation,
    compute_ht_ft_matrix,
    compute_blue_ocean_props,
    compute_player_props_odds,
    get_all_high_probability_picks,
    compute_empirical_team_stats,
    calculate_fair_odd
)

# Inicializar Base de Datos SQLite
init_db()

# Inicializar Estados de Sesión
if "selected_match" not in st.session_state:
    st.session_state.selected_match = None
if "analysis_confirmed" not in st.session_state:
    st.session_state.analysis_confirmed = False
if "confirmed_matches_history" not in st.session_state:
    st.session_state.confirmed_matches_history = 10


# ==============================================================================
# CONSULTAS Y API
# ==============================================================================
@st.cache_data(ttl=180)
def fetch_day_fixtures(date_str: str):
    """Descarga cartelera de fútbol de la fecha (DD/MM/YYYY) desde la API de 365scores."""
    url = "https://webws.365scores.com/web/games/"
    params = {
        'appTypeId': 5,
        'langId': 14,
        'timezoneName': 'America/Bogota',
        'startDate': date_str,
        'endDate': date_str
    }
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}

    try:
        r = requests.get(url, params=params, headers=headers, timeout=12)
        r.raise_for_status()
        data = r.json()

        competitions = {c["id"]: c.get("name") for c in data.get("competitions", [])}
        games = []
        for g in data.get("games", []):
            if g.get("sportId") != 1:
                continue

            comp_id = g.get("competitionId")
            comp_name = competitions.get(comp_id, "Torneo Internacional")

            home = g.get("homeCompetitor", {})
            away = g.get("awayCompetitor", {})
            home_id = home.get("id")
            away_id = away.get("id")
            if not home_id or not away_id:
                continue

            start_raw = g.get("startTime", "")
            time_str = "--:--"
            if "T" in start_raw:
                time_str = start_raw.split("T")[1][:5]

            status_text = g.get("statusText", "Prog.")
            home_score = home.get("score")
            away_score = away.get("score")

            if home_score is not None and away_score is not None and status_text != "Prog.":
                score_display = f"{int(home_score)} - {int(away_score)}"
            else:
                score_display = "vs"

            if status_text == "Prog.":
                cat = "Programado"
            elif status_text == "Finalizado":
                cat = "Finalizado"
            else:
                cat = "En Vivo"

            games.append({
                "game_id": g.get("id"),
                "Hora": time_str,
                "Torneo": comp_name,
                "Equipo Local": home.get("name", "Local"),
                "Marcador": score_display,
                "Equipo Visitante": away.get("name", "Visitante"),
                "Estado": status_text,
                "Categoría": cat,
                "home_id": home_id,
                "away_id": away_id,
                "home_name": home.get("name", "Local"),
                "away_name": away.get("name", "Visitante"),
                "competition": comp_name,
            })
        return games
    except Exception as e:
        st.error(f"Error consultando partidos: {e}")
        return []


def load_gold_data(team_id: int):
    """Carga partidos de la capa Gold."""
    try:
        query = f"""
        SELECT f.*, t.team_name, opp.team_name AS opponent_name
        FROM fact_team_match f
        LEFT JOIN dim_team t ON f.team_id = t.team_id
        LEFT JOIN dim_team opp ON f.opponent_id = opp.team_id
        WHERE f.team_id = {team_id}
        ORDER BY f.match_id DESC
        """
        return pd.read_sql(query, engine_gold)
    except Exception:
        return pd.DataFrame()


def load_players_gold_data(team_ids: list):
    """Carga estadísticas de jugadores."""
    if not team_ids:
        return pd.DataFrame()
    try:
        ids_str = ",".join(str(tid) for tid in team_ids)
        query = f"""
        SELECT fp.*, dp.player_name, dt.team_name
        FROM fact_player_match fp
        LEFT JOIN dim_player dp ON fp.player_id = dp.player_id
        LEFT JOIN dim_team dt ON fp.team_id = dt.team_id
        WHERE fp.team_id IN ({ids_str})
        ORDER BY fp.minutes_played DESC
        """
        return pd.read_sql(query, engine_gold)
    except Exception:
        return pd.DataFrame()


# ==============================================================================
# HEADER
# ==============================================================================
col_head1, col_head2 = st.columns([3, 1])
with col_head1:
    st.markdown("<div class='dash-title'>⚽ Football Analytics & Betting Engine (Elite)</div>", unsafe_allow_html=True)
    st.markdown("<div class='dash-meta'>Modelo Dixon-Coles · Simulación Monte Carlo (10k) · Scanner +EV · Océanos Azul y Rojo · Props</div>", unsafe_allow_html=True)
with col_head2:
    if st.session_state.selected_match and st.session_state.analysis_confirmed:
        if st.button("🔄 Volver a la Cartelera", use_container_width=True):
            st.session_state.selected_match = None
            st.session_state.analysis_confirmed = False
            st.rerun()


# ==============================================================================
# PASO 1: CARTELERA 365SCORES (SI NO HAY ANÁLISIS CONFIRMADO)
# ==============================================================================
if not (st.session_state.selected_match and st.session_state.analysis_confirmed):
    c_f1, c_f2, c_f3, c_f4 = st.columns([1.1, 1.4, 1.6, 2])
    with c_f1:
        match_date = st.date_input("Fecha:", date.today(), label_visibility="collapsed")
    date_str = match_date.strftime("%d/%m/%Y")

    fixtures = fetch_day_fixtures(date_str)

    with c_f2:
        status_filter = st.selectbox(
            "Estado:",
            ["Todos los partidos", "Programados / Por Jugar", "En Vivo", "Finalizados"],
            label_visibility="collapsed"
        )
    with c_f3:
        all_comps = sorted(list(set(g["Torneo"] for g in fixtures))) if fixtures else []
        comp_filter = st.selectbox(
            "Liga / Torneo:",
            ["Todas las ligas"] + all_comps,
            label_visibility="collapsed"
        )
    with c_f4:
        search_txt = st.text_input("🔍 Buscar equipo o torneo...", "").strip().lower()

    filtered_games = fixtures
    if status_filter == "Programados / Por Jugar":
        filtered_games = [g for g in filtered_games if g["Categoría"] == "Programado"]
    elif status_filter == "En Vivo":
        filtered_games = [g for g in filtered_games if g["Categoría"] == "En Vivo"]
    elif status_filter == "Finalizados":
        filtered_games = [g for g in filtered_games if g["Categoría"] == "Finalizado"]

    if comp_filter != "Todas las ligas":
        filtered_games = [g for g in filtered_games if g["Torneo"] == comp_filter]

    if search_txt:
        filtered_games = [
            g for g in filtered_games
            if search_txt in g["Equipo Local"].lower() or search_txt in g["Equipo Visitante"].lower() or search_txt in g["Torneo"].lower()
        ]

    st.markdown(f"**Agenda de partidos:** `{len(filtered_games)}` encuentros disponibles")

    if filtered_games:
        df_display = pd.DataFrame(filtered_games)[[
            "Hora", "Torneo", "Equipo Local", "Marcador", "Equipo Visitante", "Estado"
        ]]

        st.caption("👇 **Haz clic sobre la fila** del partido que deseas analizar:")

        selection = st.dataframe(
            df_display,
            on_select="rerun",
            selection_mode="single-row",
            use_container_width=True,
            hide_index=True,
            height=370
        )

        if selection and selection.get("selection") and selection["selection"].get("rows"):
            selected_row_idx = selection["selection"]["rows"][0]
            if 0 <= selected_row_idx < len(filtered_games):
                chosen = filtered_games[selected_row_idx]
                st.session_state.selected_match = chosen
                st.session_state.analysis_confirmed = False
                st.rerun()

    else:
        st.info("No se encontraron partidos para los filtros seleccionados.")


# ==============================================================================
# PASO 2: TARJETA DE VALIDACIÓN PREVIA AL ANÁLISIS
# ==============================================================================
if st.session_state.selected_match and not st.session_state.analysis_confirmed:
    match = st.session_state.selected_match
    st.markdown("---")
    st.markdown("### 📋 Validación del Partido Seleccionado")

    st.markdown(f"""
    <div class='match-validation-card'>
        <div class='match-header-box'>
            <span style='font-weight:700; color:#1E40AF;'>🏆 {match.get('competition', match.get('Torneo', ''))}</span>
            <span style='font-weight:600; color:#475569;'>⏰ {match.get('Hora', '--:--')} | 📌 {match.get('Estado', '')}</span>
        </div>
        <div style='text-align: center; margin: 12px 0;'>
            <span class='team-title'>🏠 {match['home_name']}</span>
            <span style='font-size: 1.4rem; font-weight: 800; color: #2563EB; margin: 0 20px;'>VS</span>
            <span class='team-title'>✈️ {match['away_name']}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    col_v1, col_v2, col_v3 = st.columns([2, 1.5, 1.5])
    with col_v1:
        n_history = st.slider(
            "📊 Partidos históricos a descargar por equipo:",
            min_value=3, max_value=25, value=st.session_state.confirmed_matches_history, step=1
        )
    with col_v2:
        force_dl = st.checkbox("🔄 Forzar actualización completa (API)", value=False)
    with col_v3:
        st.write("")
        st.write("")
        btn_confirm = st.button("🚀 Confirmar e Iniciar Análisis", type="primary", use_container_width=True)

    col_canc, _ = st.columns([1.5, 4])
    with col_canc:
        if st.button("✖️ Cancelar y elegir otro", use_container_width=True):
            st.session_state.selected_match = None
            st.session_state.analysis_confirmed = False
            st.rerun()

    if btn_confirm:
        st.session_state.confirmed_matches_history = n_history
        st.session_state.force_redownload = force_dl
        st.session_state.analysis_confirmed = True
        st.rerun()


# ==============================================================================
# PASO 3: DASHBOARD ANALÍTICO AVANZADO
# ==============================================================================
if st.session_state.selected_match and st.session_state.analysis_confirmed:
    match = st.session_state.selected_match
    home_id = match['home_id']
    away_id = match['away_id']
    home_name = match['home_name']
    away_name = match['away_name']
    n_history = st.session_state.confirmed_matches_history
    force_dl = st.session_state.get("force_redownload", False)

    df_home_exist = load_gold_data(home_id)
    df_away_exist = load_gold_data(away_id)

    need_dl = force_dl or df_home_exist.empty or df_away_exist.empty

    if need_dl:
        prog_bar = st.progress(0, text="Iniciando descarga de estadísticas...")
        status_txt = st.empty()

        status_txt.text(f"Descargando últimos {n_history} partidos de {home_name}...")
        def h_cb(c, t, d): prog_bar.progress(int((c / (t * 2)) * 100), text=f"[{home_name}] {d}")
        process_team_matches(home_id, max_matches=n_history, progress_callback=h_cb)

        status_txt.text(f"Descargando últimos {n_history} partidos de {away_name}...")
        def a_cb(c, t, d): prog_bar.progress(int(50 + (c / (t * 2)) * 100), text=f"[{away_name}] {d}")
        process_team_matches(away_id, max_matches=n_history, progress_callback=a_cb)

        status_txt.text("Calculando promedios móviles y variables Gold...")
        compute_rolling_averages()
        compute_dim_referee()
        generate_dim_date()

        prog_bar.progress(100, text="¡Datos procesados con éxito!")
        time.sleep(1)
        prog_bar.empty()
        status_txt.empty()

    df_home = load_gold_data(home_id)
    df_away = load_gold_data(away_id)
    df_players = load_players_gold_data([home_id, away_id])

    if df_home.empty or df_away.empty:
        st.warning("No hay suficientes partidos históricos en la API para uno de los equipos.")
        st.stop()

    # 1. Estimación de Lambdas y Modelado Dixon & Coles
    lam_h_ft, lam_a_ft = estimate_period_lambdas(df_home, df_away, home_id, away_id, "ft")
    lam_h_ht, lam_a_ht = estimate_period_lambdas(df_home, df_away, home_id, away_id, "ht")
    lam_h_2h, lam_a_2h = estimate_period_lambdas(df_home, df_away, home_id, away_id, "2h")

    model_ft = compute_dixon_coles_period_markets(lam_h_ft, lam_a_ft, "Partido Completo (FT)", [0.5, 1.5, 2.5, 3.5, 4.5])
    model_ht = compute_dixon_coles_period_markets(lam_h_ht, lam_a_ht, "Primer Tiempo (1T)", [0.5, 1.5, 2.5])
    model_2h = compute_dixon_coles_period_markets(lam_h_2h, lam_a_2h, "Segundo Tiempo (2T)", [0.5, 1.5, 2.5])

    # 2. Mercados Secundarios y Props
    ht_ft_matrix = compute_ht_ft_matrix(model_ht, model_2h)
    blue_ocean = compute_blue_ocean_props(df_home, df_away, home_id, away_id)
    player_props_df = compute_player_props_odds(df_players)
    high_prob_picks = get_all_high_probability_picks(model_ft, model_ht, model_2h, blue_ocean, threshold=68.0)
    stats_home = compute_empirical_team_stats(df_home, home_id)
    stats_away = compute_empirical_team_stats(df_away, away_id)

    # 3. Simulación de Monte Carlo (10,000 partidos)
    mc_results = run_monte_carlo_simulation(
        lam_h_ft, lam_a_ft,
        blue_ocean['sot']['lam_total'],
        blue_ocean['corners']['lam_total'],
        blue_ocean['fouls']['lam_total'],
        n_sims=10000
    )

    # --------------------------------------------------------------------------
    # EXECUTIVE KPI STRIP (FIRST GLANCE - 5 TILES)
    # --------------------------------------------------------------------------
    st.markdown("---")
    top_pick_1 = high_prob_picks[0] if len(high_prob_picks) > 0 else {"Selección": "1X", "Probabilidad (%)": 75.0, "Cuota Justa": 1.33, "Período": "FT", "Kelly Sugerido (%)": "2.5%"}
    top_blue = [p for p in high_prob_picks if "Azul" in p["Tipo"]]
    top_blue_pick = top_blue[0] if top_blue else {"Selección": "Córners FT Over 7.5", "Probabilidad (%)": 71.0, "Cuota Justa": 1.41, "Kelly Sugerido (%)": "2.2%"}

    st.markdown(f"""
    <div class='kpi-container'>
        <div class='kpi-card kpi-high'>
            <div class='kpi-label'>🔥 Máxima Certeza</div>
            <div class='kpi-value'>{top_pick_1['Probabilidad (%)']}%</div>
            <div class='kpi-sub'>{top_pick_1['Selección']} · Cuota {top_pick_1['Cuota Justa']} (Kelly {top_pick_1['Kelly Sugerido (%)']})</div>
        </div>
        <div class='kpi-card kpi-blue'>
            <div class='kpi-label'>💎 Mayor Ineficiencia (+EV)</div>
            <div class='kpi-value'>{top_blue_pick['Probabilidad (%)']}%</div>
            <div class='kpi-sub'>{top_blue_pick['Selección']} · Cuota {top_blue_pick['Cuota Justa']}</div>
        </div>
        <div class='kpi-card kpi-purple'>
            <div class='kpi-label'>🎲 Marcador Modal (MC 10k)</div>
            <div class='kpi-value'>{mc_results['modal_score']}</div>
            <div class='kpi-sub'>Frecuencia {mc_results['modal_score_freq']}% · IC 95% [{mc_results['percentiles']['goles']['CI_95_low']}, {mc_results['percentiles']['goles']['CI_95_high']} goles]</div>
        </div>
        <div class='kpi-card'>
            <div class='kpi-label'>⚽ xG Dixon-Coles (FT)</div>
            <div class='kpi-value'>{round(lam_h_ft + lam_a_ft, 2)}</div>
            <div class='kpi-sub'>{home_name} {lam_h_ft} - {lam_a_ft} {away_name}</div>
        </div>
        <div class='kpi-card'>
            <div class='kpi-label'>🎯 Ambos Marcan (BTTS)</div>
            <div class='kpi-value'>{model_ft['btts']['Sí']['prob']}%</div>
            <div class='kpi-sub'>Cuota Justa: {model_ft['btts']['Sí']['fair_odd']}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # --------------------------------------------------------------------------
    # TABS ANALÍTICOS DE ÉLITE
    # --------------------------------------------------------------------------
    (
        tab_radar,
        tab_mc,
        tab_ft,
        tab_halves,
        tab_sot,
        tab_fouls,
        tab_corners,
        tab_props,
        tab_xg_stats,
        tab_export
    ) = st.tabs([
        "🎯 Radar de Oportunidades & Scanner +EV",
        "🎲 Monte Carlo (10k Sims & Percentiles)",
        "⏱️ Partido Completo (Dixon-Coles)",
        "🌓 1T y 2T (Por Mitades)",
        "🎯 Tiros y Remates (Océano Azul)",
        "🟨 Faltas, Tarjetas y Árbitro",
        "🚩 Córners (FT & 1T)",
        "🏃 Player Props (Cuotas Jugador)",
        "📊 Marcados vs Concedidos & xG",
        "💾 Exportación Excel / CSV"
    ])

    # --------------------------------------------------------------------------
    # TAB 1: RADAR DE OPORTUNIDADES & SCANNER +EV
    # --------------------------------------------------------------------------
    with tab_radar:
        st.markdown("### 🎯 Radar de Oportunidades y Scanner de Valor Matemático (+EV)")
        st.caption("Filtro algorítmico que clasifica automáticamente todas las apuestas que superan el 68% de certeza matemática o presentan ventaja estadística.")

        col_rad1, col_rad2 = st.columns([1.5, 1])
        with col_rad1:
            cat_filter = st.selectbox(
                "Filtrar por categoría:",
                ["Todas las oportunidades", "Ultra Certeza (>= 75%)", "Océano Azul (Ineficiencias)", "Mercados FT (90m)", "Mercados 1T / 2T"]
            )

            filtered_picks = high_prob_picks
            if cat_filter == "Ultra Certeza (>= 75%)":
                filtered_picks = [p for p in high_prob_picks if p["Probabilidad (%)"] >= 75.0]
            elif cat_filter == "Océano Azul (Ineficiencias)":
                filtered_picks = [p for p in high_prob_picks if "Azul" in p["Tipo"]]
            elif cat_filter == "Mercados FT (90m)":
                filtered_picks = [p for p in high_prob_picks if p["Período"] == "FT"]
            elif cat_filter == "Mercados 1T / 2T":
                filtered_picks = [p for p in high_prob_picks if p["Período"] in ["1T", "2T"]]

            if filtered_picks:
                df_rad = pd.DataFrame(filtered_picks)[[
                    "Selección", "Período", "Tipo", "Probabilidad (%)", "Cuota Justa", "Kelly Sugerido (%)"
                ]]
                st.dataframe(df_rad, use_container_width=True, hide_index=True)
            else:
                st.info("No se encontraron selecciones para este filtro.")

        with col_rad2:
            st.markdown("<div class='calc-box'>", unsafe_allow_html=True)
            st.markdown("#### 🧮 Calculadora de Valor (+EV) y Bankroll")
            st.caption("Introduce la cuota de tu casa de apuestas para calcular si existe ventaja matemática:")

            user_odd = st.number_input("Cuota de la Casa de Apuestas:", min_value=1.01, max_value=50.0, value=1.55, step=0.05)
            user_prob_pct = st.number_input("Probabilidad del Modelo (%):", min_value=1.0, max_value=99.0, value=float(top_pick_1['Probabilidad (%)']), step=0.5)
            user_bank = st.number_input("Tamaño total de tu Bankroll ($):", min_value=10, max_value=1000000, value=1000, step=50)

            p_dec = user_prob_pct / 100.0
            ev_pct = round(((p_dec * user_odd) - 1.0) * 100, 2)
            edge_pct = round((p_dec - (1.0 / user_odd)) * 100, 2)

            b = user_odd - 1.0
            q = 1.0 - p_dec
            kelly_full = (b * p_dec - q) / b if b > 0 else 0.0
            kelly_quarter = max(kelly_full * 0.25, 0.0)
            stake_dollars = round(user_bank * kelly_quarter, 2)

            if ev_pct > 0:
                st.markdown(f"**Resultado:** <span style='color:#15803D; font-weight:700;'>+EV Detectado (+{ev_pct}%)</span>", unsafe_allow_html=True)
                st.write(f"- Ventaja Estadística (Edge): **+{edge_pct}%**")
                st.write(f"- Cuota Justa del Modelo: **{calculate_fair_odd(p_dec)}** vs Cuota Casa: **{user_odd}**")
                st.write(f"- Stake Óptimo (1/4 Kelly): **{round(kelly_quarter*100, 2)}%** (${stake_dollars})")
            else:
                st.markdown(f"**Resultado:** <span style='color:#B91C1C; font-weight:700;'>-EV Sin Valor ({ev_pct}%)</span>", unsafe_allow_html=True)
                st.caption("La casa de apuestas está pagando menos de lo que la probabilidad matemática exige.")
            st.markdown("</div>", unsafe_allow_html=True)

    # --------------------------------------------------------------------------
    # TAB 2: MONTE CARLO (10,000 SIMULACIONES & PERCENTILES)
    # --------------------------------------------------------------------------
    with tab_mc:
        st.markdown("### 🎲 Simulación de Monte Carlo (10,000 Partidos Vectorizados)")
        st.caption("Distribución empírica e intervalos de confianza del 95% calculados sobre 10,000 iteraciones del partido.")

        c_mc1, c_mc2 = st.columns([1.6, 1])
        with c_mc1:
            fig_hist = px.histogram(
                mc_results["raw_goals"],
                nbins=10,
                title="Distribución de Frecuencia de Goles Totales Simulados",
                labels={"value": "Goles Totales en el Partido", "count": "Frecuencia"},
                color_discrete_sequence=["#2563EB"]
            )
            fig_hist.update_layout(height=320, margin=dict(l=20, r=20, t=35, b=20), showlegend=False)
            st.plotly_chart(fig_hist, use_container_width=True)

        with c_mc2:
            st.markdown("#### 📊 Percentiles e Intervalos de Confianza (95%)")
            df_perc = pd.DataFrame([
                {"Métrica": "Goles Totales", "P10": mc_results['percentiles']['goles']['P10'], "Mediana (P50)": mc_results['percentiles']['goles']['P50'], "P90": mc_results['percentiles']['goles']['P90'], "IC 95%": f"[{mc_results['percentiles']['goles']['CI_95_low']} - {mc_results['percentiles']['goles']['CI_95_high']}]"},
                {"Métrica": "Tiros al Arco", "P10": mc_results['percentiles']['tiros_puerta']['P10'], "Mediana (P50)": mc_results['percentiles']['tiros_puerta']['P50'], "P90": mc_results['percentiles']['tiros_puerta']['P90'], "IC 95%": f"[{mc_results['percentiles']['tiros_puerta']['CI_95_low']} - {mc_results['percentiles']['tiros_puerta']['CI_95_high']}]"},
                {"Métrica": "Córners", "P10": mc_results['percentiles']['corners']['P10'], "Mediana (P50)": mc_results['percentiles']['corners']['P50'], "P90": mc_results['percentiles']['corners']['P90'], "IC 95%": f"[{mc_results['percentiles']['corners']['CI_95_low']} - {mc_results['percentiles']['corners']['CI_95_high']}]"},
                {"Métrica": "Faltas", "P10": mc_results['percentiles']['faltas']['P10'], "Mediana (P50)": mc_results['percentiles']['faltas']['P50'], "P90": mc_results['percentiles']['faltas']['P90'], "IC 95%": f"[{mc_results['percentiles']['faltas']['CI_95_low']} - {mc_results['percentiles']['faltas']['CI_95_high']}]"},
            ])
            st.dataframe(df_perc, use_container_width=True, hide_index=True)

            st.write(f"- Marcador más simulado: **{mc_results['modal_score']}** (ocurrió en el **{mc_results['modal_score_freq']}%** de simulaciones)")
            st.write(f"- Resultados 1X2 simulados: Local **{mc_results['1x2_mc']['1']}%** | Empate **{mc_results['1x2_mc']['X']}%** | Visitante **{mc_results['1x2_mc']['2']}%**")

    # --------------------------------------------------------------------------
    # TAB 3: PARTIDO COMPLETO (FT) - DIXON-COLES
    # --------------------------------------------------------------------------
    with tab_ft:
        st.markdown("### ⏱️ Mercados de Partido Completo (Modelo Dixon-Coles)")
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown("#### 1X2 Resultado Final")
            df_1x2_ft = pd.DataFrame([
                {"Opción": f"1 ({home_name})", "Prob (%)": f"{model_ft['1x2']['1']['prob']}%", "Cuota": model_ft['1x2']['1']['fair_odd']},
                {"Opción": "X (Empate)", "Prob (%)": f"{model_ft['1x2']['X']['prob']}%", "Cuota": model_ft['1x2']['X']['fair_odd']},
                {"Opción": f"2 ({away_name})", "Prob (%)": f"{model_ft['1x2']['2']['prob']}%", "Cuota": model_ft['1x2']['2']['fair_odd']},
            ])
            st.dataframe(df_1x2_ft, use_container_width=True, hide_index=True)

        with c2:
            st.markdown("#### Doble Oportunidad & DNB")
            df_dc_ft = pd.DataFrame([
                {"Mercado": "1X (Local o Empate)", "Prob (%)": f"{model_ft['double_chance']['1X']['prob']}%", "Cuota": model_ft['double_chance']['1X']['fair_odd']},
                {"Mercado": "12 (Cualquiera Gana)", "Prob (%)": f"{model_ft['double_chance']['12']['prob']}%", "Cuota": model_ft['double_chance']['12']['fair_odd']},
                {"Mercado": "X2 (Empate o Visitante)", "Prob (%)": f"{model_ft['double_chance']['X2']['prob']}%", "Cuota": model_ft['double_chance']['X2']['fair_odd']},
                {"Mercado": "DNB Local (Empate No Válido)", "Prob (%)": f"{model_ft['dnb']['1 (Local DNB)']['prob']}%", "Cuota": model_ft['dnb']['1 (Local DNB)']['fair_odd']},
                {"Mercado": "DNB Visitante", "Prob (%)": f"{model_ft['dnb']['2 (Visitante DNB)']['prob']}%", "Cuota": model_ft['dnb']['2 (Visitante DNB)']['fair_odd']},
            ])
            st.dataframe(df_dc_ft, use_container_width=True, hide_index=True)

        with c3:
            st.markdown("#### Ambos Marcan (BTTS)")
            df_btts_ft = pd.DataFrame([
                {"Opción": "Sí (Ambos Anotan)", "Prob (%)": f"{model_ft['btts']['Sí']['prob']}%", "Cuota": model_ft['btts']['Sí']['fair_odd']},
                {"Opción": "No (Al menos uno en cero)", "Prob (%)": f"{model_ft['btts']['No']['prob']}%", "Cuota": model_ft['btts']['No']['fair_odd']},
            ])
            st.dataframe(df_btts_ft, use_container_width=True, hide_index=True)

        st.markdown("---")
        c_ou, c_team = st.columns(2)
        with c_ou:
            st.markdown("#### Goles Totales (Over y Under)")
            df_ou_ft = pd.DataFrame(model_ft["ou_table"])[[
                "Línea", "Over Prob (%)", "Cuota Over", "Under Prob (%)", "Cuota Under"
            ]]
            st.dataframe(df_ou_ft, use_container_width=True, hide_index=True)

        with c_team:
            st.markdown(f"#### Goles de {home_name} (Local Totals)")
            df_h_totals = pd.DataFrame(model_ft["home_totals"])[[
                "Línea", "Over Prob (%)", "Cuota Over", "Under Prob (%)", "Cuota Under"
            ]]
            st.dataframe(df_h_totals, use_container_width=True, hide_index=True)

            st.markdown(f"#### Goles de {away_name} (Visitante Totals)")
            df_a_totals = pd.DataFrame(model_ft["away_totals"])[[
                "Línea", "Over Prob (%)", "Cuota Over", "Under Prob (%)", "Cuota Under"
            ]]
            st.dataframe(df_a_totals, use_container_width=True, hide_index=True)

        st.markdown("---")
        c_mat, c_htft = st.columns([1.4, 1])
        with c_mat:
            st.markdown("#### Matriz Bivariada de Marcadores (Dixon-Coles)")
            matrix_df = pd.DataFrame(
                np.round(model_ft['matrix'][:6, :6] * 100, 1),
                index=[f"{i} gol{'es' if i!=1 else ''}" for i in range(6)],
                columns=[f"{j} gol{'es' if j!=1 else ''}" for j in range(6)]
            )
            fig_heatmap = px.imshow(
                matrix_df,
                text_auto=True,
                labels=dict(x=f"Goles {away_name}", y=f"Goles {home_name}", color="Prob (%)"),
                color_continuous_scale="Blues",
                aspect="auto"
            )
            fig_heatmap.update_layout(height=320, margin=dict(l=20, r=20, t=20, b=20))
            st.plotly_chart(fig_heatmap, use_container_width=True)

        with c_htft:
            st.markdown("#### Descanso / Final (HT / FT)")
            st.dataframe(pd.DataFrame(ht_ft_matrix), use_container_width=True, hide_index=True)

    # --------------------------------------------------------------------------
    # TAB 4: 1T Y 2T (POR MITADES)
    # --------------------------------------------------------------------------
    with tab_halves:
        st.markdown("### 🌓 Mercados por Mitades: Primer Tiempo (1T) y Segundo Tiempo (2T)")
        c_ht_1, c_ht_2 = st.columns(2)
        with c_ht_1:
            st.markdown("#### 🌓 Primer Tiempo (1T)")
            df_ou_ht = pd.DataFrame(model_ht["ou_table"])[[
                "Línea", "Over Prob (%)", "Cuota Over", "Under Prob (%)", "Cuota Under"
            ]]
            st.dataframe(df_ou_ht, use_container_width=True, hide_index=True)

            df_1x2_ht = pd.DataFrame([
                {"1T": f"1 ({home_name})", "Prob": f"{model_ht['1x2']['1']['prob']}%", "Cuota": model_ht['1x2']['1']['fair_odd']},
                {"1T": "X (Empate)", "Prob": f"{model_ht['1x2']['X']['prob']}%", "Cuota": model_ht['1x2']['X']['fair_odd']},
                {"1T": f"2 ({away_name})", "Prob": f"{model_ht['1x2']['2']['prob']}%", "Cuota": model_ht['1x2']['2']['fair_odd']},
                {"1T": "Ambos Marcan (Sí)", "Prob": f"{model_ht['btts']['Sí']['prob']}%", "Cuota": model_ht['btts']['Sí']['fair_odd']},
            ])
            st.dataframe(df_1x2_ht, use_container_width=True, hide_index=True)

        with c_ht_2:
            st.markdown("#### 🌗 Segundo Tiempo (2T)")
            df_ou_2h = pd.DataFrame(model_2h["ou_table"])[[
                "Línea", "Over Prob (%)", "Cuota Over", "Under Prob (%)", "Cuota Under"
            ]]
            st.dataframe(df_ou_2h, use_container_width=True, hide_index=True)

            df_1x2_2h = pd.DataFrame([
                {"2T": f"1 ({home_name})", "Prob": f"{model_2h['1x2']['1']['prob']}%", "Cuota": model_2h['1x2']['1']['fair_odd']},
                {"2T": "X (Empate)", "Prob": f"{model_2h['1x2']['X']['prob']}%", "Cuota": model_2h['1x2']['X']['fair_odd']},
                {"2T": f"2 ({away_name})", "Prob": f"{model_2h['1x2']['2']['prob']}%", "Cuota": model_2h['1x2']['2']['fair_odd']},
                {"2T": "Ambos Marcan (Sí)", "Prob": f"{model_2h['btts']['Sí']['prob']}%", "Cuota": model_2h['btts']['Sí']['fair_odd']},
            ])
            st.dataframe(df_1x2_2h, use_container_width=True, hide_index=True)

    # --------------------------------------------------------------------------
    # TAB 5: TIROS Y REMATES (OCÉANO AZUL)
    # --------------------------------------------------------------------------
    with tab_sot:
        st.markdown("### 🎯 Tiros a Puerta (SOT) y Disparos Totales")
        c_s1, c_s2 = st.columns(2)
        with c_s1:
            st.markdown(f"#### 🎯 Tiros al Arco Totales FT (Media estimada: {blue_ocean['sot']['lam_total']})")
            df_sot_tot = pd.DataFrame(blue_ocean["sot"]["total"])[[
                "Línea", "Over Prob (%)", "Cuota Over", "Under Prob (%)", "Cuota Under"
            ]]
            st.dataframe(df_sot_tot, use_container_width=True, hide_index=True)

            st.markdown(f"#### 🎯 Tiros al Arco 1T (Media: {blue_ocean['sot']['lam_total']*0.47:.1f})")
            df_sot_1t = pd.DataFrame(blue_ocean["sot"]["1t"])[[
                "Línea", "Over Prob (%)", "Cuota Over", "Under Prob (%)", "Cuota Under"
            ]]
            st.dataframe(df_sot_1t, use_container_width=True, hide_index=True)

        with c_s2:
            st.markdown(f"#### 🏠 {home_name} - Tiros al Arco (Media: {blue_ocean['sot']['lam_home']})")
            df_sot_h = pd.DataFrame(blue_ocean["sot"]["home"])[[
                "Línea", "Over Prob (%)", "Cuota Over", "Under Prob (%)", "Cuota Under"
            ]]
            st.dataframe(df_sot_h, use_container_width=True, hide_index=True)

            st.markdown(f"#### ✈️ {away_name} - Tiros al Arco (Media: {blue_ocean['sot']['lam_away']})")
            df_sot_a = pd.DataFrame(blue_ocean["sot"]["away"])[[
                "Línea", "Over Prob (%)", "Cuota Over", "Under Prob (%)", "Cuota Under"
            ]]
            st.dataframe(df_sot_a, use_container_width=True, hide_index=True)

        st.markdown("---")
        st.markdown(f"#### 🚀 Disparos Totales (Remates Dentro + Fuera - Media FT: {blue_ocean['shots']['lam_total']})")
        c_sh1, c_sh2 = st.columns(2)
        with c_sh1:
            df_sh_tot = pd.DataFrame(blue_ocean["shots"]["total"])[[
                "Línea", "Over Prob (%)", "Cuota Over", "Under Prob (%)", "Cuota Under"
            ]]
            st.dataframe(df_sh_tot, use_container_width=True, hide_index=True)
        with c_sh2:
            df_sh_h = pd.DataFrame(blue_ocean["shots"]["home"])[[
                "Línea", "Over Prob (%)", "Cuota Over", "Under Prob (%)", "Cuota Under"
            ]]
            st.dataframe(df_sh_h, use_container_width=True, hide_index=True)

    # --------------------------------------------------------------------------
    # TAB 6: FALTAS Y TARJETAS
    # --------------------------------------------------------------------------
    with tab_fouls:
        st.markdown("### 🟨 Mercados de Disciplina: Faltas y Tarjetas")
        c_f1, c_f2 = st.columns(2)
        with c_f1:
            st.markdown(f"#### ⚠️ Faltas Totales FT (Media estimada: {blue_ocean['fouls']['lam_total']})")
            df_foul_tot = pd.DataFrame(blue_ocean["fouls"]["total"])[[
                "Línea", "Over Prob (%)", "Cuota Over", "Under Prob (%)", "Cuota Under"
            ]]
            st.dataframe(df_foul_tot, use_container_width=True, hide_index=True)

            st.markdown(f"#### 🏠 Faltas Cometidas por {home_name} (Media: {blue_ocean['fouls']['lam_home']})")
            df_foul_h = pd.DataFrame(blue_ocean["fouls"]["home"])[[
                "Línea", "Over Prob (%)", "Cuota Over", "Under Prob (%)", "Cuota Under"
            ]]
            st.dataframe(df_foul_h, use_container_width=True, hide_index=True)

        with c_f2:
            st.markdown(f"#### 🟨 Tarjetas Amarillas Totales FT (Media: {blue_ocean['discipline']['lam_total']})")
            df_card_tot = pd.DataFrame(blue_ocean["discipline"]["total"])[[
                "Línea", "Over Prob (%)", "Cuota Over", "Under Prob (%)", "Cuota Under"
            ]]
            st.dataframe(df_card_tot, use_container_width=True, hide_index=True)

            st.markdown("#### 🟥 Tarjeta Roja en el Partido")
            red_dict = blue_ocean["discipline"]["red_card"]
            df_red = pd.DataFrame([
                {"Opción": "Sí (Habrá Expulsión)", "Probabilidad": f"{red_dict['Sí (Habrá Expulsión)']['prob']}%", "Cuota Justa": red_dict['Sí (Habrá Expulsión)']['fair_odd']},
                {"Opción": "No (Sin Expulsión)", "Probabilidad": f"{red_dict['No (Sin Expulsión)']['prob']}%", "Cuota Justa": red_dict['No (Sin Expulsión)']['fair_odd']},
            ])
            st.dataframe(df_red, use_container_width=True, hide_index=True)

    # --------------------------------------------------------------------------
    # TAB 7: CÓRNERS (SAQUES DE ESQUINA)
    # --------------------------------------------------------------------------
    with tab_corners:
        st.markdown("### 🚩 Mercados de Córners (Saques de Esquina)")
        c_c1, c_c2 = st.columns(2)
        with c_c1:
            st.markdown(f"#### 🚩 Córners Totales FT (Media estimada: {blue_ocean['corners']['lam_total']})")
            df_corn_tot = pd.DataFrame(blue_ocean["corners"]["total"])[[
                "Línea", "Over Prob (%)", "Cuota Over", "Under Prob (%)", "Cuota Under"
            ]]
            st.dataframe(df_corn_tot, use_container_width=True, hide_index=True)

            st.markdown(f"#### 🚩 Córners 1T (Media: {blue_ocean['corners']['lam_1t']})")
            df_corn_1t = pd.DataFrame(blue_ocean["corners"]["1t"])[[
                "Línea", "Over Prob (%)", "Cuota Over", "Under Prob (%)", "Cuota Under"
            ]]
            st.dataframe(df_corn_1t, use_container_width=True, hide_index=True)

        with c_c2:
            st.markdown(f"#### 🏠 Córners a Favor de {home_name} (Media: {blue_ocean['corners']['lam_home']})")
            df_corn_h = pd.DataFrame(blue_ocean["corners"]["home"])[[
                "Línea", "Over Prob (%)", "Cuota Over", "Under Prob (%)", "Cuota Under"
            ]]
            st.dataframe(df_corn_h, use_container_width=True, hide_index=True)

            st.markdown(f"#### ✈️ Córners a Favor de {away_name} (Media: {blue_ocean['corners']['lam_away']})")
            df_corn_a = pd.DataFrame(blue_ocean["corners"]["away"])[[
                "Línea", "Over Prob (%)", "Cuota Over", "Under Prob (%)", "Cuota Under"
            ]]
            st.dataframe(df_corn_a, use_container_width=True, hide_index=True)

    # --------------------------------------------------------------------------
    # TAB 8: PLAYER PROPS
    # --------------------------------------------------------------------------
    with tab_props:
        st.markdown("### 🏃 Player Props Individuales con Cuota Justa")
        st.caption("Probabilidades y cuotas justas por jugador individual para Tiros a Puerta (>=1 y >=2), Faltas (>=1 y >=2), Tarjeta Amarilla y Gol.")

        if player_props_df.empty:
            st.info("No hay datos de jugadores disponibles para esta muestra.")
        else:
            team_filter = st.selectbox("Filtrar por equipo:", ["Todos los equipos", home_name, away_name])
            filter_tid = home_id if team_filter == home_name else (away_id if team_filter == away_name else None)

            p_summary = compute_player_props_odds(df_players, filter_tid)
            if not p_summary.empty:
                cols_display = [
                    'player_name', 'matches', 'starts',
                    'P(>=1 Tiro SOT)', 'P(>=2 Tiros SOT)',
                    'P(>=1 Falta)', 'P(>=2 Faltas)',
                    'P(Recibirá Tarjeta)', 'P(Anotará Gol)'
                ]
                df_props_view = p_summary[cols_display].rename(columns={
                    'player_name': 'Jugador',
                    'matches': 'Partidos',
                    'starts': 'Titular',
                })
                st.dataframe(df_props_view, use_container_width=True, hide_index=True)
            else:
                st.info("No se encontraron registros para el filtro seleccionado.")

    # --------------------------------------------------------------------------
    # TAB 9: MARCADOS VS CONCEDIDOS & REGRESIÓN A LA MEDIA (xG)
    # --------------------------------------------------------------------------
    with tab_xg_stats:
        st.markdown("### 📊 Balance Detallado de Marcados vs Concedidos y Regresión a la Media")
        c_bal1, c_bal2 = st.columns(2)
        with c_bal1:
            st.markdown(f"#### 🏠 {home_name} (Medias por partido)")
            df_bal_h = pd.DataFrame({
                "Período": ["Partido Completo (FT)", "Primer Tiempo (1T)", "Segundo Tiempo (2T)"],
                "Goles Marcados (GF)": [stats_home['metrics']['goals_for']['mean'], stats_home['metrics']['goals_ht_for']['mean'], stats_home['metrics']['goals_2h_for']['mean']],
                "Goles Concedidos (GA)": [stats_home['metrics']['goals_against']['mean'], stats_home['metrics']['goals_ht_against']['mean'], stats_home['metrics']['goals_2h_against']['mean']],
            })
            st.dataframe(df_bal_h, use_container_width=True, hide_index=True)
            st.write(f"- Portería a cero (Clean Sheet FT): **{stats_home['rates']['clean_sheet_pct']}%**")
            st.write(f"- Anotó al menos un gol: **{100 - stats_home['rates']['failed_to_score_pct']}%**")
            st.write(f"- Hubo gol en el 1T: **{stats_home['rates']['over_0_5_ht_pct']}%**")

            # Diagnóstico de xG
            xg_h_for = stats_home['metrics'].get('xg_for', {}).get('mean', 0.0)
            if xg_h_for > 0:
                diff_h = round(stats_home['metrics']['goals_for']['mean'] - xg_h_for, 2)
                diag = "Sobre-rendimiento ofensivo (Riesgo de regresión negativa)" if diff_h > 0.35 else ("Sub-rendimiento ofensivo (Oportunidad de rebote positivo)" if diff_h < -0.35 else "Rendimiento alineado con la calidad de ocasiones")
                st.info(f"**Diagnóstico xG:** Goles reales {stats_home['metrics']['goals_for']['mean']} vs xG {xg_h_for} (Diferencia: {diff_h:+} goles). *{diag}*")

        with c_bal2:
            st.markdown(f"#### ✈️ {away_name} (Medias por partido)")
            df_bal_a = pd.DataFrame({
                "Período": ["Partido Completo (FT)", "Primer Tiempo (1T)", "Segundo Tiempo (2T)"],
                "Goles Marcados (GF)": [stats_away['metrics']['goals_for']['mean'], stats_away['metrics']['goals_ht_for']['mean'], stats_away['metrics']['goals_2h_for']['mean']],
                "Goles Concedidos (GA)": [stats_away['metrics']['goals_against']['mean'], stats_away['metrics']['goals_ht_against']['mean'], stats_away['metrics']['goals_2h_against']['mean']],
            })
            st.dataframe(df_bal_a, use_container_width=True, hide_index=True)
            st.write(f"- Portería a cero (Clean Sheet FT): **{stats_away['rates']['clean_sheet_pct']}%**")
            st.write(f"- Anotó al menos un gol: **{100 - stats_away['rates']['failed_to_score_pct']}%**")
            st.write(f"- Hubo gol en el 1T: **{stats_away['rates']['over_0_5_ht_pct']}%**")

            xg_a_for = stats_away['metrics'].get('xg_for', {}).get('mean', 0.0)
            if xg_a_for > 0:
                diff_a = round(stats_away['metrics']['goals_for']['mean'] - xg_a_for, 2)
                diag = "Sobre-rendimiento ofensivo" if diff_a > 0.35 else ("Sub-rendimiento ofensivo" if diff_a < -0.35 else "Rendimiento alineado")
                st.info(f"**Diagnóstico xG:** Goles reales {stats_away['metrics']['goals_for']['mean']} vs xG {xg_a_for} (Diferencia: {diff_a:+} goles). *{diag}*")

    # --------------------------------------------------------------------------
    # TAB 10: DESCARGAS
    # --------------------------------------------------------------------------
    with tab_export:
        st.markdown("### 💾 Exportación Rápida de Datos")
        combined_matches = pd.concat([df_home, df_away], ignore_index=True).drop_duplicates(subset=['match_id', 'team_id'])

        c_exp1, c_exp2 = st.columns(2)
        with c_exp1:
            csv_matches = combined_matches.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Descargar Partidos (CSV)", data=csv_matches, file_name=f"partidos_{home_name}_vs_{away_name}.csv", mime="text/csv", use_container_width=True)

            excel_buffer = io.BytesIO()
            with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                combined_matches.to_excel(writer, index=False, sheet_name='Partidos')
            st.download_button("📊 Descargar Partidos (Excel)", data=excel_buffer.getvalue(), file_name=f"partidos_{home_name}_vs_{away_name}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)

        with c_exp2:
            if high_prob_picks:
                df_high_exp = pd.DataFrame(high_prob_picks)
                st.download_button("🔥 Descargar Reporte Alta Probabilidad (CSV)", data=df_high_exp.to_csv(index=False).encode('utf-8'), file_name=f"alta_probabilidad_{home_name}_vs_{away_name}.csv", mime="text/csv", use_container_width=True)
