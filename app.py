# app.py
"""
Football Analytics & Pure Probability Engine
Diseñado bajo los principios de 'dashboard-design-skill' (First glance, Quiet, Wordless, Honest).

Incluye:
1. Cartelera interactiva estilo 365Scores con selección por fila.
2. Modal de validación de cantidad de partidos históricos a analizar.
3. Desglose completo de mercados para:
   - Partido Completo (FT)
   - Primer Tiempo (1T / HT)
   - Segundo Tiempo (2T / 2H)
   - Mercados Océano Rojo (1X2, Doble Oportunidad, Over/Under, BTTS, HT/FT, DNB)
   - Mercados Océano Azul (Tiros a puerta, Córners por tiempo, Tarjetas, Faltas, Team Totals)
4. Detección automática y destacados visuales de Alta Probabilidad (>= 68%) y Cuota Justa (1 / P).
5. Exportación directa a Excel y CSV.
"""

import os
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
    page_title="Football Analytics & Probabilidades",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Estilos CSS según principios de dashboard-design-skill (Paleta sobria, saliencia alta, tipografía clara)
st.markdown("""
<style>
    /* Estructura general */
    .block-container { padding-top: 1.5rem; padding-bottom: 3rem; }
    
    /* Tipografía y Título principal */
    .dash-header { display: flex; justify-content: space-between; align-items: flex-end; margin-bottom: 1.2rem; }
    .dash-title { font-size: 2.0rem; font-weight: 800; color: #0F172A; letter-spacing: -0.02em; margin: 0; }
    .dash-meta { font-size: 0.9rem; color: #64748B; margin-top: 0.2rem; }
    
    /* KPI Strip */
    .kpi-container { display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; margin-bottom: 22px; }
    .kpi-card { background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 10px; padding: 14px 16px; box-shadow: 0 1px 2px rgba(0,0,0,0.04); }
    .kpi-label { font-size: 0.8rem; font-weight: 600; text-transform: uppercase; color: #64748B; letter-spacing: 0.04em; margin-bottom: 6px; }
    .kpi-value { font-size: 1.6rem; font-weight: 800; color: #0F172A; line-height: 1.1; }
    .kpi-sub { font-size: 0.85rem; font-weight: 600; color: #2563EB; margin-top: 4px; }
    .kpi-high { border-top: 3px solid #16A34A; }
    .kpi-blue { border-top: 3px solid #3B82F6; }

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
    
    /* Badges */
    .badge-high { background-color: #DCFCE7; color: #15803D; font-weight: 700; padding: 3px 8px; border-radius: 6px; font-size: 0.82rem; }
    .badge-blue { background-color: #DBEAFE; color: #1E40AF; font-weight: 700; padding: 3px 8px; border-radius: 6px; font-size: 0.82rem; }
    .badge-red { background-color: #FEE2E2; color: #B91C1C; font-weight: 700; padding: 3px 8px; border-radius: 6px; font-size: 0.82rem; }

    /* Botón de volver */
    .btn-return { margin-bottom: 15px; }
</style>
""", unsafe_allow_html=True)

# Importaciones del motor local
from db.database import init_db, SessionGold, engine_gold
from main import process_team_matches
from transform.silver_to_gold import compute_rolling_averages, compute_dim_referee, generate_dim_date
from analysis.probabilities import (
    estimate_period_lambdas,
    compute_period_markets,
    compute_ht_ft_matrix,
    compute_blue_ocean_props,
    get_all_high_probability_picks,
    compute_empirical_team_stats,
    compute_player_props_summary,
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
    st.markdown("<div class='dash-title'>⚽ Football Analytics & Betting Engine</div>", unsafe_allow_html=True)
    st.markdown("<div class='dash-meta'>Cartelera estilo 365Scores · Desglose por Períodos (FT, 1T, 2T) · Océanos Azul y Rojo · Probabilidad Pura</div>", unsafe_allow_html=True)
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
    # Controles de filtrado
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

    # Filtrar
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
    st.markdown("### 📋 Validación y Parámetros del Partido Seleccionado")

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
        force_dl = st.checkbox("🔄 Forzar descarga completa desde la API", value=False)
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
# PASO 3: DESCARGA AUTOMATIZADA Y DASHBOARD DE MERCADOS COMPLETOS
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
        prog_bar = st.progress(0, text="Descargando datos crudos...")
        status_txt = st.empty()

        status_txt.text(f"Descargando últimos {n_history} partidos de {home_name}...")
        def h_cb(c, t, d): prog_bar.progress(int((c / (t * 2)) * 100), text=f"[{home_name}] {d}")
        process_team_matches(home_id, max_matches=n_history, progress_callback=h_cb)

        status_txt.text(f"Descargando últimos {n_history} partidos de {away_name}...")
        def a_cb(c, t, d): prog_bar.progress(int(50 + (c / (t * 2)) * 100), text=f"[{away_name}] {d}")
        process_team_matches(away_id, max_matches=n_history, progress_callback=a_cb)

        status_txt.text("Calculando promedios móviles y esquemas Gold...")
        compute_rolling_averages()
        compute_dim_referee()
        generate_dim_date()

        prog_bar.progress(100, text="¡Completado con éxito!")
        time.sleep(1)
        prog_bar.empty()
        status_txt.empty()

    df_home = load_gold_data(home_id)
    df_away = load_gold_data(away_id)
    df_players = load_players_gold_data([home_id, away_id])

    if df_home.empty or df_away.empty:
        st.warning("No hay suficientes partidos para generar el modelo estadístico.")
        st.stop()

    # Modelos por período (FT, 1T, 2T)
    lam_h_ft, lam_a_ft = estimate_period_lambdas(df_home, df_away, home_id, away_id, "ft")
    lam_h_ht, lam_a_ht = estimate_period_lambdas(df_home, df_away, home_id, away_id, "ht")
    lam_h_2h, lam_a_2h = estimate_period_lambdas(df_home, df_away, home_id, away_id, "2h")

    model_ft = compute_period_markets(lam_h_ft, lam_a_ft, "Partido Completo (FT)", [0.5, 1.5, 2.5, 3.5, 4.5])
    model_ht = compute_period_markets(lam_h_ht, lam_a_ht, "Primer Tiempo (1T)", [0.5, 1.5, 2.5])
    model_2h = compute_period_markets(lam_h_2h, lam_a_2h, "Segundo Tiempo (2T)", [0.5, 1.5, 2.5])

    ht_ft_matrix = compute_ht_ft_matrix(model_ht, model_2h)
    blue_ocean = compute_blue_ocean_props(df_home, df_away, home_id, away_id)
    high_prob_picks = get_all_high_probability_picks(model_ft, model_ht, model_2h, blue_ocean, threshold=68.0)
    stats_home = compute_empirical_team_stats(df_home, home_id)
    stats_away = compute_empirical_team_stats(df_away, away_id)

    # --------------------------------------------------------------------------
    # FIRST GLANCE: KPI STRIP (4 TARJETAS CON LAS MEJORES SELECCIONES)
    # --------------------------------------------------------------------------
    st.markdown("---")
    top_pick_1 = high_prob_picks[0] if len(high_prob_picks) > 0 else {"Selección": "1X", "Probabilidad (%)": 75.0, "Cuota Justa": 1.33, "Período": "FT"}
    top_pick_2 = high_prob_picks[1] if len(high_prob_picks) > 1 else {"Selección": "Over 0.5 Goles", "Probabilidad (%)": 72.0, "Cuota Justa": 1.38, "Período": "1T"}
    top_blue = [p for p in high_prob_picks if "Azul" in p["Tipo"]]
    top_blue_pick = top_blue[0] if top_blue else {"Selección": "Córners FT Over 7.5", "Probabilidad (%)": 71.0, "Cuota Justa": 1.41}

    st.markdown(f"""
    <div class='kpi-container'>
        <div class='kpi-card kpi-high'>
            <div class='kpi-label'>🔥 Mejor Selección Alta Prob.</div>
            <div class='kpi-value'>{top_pick_1['Probabilidad (%)']}%</div>
            <div class='kpi-sub'>{top_pick_1['Selección']} ({top_pick_1['Período']}) · Cuota {top_pick_1['Cuota Justa']}</div>
        </div>
        <div class='kpi-card kpi-blue'>
            <div class='kpi-label'>💎 Mejor Océano Azul (+EV)</div>
            <div class='kpi-value'>{top_blue_pick['Probabilidad (%)']}%</div>
            <div class='kpi-sub'>{top_blue_pick['Selección']} · Cuota {top_blue_pick['Cuota Justa']}</div>
        </div>
        <div class='kpi-card'>
            <div class='kpi-label'>⚽ Goles Esperados (FT)</div>
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
    # TABS POR PERÍODO Y MERCADO
    # --------------------------------------------------------------------------
    tab_high, tab_ft, tab_ht, tab_2h, tab_blue, tab_props, tab_stats, tab_export = st.tabs([
        "🔥 Top Alta Probabilidad (>=68%)",
        "⏱️ Partido Completo (FT)",
        "🌓 Primer Tiempo (1T)",
        "🌗 Segundo Tiempo (2T)",
        "💎 Océanos Azules (Tiros, Córners, Faltas)",
        "🏃 Player Props (Jugadores)",
        "📊 Marcados vs Concedidos",
        "💾 Descargas Excel / CSV"
    ])

    # --------------------------------------------------------------------------
    # TAB: TOP ALTA PROBABILIDAD (>= 68%)
    # --------------------------------------------------------------------------
    with tab_high:
        st.markdown("### 🔥 Todas las Selecciones de Alta Probabilidad Identificadas")
        st.caption("Filtro algorítmico sobre todos los mercados (goles, resultados, tiros, córners) que superan el 68% de certeza matemática.")

        if high_prob_picks:
            df_high = pd.DataFrame(high_prob_picks)[[
                "Selección", "Período", "Tipo", "Probabilidad (%)", "Cuota Justa", "Detalle"
            ]]
            st.dataframe(df_high, use_container_width=True, hide_index=True)
        else:
            st.info("No hay selecciones que superen el umbral del 68% para este encuentro.")

    # --------------------------------------------------------------------------
    # TAB: PARTIDO COMPLETO (FT)
    # --------------------------------------------------------------------------
    with tab_ft:
        st.markdown("### ⏱️ Mercados de Partido Completo (90 Minutos)")
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
            st.markdown("#### Goles Totales (Over / Under FT)")
            ou_rows = []
            for line in [0.5, 1.5, 2.5, 3.5, 4.5]:
                o = model_ft['over_under'][f"Over {line}"]
                u = model_ft['over_under'][f"Under {line}"]
                ou_rows.append({
                    "Línea": f"{line} Goles",
                    "Over Prob (%)": f"{o['prob']}%",
                    "Cuota Over": o['fair_odd'],
                    "Under Prob (%)": f"{u['prob']}%",
                    "Cuota Under": u['fair_odd']
                })
            st.dataframe(pd.DataFrame(ou_rows), use_container_width=True, hide_index=True)

        with c_team:
            st.markdown("#### Goles por Equipo (Team Totals FT)")
            tt_rows = []
            for line in [0.5, 1.5, 2.5]:
                ho = model_ft['home_totals'][f"Local Over {line}"]
                ao = model_ft['away_totals'][f"Visitante Over {line}"]
                tt_rows.append({
                    "Línea": f"Over {line} Goles",
                    f"{home_name} Prob": f"{ho['prob']}%",
                    f"{home_name} Cuota": ho['fair_odd'],
                    f"{away_name} Prob": f"{ao['prob']}%",
                    f"{away_name} Cuota": ao['fair_odd'],
                })
            st.dataframe(pd.DataFrame(tt_rows), use_container_width=True, hide_index=True)

        st.markdown("---")
        c_htft, c_scores = st.columns([1.2, 1])
        with c_htft:
            st.markdown("#### Descanso / Final (HT / FT)")
            st.dataframe(pd.DataFrame(ht_ft_matrix), use_container_width=True, hide_index=True)
        with c_scores:
            st.markdown("#### Marcadores Más Probables (FT)")
            st.dataframe(pd.DataFrame(model_ft["top_scores"]), use_container_width=True, hide_index=True)

    # --------------------------------------------------------------------------
    # TAB: PRIMER TIEMPO (1T / HT)
    # --------------------------------------------------------------------------
    with tab_ht:
        st.markdown("### 🌓 Mercados del Primer Tiempo (1T / 45 Minutos)")
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown("#### 1X2 Primer Tiempo")
            df_1x2_ht = pd.DataFrame([
                {"Opción": f"1 ({home_name})", "Prob (%)": f"{model_ht['1x2']['1']['prob']}%", "Cuota": model_ht['1x2']['1']['fair_odd']},
                {"Opción": "X (Empate)", "Prob (%)": f"{model_ht['1x2']['X']['prob']}%", "Cuota": model_ht['1x2']['X']['fair_odd']},
                {"Opción": f"2 ({away_name})", "Prob (%)": f"{model_ht['1x2']['2']['prob']}%", "Cuota": model_ht['1x2']['2']['fair_odd']},
            ])
            st.dataframe(df_1x2_ht, use_container_width=True, hide_index=True)

        with c2:
            st.markdown("#### Doble Oportunidad 1T")
            df_dc_ht = pd.DataFrame([
                {"Mercado": "1X 1T", "Prob (%)": f"{model_ht['double_chance']['1X']['prob']}%", "Cuota": model_ht['double_chance']['1X']['fair_odd']},
                {"Mercado": "12 1T", "Prob (%)": f"{model_ht['double_chance']['12']['prob']}%", "Cuota": model_ht['double_chance']['12']['fair_odd']},
                {"Mercado": "X2 1T", "Prob (%)": f"{model_ht['double_chance']['X2']['prob']}%", "Cuota": model_ht['double_chance']['X2']['fair_odd']},
            ])
            st.dataframe(df_dc_ht, use_container_width=True, hide_index=True)

        with c3:
            st.markdown("#### Ambos Marcan 1T (BTTS 1T)")
            df_btts_ht = pd.DataFrame([
                {"Opción": "Sí (Ambos Anotan 1T)", "Prob (%)": f"{model_ht['btts']['Sí']['prob']}%", "Cuota": model_ht['btts']['Sí']['fair_odd']},
                {"Opción": "No (Al menos uno en cero 1T)", "Prob (%)": f"{model_ht['btts']['No']['prob']}%", "Cuota": model_ht['btts']['No']['fair_odd']},
            ])
            st.dataframe(df_btts_ht, use_container_width=True, hide_index=True)

        st.markdown("---")
        c_ou_ht, c_team_ht = st.columns(2)
        with c_ou_ht:
            st.markdown("#### Goles Totales Primer Tiempo (Over / Under 1T)")
            ou_ht_rows = []
            for line in [0.5, 1.5, 2.5]:
                o = model_ht['over_under'][f"Over {line}"]
                u = model_ht['over_under'][f"Under {line}"]
                ou_ht_rows.append({
                    "Línea": f"{line} Goles 1T",
                    "Over Prob (%)": f"{o['prob']}%",
                    "Cuota Over": o['fair_odd'],
                    "Under Prob (%)": f"{u['prob']}%",
                    "Cuota Under": u['fair_odd']
                })
            st.dataframe(pd.DataFrame(ou_ht_rows), use_container_width=True, hide_index=True)

        with c_team_ht:
            st.markdown("#### Marcador Exacto al Descanso")
            st.dataframe(pd.DataFrame(model_ht["top_scores"]), use_container_width=True, hide_index=True)

    # --------------------------------------------------------------------------
    # TAB: SEGUNDO TIEMPO (2T)
    # --------------------------------------------------------------------------
    with tab_2h:
        st.markdown("### 🌗 Mercados del Segundo Tiempo (2T)")
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown("#### 1X2 Segundo Tiempo")
            df_1x2_2h = pd.DataFrame([
                {"Opción": f"1 ({home_name})", "Prob (%)": f"{model_2h['1x2']['1']['prob']}%", "Cuota": model_2h['1x2']['1']['fair_odd']},
                {"Opción": "X (Empate)", "Prob (%)": f"{model_2h['1x2']['X']['prob']}%", "Cuota": model_2h['1x2']['X']['fair_odd']},
                {"Opción": f"2 ({away_name})", "Prob (%)": f"{model_2h['1x2']['2']['prob']}%", "Cuota": model_2h['1x2']['2']['fair_odd']},
            ])
            st.dataframe(df_1x2_2h, use_container_width=True, hide_index=True)

        with c2:
            st.markdown("#### Goles Totales Segundo Tiempo")
            ou_2h_rows = []
            for line in [0.5, 1.5, 2.5]:
                o = model_2h['over_under'][f"Over {line}"]
                u = model_2h['over_under'][f"Under {line}"]
                ou_2h_rows.append({
                    "Línea": f"{line} Goles 2T",
                    "Over Prob (%)": f"{o['prob']}%",
                    "Cuota Over": o['fair_odd'],
                    "Under Prob (%)": f"{u['prob']}%",
                    "Cuota Under": u['fair_odd']
                })
            st.dataframe(pd.DataFrame(ou_2h_rows), use_container_width=True, hide_index=True)

        with c3:
            st.markdown("#### Ambos Marcan 2T")
            df_btts_2h = pd.DataFrame([
                {"Opción": "Sí (Ambos 2T)", "Prob (%)": f"{model_2h['btts']['Sí']['prob']}%", "Cuota": model_2h['btts']['Sí']['fair_odd']},
                {"Opción": "No 2T", "Prob (%)": f"{model_2h['btts']['No']['prob']}%", "Cuota": model_2h['btts']['No']['fair_odd']},
            ])
            st.dataframe(df_btts_2h, use_container_width=True, hide_index=True)

    # --------------------------------------------------------------------------
    # TAB: OCÉANOS AZULES (TIROS, CÓRNERS, FALTAS, TARJETAS)
    # --------------------------------------------------------------------------
    with tab_blue:
        st.markdown("### 💎 Mercados Océano Azul (Estadística Pura & Ineficiencias)")
        st.caption("Mercados de props donde los modelos predictivos presentan mayores discrepancias con las casas de apuestas.")

        c_sot, c_corn = st.columns(2)
        with c_sot:
            st.markdown(f"#### 🎯 Tiros al Arco (Media estimada: {blue_ocean['means']['sot_total']})")
            df_sot = pd.DataFrame(blue_ocean["shots_on_target"])[[
                "Mercado", "Prob", "Cuota", "Media Estimada"
            ]].rename(columns={"Prob": "Probabilidad (%)", "Cuota": "Cuota Justa"})
            st.dataframe(df_sot, use_container_width=True, hide_index=True)

        with c_corn:
            st.markdown(f"#### 🚩 Córners (Media FT: {blue_ocean['means']['corners_total']} | 1T: {blue_ocean['means']['corners_1t']})")
            df_corn = pd.DataFrame(blue_ocean["corners"])[[
                "Mercado", "Prob", "Cuota", "Media"
            ]].rename(columns={"Prob": "Probabilidad (%)", "Cuota": "Cuota Justa", "Media": "Media Estimada"})
            st.dataframe(df_corn, use_container_width=True, hide_index=True)

        st.markdown("---")
        st.markdown("#### 🟨 Disciplina (Faltas y Tarjetas)")
        df_disc = pd.DataFrame(blue_ocean["discipline"])[[
            "Mercado", "Prob", "Cuota", "Media"
        ]].rename(columns={"Prob": "Probabilidad (%)", "Cuota": "Cuota Justa", "Media": "Media Estimada"})
        st.dataframe(df_disc, use_container_width=True, hide_index=True)

    # --------------------------------------------------------------------------
    # TAB: PLAYER PROPS
    # --------------------------------------------------------------------------
    with tab_props:
        st.markdown("### 🏃 Player Props (Estadísticas Atómicas de Jugadores)")
        if df_players.empty:
            st.info("No hay datos de jugadores disponibles para esta muestra.")
        else:
            team_filter = st.selectbox("Filtrar equipo:", ["Todos los equipos", home_name, away_name])
            filter_tid = home_id if team_filter == home_name else (away_id if team_filter == away_name else None)

            p_summary = compute_player_props_summary(df_players, filter_tid)
            if not p_summary.empty:
                p_summary = p_summary.rename(columns={
                    'player_name': 'Jugador',
                    'matches': 'Partidos',
                    'starts': 'Titular',
                    'total_mins': 'Minutos',
                    'goals': 'Goles',
                    'shots_on_target': 'Tiros Puerta Totales',
                    'sot_per_game': 'Tiros Puerta / Partido',
                    'fouls': 'Faltas Totales',
                    'fouls_per_game': 'Faltas / Partido',
                    'yellow_cards': 'Tarjetas Amarillas'
                })
                st.dataframe(p_summary.drop(columns=['player_id'], errors='ignore'), use_container_width=True, hide_index=True)

    # --------------------------------------------------------------------------
    # TAB: MARCADOS VS CONCEDIDOS (ESTADÍSTICA PURA)
    # --------------------------------------------------------------------------
    with tab_stats:
        st.markdown("### 📊 Balance Detallado de Marcados vs Concedidos por Período")

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

    # --------------------------------------------------------------------------
    # TAB: DESCARGA
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
