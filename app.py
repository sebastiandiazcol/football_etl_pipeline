# app.py
"""
Football Analytics & Pure Probability Engine
Web App interactiva:
1. Cartelera visual estilo 365Scores de los Partidos de Hoy (selección interactiva por filas).
2. Paso de Validación y confirmación: Selección de cantidad de partidos históricos a analizar.
3. Descarga y procesamiento Medallion automatizado (Bronze -> Silver -> Gold).
4. Motor de Probabilidades Estadísticas Puras (Distribución de Poisson Bivariada, 1X2, Over/Under, BTTS).
5. Análisis descriptivo de rendimiento y Player Props (tiros a puerta, faltas, tarjetas).
6. Exportación instantánea en Excel (.xlsx) y CSV.
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
from sqlalchemy import text

# Configuración inicial de Streamlit
st.set_page_config(
    page_title="Football Analytics & Probabilidades",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Estilos CSS personalizados inspirados en 365Scores
st.markdown("""
<style>
    .main-title {
        font-size: 2.2rem;
        font-weight: 800;
        color: #1E3A8A;
        margin-bottom: 0.2rem;
    }
    .main-subtitle {
        font-size: 1.05rem;
        color: #4B5563;
        margin-bottom: 1.5rem;
    }
    .match-validation-card {
        background: #FFFFFF;
        border: 2px solid #2563EB;
        border-radius: 12px;
        padding: 22px;
        margin-bottom: 24px;
        box-shadow: 0 4px 12px rgba(37, 99, 235, 0.12);
    }
    .match-header-box {
        display: flex;
        justify-content: space-between;
        align-items: center;
        background: #F1F5F9;
        padding: 12px 18px;
        border-radius: 8px;
        margin-bottom: 15px;
    }
    .team-title {
        font-size: 1.4rem;
        font-weight: 700;
        color: #0F172A;
    }
    .comp-badge {
        background: #DBEAFE;
        color: #1E40AF;
        padding: 4px 10px;
        border-radius: 6px;
        font-weight: 600;
        font-size: 0.88rem;
    }
    .status-live {
        background: #FEE2E2;
        color: #991B1B;
        padding: 4px 10px;
        border-radius: 6px;
        font-weight: 700;
    }
    .status-finished {
        background: #DCFCE7;
        color: #166534;
        padding: 4px 10px;
        border-radius: 6px;
        font-weight: 600;
    }
    .status-scheduled {
        background: #E0E7FF;
        color: #3730A3;
        padding: 4px 10px;
        border-radius: 6px;
        font-weight: 600;
    }
    .metric-card {
        background: #F8FAFC;
        border: 1px solid #E2E8F0;
        border-radius: 10px;
        padding: 16px;
        text-align: center;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    .metric-title {
        font-size: 0.88rem;
        color: #64748B;
        font-weight: 600;
        text-transform: uppercase;
    }
    .metric-value {
        font-size: 1.85rem;
        font-weight: 800;
        color: #0F172A;
    }
    .metric-odd {
        font-size: 0.95rem;
        color: #2563EB;
        font-weight: 700;
        margin-top: 4px;
    }
</style>
""", unsafe_allow_html=True)

# Importaciones locales del pipeline
from db.database import init_db, SessionGold, engine_gold
from db.models.gold_models import FactTeamMatch, FactPlayerMatch, DimTeam
from main import process_team_matches
from transform.silver_to_gold import compute_rolling_averages, compute_dim_referee, generate_dim_date
from analysis.probabilities import (
    compute_poisson_match_probabilities,
    estimate_lambdas_from_history,
    compute_empirical_team_stats,
    compute_player_props_summary,
    calculate_fair_odd
)

# Inicializar Base de Datos SQLite
init_db()

# Inicializar Session State para navegación
if "selected_match" not in st.session_state:
    st.session_state.selected_match = None
if "analysis_confirmed" not in st.session_state:
    st.session_state.analysis_confirmed = False
if "confirmed_matches_history" not in st.session_state:
    st.session_state.confirmed_matches_history = 10


# ==============================================================================
# FUNCIONES DE CONSULTA Y API
# ==============================================================================
@st.cache_data(ttl=180)
def fetch_day_fixtures(date_str: str):
    """
    Descarga la cartelera completa de partidos de fútbol para una fecha (DD/MM/YYYY)
    desde la API de 365scores.
    """
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
        countries = {c["id"]: c.get("name") for c in data.get("countries", [])}

        games = []
        for g in data.get("games", []):
            if g.get("sportId") != 1:  # Solo Fútbol
                continue

            comp_id = g.get("competitionId")
            comp_name = competitions.get(comp_id, "Torneo Internacional")

            home = g.get("homeCompetitor", {})
            away = g.get("awayCompetitor", {})
            home_id = home.get("id")
            away_id = away.get("id")
            home_name = home.get("name", "Local")
            away_name = away.get("name", "Visitante")

            if not home_id or not away_id:
                continue

            start_raw = g.get("startTime", "")
            time_str = "--:--"
            if "T" in start_raw:
                time_str = start_raw.split("T")[1][:5]

            status_text = g.get("statusText", "Prog.")
            home_score = home.get("score")
            away_score = away.get("score")

            # Formato de marcador o VS
            if home_score is not None and away_score is not None and status_text != "Prog.":
                score_display = f"{int(home_score)} - {int(away_score)}"
            else:
                score_display = "vs"

            # Categorización de estado
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
                "Equipo Local": home_name,
                "Marcador": score_display,
                "Equipo Visitante": away_name,
                "Estado": status_text,
                "Categoría": cat,
                "home_id": home_id,
                "away_id": away_id,
                "home_name": home_name,
                "away_name": away_name,
                "competition": comp_name,
            })

        return games
    except Exception as e:
        st.error(f"Error consultando partidos: {e}")
        return []


@st.cache_data(ttl=3600)
def search_teams_api(query: str):
    """Busca equipos en la API de 365scores."""
    if not query or len(query.strip()) < 2:
        return []
    url = "https://webws.365scores.com/web/search/"
    params = {'appTypeId': 5, 'langId': 14, 'timezoneName': 'America/Bogota', 'q': query.strip()}
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        r = requests.get(url, params=params, headers=headers, timeout=10)
        r.raise_for_status()
        data = r.json()
        countries = {c.get('id'): c.get('name') for c in data.get('countries', [])}
        competitions = {c.get('id'): c.get('name') for c in data.get('competitions', [])}
        comps = [c for c in data.get('competitors', []) if c.get('sportId') == 1]
        results = []
        for c in comps:
            country = countries.get(c.get('countryId'), 'País desconocido')
            league = competitions.get(c.get('mainCompetitionId'), 'Torneo desconocido')
            results.append({
                'id': c.get('id'),
                'name': c.get('name'),
                'country': country,
                'league': league,
                'display': f"{c.get('name')} | {country} ({league}) [ID: {c.get('id')}]"
            })
        return results
    except Exception as e:
        return []


def load_gold_data(team_id: int):
    """Carga los partidos de un equipo desde la capa Gold."""
    try:
        query = f"""
        SELECT f.*, t.team_name, opp.team_name AS opponent_name
        FROM fact_team_match f
        LEFT JOIN dim_team t ON f.team_id = t.team_id
        LEFT JOIN dim_team opp ON f.opponent_id = opp.team_id
        WHERE f.team_id = {team_id}
        ORDER BY f.match_id DESC
        """
        df = pd.read_sql(query, engine_gold)
        return df
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
        df = pd.read_sql(query, engine_gold)
        return df
    except Exception:
        return pd.DataFrame()


# ==============================================================================
# HEADER DE LA APLICACIÓN
# ==============================================================================
st.markdown("<div class='main-title'>⚽ Football Analytics & Pure Probability Engine</div>", unsafe_allow_html=True)
st.markdown("<div class='main-subtitle'>Cartelera interactiva estilo 365Scores, validación de partidos y modelado estadístico puro de Poisson.</div>", unsafe_allow_html=True)


# ==============================================================================
# BARRA LATERAL (MODO Y FECHA)
# ==============================================================================
st.sidebar.markdown("## 🧭 Menú")
app_mode = st.sidebar.radio(
    "Selecciona el modo:",
    ["📅 Cartelera de Partidos (Estilo 365)", "🔍 Búsqueda Manual de Equipos"],
    index=0
)

# ------------------------------------------------------------------------------
# SI ESTÁ EN MODO MANUAL
# ------------------------------------------------------------------------------
if app_mode == "🔍 Búsqueda Manual de Equipos":
    st.sidebar.markdown("### 🔍 Búsqueda Manual")
    h_query = st.sidebar.text_input("Equipo Local:", value="Real Madrid")
    h_res = search_teams_api(h_query)
    h_pick = None
    if h_res:
        h_dict = {x['display']: x for x in h_res}
        h_sel = st.sidebar.selectbox("Confirmar Local:", list(h_dict.keys()), key="man_h")
        h_pick = h_dict[h_sel]

    a_query = st.sidebar.text_input("Equipo Visitante:", value="Barcelona")
    a_res = search_teams_api(a_query)
    a_pick = None
    if a_res:
        a_dict = {x['display']: x for x in a_res}
        a_sel = st.sidebar.selectbox("Confirmar Visitante:", list(a_dict.keys()), key="man_a")
        a_pick = a_dict[a_sel]

    if st.sidebar.button("Cargar Partido Manual", type="primary", use_container_width=True):
        if h_pick and a_pick:
            st.session_state.selected_match = {
                "home_id": h_pick['id'],
                "home_name": h_pick['name'],
                "away_id": a_pick['id'],
                "away_name": a_pick['name'],
                "competition": "Amistoso / Búsqueda Manual",
                "Hora": "--:--",
                "Estado": "Manual"
            }
            st.session_state.analysis_confirmed = False
            st.rerun()


# ==============================================================================
# PASO 1: CARTELERA ESTILO 365SCORES (SI NO HAY ANÁLISIS CONFIRMADO)
# ==============================================================================
if app_mode == "📅 Cartelera de Partidos (Estilo 365)":
    # Barra de Filtros estilo 365
    c_f1, c_f2, c_f3, c_f4 = st.columns([1.2, 1.5, 1.5, 2])
    with c_f1:
        match_date = st.date_input("📅 Fecha:", date.today(), label_visibility="collapsed")
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

    # Filtrar partidos
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

    st.markdown(f"**Partidos encontrados:** `{len(filtered_games)}` partidos en agenda")

    # Mostrar la tabla interactiva 365Scores
    if filtered_games:
        df_display = pd.DataFrame(filtered_games)[[
            "Hora", "Torneo", "Equipo Local", "Marcador", "Equipo Visitante", "Estado"
        ]]

        st.caption("👆 **Haz clic sobre cualquier fila** de la tabla para seleccionar el partido a analizar:")
        
        # Selección interactiva de fila con st.dataframe
        selection = st.dataframe(
            df_display,
            on_select="rerun",
            selection_mode="single-row",
            use_container_width=True,
            hide_index=True,
            height=380
        )

        # Si el usuario hace clic en una fila, guardamos en session_state
        if selection and selection.get("selection") and selection["selection"].get("rows"):
            selected_row_idx = selection["selection"]["rows"][0]
            if 0 <= selected_row_idx < len(filtered_games):
                chosen = filtered_games[selected_row_idx]
                st.session_state.selected_match = chosen
                st.session_state.analysis_confirmed = False
                st.rerun()

    else:
        st.info("No se encontraron partidos con los filtros seleccionados.")


# ==============================================================================
# PASO 2: TARJETA DE VALIDACIÓN DEL PARTIDO SELECCIONADO
# ==============================================================================
if st.session_state.selected_match:
    match = st.session_state.selected_match

    st.markdown("---")
    st.markdown("### 📋 Validación del Partido a Analizar")

    st.markdown(f"""
    <div class='match-validation-card'>
        <div class='match-header-box'>
            <span class='comp-badge'>🏆 {match.get('competition', match.get('Torneo', 'Torneo'))}</span>
            <span class='status-scheduled'>⏰ {match.get('time', match.get('Hora', '--:--'))} | 📌 {match.get('status', match.get('Estado', ''))}</span>
        </div>
        <div style='text-align: center; margin: 15px 0;'>
            <span class='team-title'>🏠 {match['home_name']}</span>
            <span style='font-size: 1.5rem; font-weight: 800; color: #2563EB; margin: 0 20px;'>VS</span>
            <span class='team-title'>✈️ {match['away_name']}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Controles de validación antes de descargar
    col_v1, col_v2, col_v3 = st.columns([2, 1.5, 1.5])

    with col_v1:
        n_history = st.slider(
            "📊 ¿Cuántos últimos partidos históricos analizar por equipo?",
            min_value=3, max_value=25, value=st.session_state.confirmed_matches_history, step=1
        )
    with col_v2:
        force_dl = st.checkbox("🔄 Forzar actualización completa (API)", value=False)
    with col_v3:
        st.write("")
        st.write("")
        btn_confirm = st.button("🚀 Confirmar e Iniciar Análisis", type="primary", use_container_width=True)

    col_cancel, _ = st.columns([1.5, 4])
    with col_cancel:
        if st.button("✖️ Cancelar y elegir otro partido", use_container_width=True):
            st.session_state.selected_match = None
            st.session_state.analysis_confirmed = False
            st.rerun()

    if btn_confirm:
        st.session_state.confirmed_matches_history = n_history
        st.session_state.force_redownload = force_dl
        st.session_state.analysis_confirmed = True
        st.rerun()


# ==============================================================================
# PASO 3: DESCARGA AUTOMATIZADA Y DASHBOARD ANALÍTICO
# ==============================================================================
if st.session_state.selected_match and st.session_state.analysis_confirmed:
    match = st.session_state.selected_match
    home_id = match['home_id']
    away_id = match['away_id']
    home_name = match['home_name']
    away_name = match['away_name']
    n_history = st.session_state.confirmed_matches_history
    force_dl = st.session_state.get("force_redownload", False)

    # Verificar existencia en Gold
    df_home_exist = load_gold_data(home_id)
    df_away_exist = load_gold_data(away_id)

    need_dl = force_dl or df_home_exist.empty or df_away_exist.empty

    if need_dl:
        prog_bar = st.progress(0, text="Iniciando descarga de estadísticas...")
        status_txt = st.empty()

        # 1. Descarga Local
        status_txt.text(f"Descargando últimos {n_history} partidos de {home_name}...")
        def h_cb(curr, tot, desc):
            prog_bar.progress(int((curr / (tot * 2)) * 100), text=f"[{home_name}] {desc}")
        process_team_matches(home_id, max_matches=n_history, progress_callback=h_cb)

        # 2. Descarga Visitante
        status_txt.text(f"Descargando últimos {n_history} partidos de {away_name}...")
        def a_cb(curr, tot, desc):
            prog_bar.progress(int(50 + (curr / (tot * 2)) * 100), text=f"[{away_name}] {desc}")
        process_team_matches(away_id, max_matches=n_history, progress_callback=a_cb)

        # 3. Postprocesamiento Gold
        status_txt.text("Calculando promedios móviles y variables predictivas Gold...")
        compute_rolling_averages()
        compute_dim_referee()
        generate_dim_date()

        prog_bar.progress(100, text="¡Datos descargados y procesados con éxito!")
        time.sleep(1)
        prog_bar.empty()
        status_txt.empty()

    # Cargar datos
    df_home = load_gold_data(home_id)
    df_away = load_gold_data(away_id)
    df_players = load_players_gold_data([home_id, away_id])

    if df_home.empty or df_away.empty:
        st.warning("No se encontraron suficientes partidos históricos en la API para uno de los equipos.")
        st.stop()

    # Cálculos estadísticos
    lambda_home, lambda_away = estimate_lambdas_from_history(df_home, df_away, home_id, away_id)
    model = compute_poisson_match_probabilities(lambda_home, lambda_away)
    stats_home = compute_empirical_team_stats(df_home, home_id)
    stats_away = compute_empirical_team_stats(df_away, away_id)

    st.markdown("---")
    st.markdown(f"## 📊 Informe Analítico: {home_name} vs {away_name}")
    st.markdown(f"<span style='color: #4B5563;'>Muestra analizada: <b>{len(df_home)}</b> partidos de {home_name} y <b>{len(df_away)}</b> partidos de {away_name}</span>", unsafe_allow_html=True)

    # TABS ANALÍTICOS
    tab1, tab2, tab3, tab4 = st.tabs([
        "🎲 Probabilidades Poisson (1X2 & Mercados)",
        "📊 Estadísticas Descriptivas & Comparativa",
        "🏃 Rendimiento Jugadores (Player Props)",
        "💾 Descarga Fácil (Excel / CSV)"
    ])

    # --------------------------------------------------------------------------
    # TAB 1: PROBABILIDADES MATEMÁTICAS PURAS
    # --------------------------------------------------------------------------
    with tab1:
        st.markdown("### 1. Probabilidades del Resultado Final (1X2) y Cuotas Justas")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown(f"""
            <div class='metric-card'>
                <div class='metric-title'>Victoria {home_name} (1)</div>
                <div class='metric-value'>{model['1x2']['home_win']['prob']}%</div>
                <div class='metric-odd'>Cuota Justa: <b>{model['1x2']['home_win']['fair_odd']}</b></div>
            </div>
            """, unsafe_allow_html=True)
        with col2:
            st.markdown(f"""
            <div class='metric-card'>
                <div class='metric-title'>Empate (X)</div>
                <div class='metric-value'>{model['1x2']['draw']['prob']}%</div>
                <div class='metric-odd'>Cuota Justa: <b>{model['1x2']['draw']['fair_odd']}</b></div>
            </div>
            """, unsafe_allow_html=True)
        with col3:
            st.markdown(f"""
            <div class='metric-card'>
                <div class='metric-title'>Victoria {away_name} (2)</div>
                <div class='metric-value'>{model['1x2']['away_win']['prob']}%</div>
                <div class='metric-odd'>Cuota Justa: <b>{model['1x2']['away_win']['fair_odd']}</b></div>
            </div>
            """, unsafe_allow_html=True)

        st.caption(f"**Parámetros estimados del modelo:** Goles esperados Local $\\lambda_{{home}} = {model['lambda_home']}$ | Goles esperados Visitante $\\lambda_{{away}} = {model['lambda_away']}$")
        st.markdown("---")

        st.markdown("### 2. Matriz Bivariada de Marcadores Exactos")
        c_mat, c_top = st.columns([1.5, 1])

        with c_mat:
            matrix_df = pd.DataFrame(
                np.round(model['matrix'][:6, :6] * 100, 1),
                index=[f"{i} gol{'es' if i!=1 else ''}" for i in range(6)],
                columns=[f"{j} gol{'es' if j!=1 else ''}" for j in range(6)]
            )
            fig_heatmap = px.imshow(
                matrix_df,
                text_auto=True,
                labels=dict(x=f"Goles {away_name}", y=f"Goles {home_name}", color="Probabilidad (%)"),
                color_continuous_scale="Blues",
                aspect="auto"
            )
            fig_heatmap.update_layout(
                title=f"Probabilidad de cada Marcador Exacto (%)",
                xaxis_title=f"{away_name} (Visitante)",
                yaxis_title=f"{home_name} (Local)",
                margin=dict(l=20, r=20, t=40, b=20),
                height=350
            )
            st.plotly_chart(fig_heatmap, use_container_width=True)

        with c_top:
            st.markdown("#### 🎯 Marcadores Más Probables")
            top_df = pd.DataFrame(model['top_scores'])
            top_df.columns = ["Marcador", "Probabilidad (%)", "Cuota Justa"]
            st.dataframe(top_df, use_container_width=True, hide_index=True)

            st.markdown("#### 🛡️ Doble Oportunidad")
            dc_data = [
                {"Opción": f"1X ({home_name} o Empate)", "Probabilidad (%)": f"{model['double_chance']['1X']['prob']}%", "Cuota Justa": model['double_chance']['1X']['fair_odd']},
                {"Opción": "12 (Cualquiera Gana)", "Probabilidad (%)": f"{model['double_chance']['12']['prob']}%", "Cuota Justa": model['double_chance']['12']['fair_odd']},
                {"Opción": f"X2 (Empate o {away_name})", "Probabilidad (%)": f"{model['double_chance']['X2']['prob']}%", "Cuota Justa": model['double_chance']['X2']['fair_odd']},
            ]
            st.dataframe(pd.DataFrame(dc_data), use_container_width=True, hide_index=True)

        st.markdown("---")

        st.markdown("### 3. Mercados de Goles (Over / Under) y Ambos Equipos Marcan (BTTS)")
        c_ou, c_btts = st.columns(2)

        with c_ou:
            st.markdown("#### Líneas de Goles Totales")
            ou_rows = []
            for line in [0.5, 1.5, 2.5, 3.5]:
                over = model['over_under'][f"Over {line}"]
                under = model['over_under'][f"Under {line}"]
                ou_rows.append({
                    "Línea": f"{line} Goles",
                    "Over Prob (%)": f"{over['prob']}%",
                    "Cuota Over": over['fair_odd'],
                    "Under Prob (%)": f"{under['prob']}%",
                    "Cuota Under": under['fair_odd'],
                })
            st.dataframe(pd.DataFrame(ou_rows), use_container_width=True, hide_index=True)

        with c_btts:
            st.markdown("#### Ambos Equipos Marcan (BTTS)")
            btts_rows = [
                {"Opción": "Sí (Ambos Anotan)", "Probabilidad": f"{model['btts']['yes']['prob']}%", "Cuota Justa": model['btts']['yes']['fair_odd']},
                {"Opción": "No (Al menos uno en 0)", "Probabilidad": f"{model['btts']['no']['prob']}%", "Cuota Justa": model['btts']['no']['fair_odd']},
            ]
            st.dataframe(pd.DataFrame(btts_rows), use_container_width=True, hide_index=True)

    # --------------------------------------------------------------------------
    # TAB 2: ESTADÍSTICAS DESCRIPTIVAS Y FRECUENCIAS
    # --------------------------------------------------------------------------
    with tab2:
        st.markdown("### Métricas Comparativas de Rendimiento Real (Datos Observados)")

        metrics_compare = pd.DataFrame({
            "Métrica": ["Goles Anotados", "Goles Concedidos", "Tiros al Arco", "Córners", "Faltas Cometidas"],
            f"{home_name} (Media)": [
                stats_home['metrics']['goals_for']['mean'],
                stats_home['metrics']['goals_against']['mean'],
                stats_home['metrics']['shots_on_target_for']['mean'],
                stats_home['metrics']['corners_for']['mean'],
                stats_home['metrics']['fouls_for']['mean'],
            ],
            f"{away_name} (Media)": [
                stats_away['metrics']['goals_for']['mean'],
                stats_away['metrics']['goals_against']['mean'],
                stats_away['metrics']['shots_on_target_for']['mean'],
                stats_away['metrics']['corners_for']['mean'],
                stats_away['metrics']['fouls_for']['mean'],
            ]
        })

        fig_bar = go.Figure()
        fig_bar.add_trace(go.Bar(
            name=home_name,
            x=metrics_compare["Métrica"],
            y=metrics_compare[f"{home_name} (Media)"],
            marker_color="#1E3A8A"
        ))
        fig_bar.add_trace(go.Bar(
            name=away_name,
            x=metrics_compare["Métrica"],
            y=metrics_compare[f"{away_name} (Media)"],
            marker_color="#EF4444"
        ))
        fig_bar.update_layout(barmode='group', height=360, margin=dict(l=20, r=20, t=30, b=20))
        st.plotly_chart(fig_bar, use_container_width=True)

        st.markdown("#### Frecuencias Observadas en la Muestra Reciente")
        c_f1, c_f2 = st.columns(2)
        with c_f1:
            st.markdown(f"**Historial {home_name}:**")
            st.write(f"- Partidos analizados: **{stats_home['sample_size']}**")
            st.write(f"- Victorias: **{stats_home['record']['wins']}** ({stats_home['rates']['win_pct']}%) | Empates: **{stats_home['record']['draws']}** | Derrotas: **{stats_home['record']['losses']}**")
            st.write(f"- Portería a cero (Clean Sheet): **{stats_home['rates']['clean_sheet_pct']}%**")
            st.write(f"- Partidos con Ambos Marcan (BTTS): **{stats_home['rates']['btts_pct']}%**")
            st.write(f"- Partidos con Más de 2.5 Goles: **{stats_home['rates']['over_2_5_pct']}%**")
        with c_f2:
            st.markdown(f"**Historial {away_name}:**")
            st.write(f"- Partidos analizados: **{stats_away['sample_size']}**")
            st.write(f"- Victorias: **{stats_away['record']['wins']}** ({stats_away['rates']['win_pct']}%) | Empates: **{stats_away['record']['draws']}** | Derrotas: **{stats_away['record']['losses']}**")
            st.write(f"- Portería a cero (Clean Sheet): **{stats_away['rates']['clean_sheet_pct']}%**")
            st.write(f"- Partidos con Ambos Marcan (BTTS): **{stats_away['rates']['btts_pct']}%**")
            st.write(f"- Partidos con Más de 2.5 Goles: **{stats_away['rates']['over_2_5_pct']}%**")

        st.markdown("---")
        st.markdown("#### Últimos Partidos Registrados")
        c_t1, c_t2 = st.columns(2)
        with c_t1:
            st.markdown(f"**Partidos de {home_name}:**")
            cols_show = ['match_id', 'opponent_name', 'is_home', 'goals_for', 'goals_against', 'shots_on_target_for', 'corners_for']
            avail_cols = [c for c in cols_show if c in df_home.columns]
            st.dataframe(df_home[avail_cols].head(8), use_container_width=True, hide_index=True)
        with c_t2:
            st.markdown(f"**Partidos de {away_name}:**")
            cols_show = ['match_id', 'opponent_name', 'is_home', 'goals_for', 'goals_against', 'shots_on_target_for', 'corners_for']
            avail_cols = [c for c in cols_show if c in df_away.columns]
            st.dataframe(df_away[avail_cols].head(8), use_container_width=True, hide_index=True)

    # --------------------------------------------------------------------------
    # TAB 3: RENDIMIENTO DE JUGADORES (PLAYER PROPS)
    # --------------------------------------------------------------------------
    with tab3:
        st.markdown("### Rendimiento Atómico de Jugadores (Player Props)")
        st.markdown("Estadísticas individuales para mercados de Tiros a Puerta, Goles, Faltas y Tarjetas.")

        if df_players.empty:
            st.info("No hay datos de alineaciones disponibles aún para estos partidos.")
        else:
            team_filter = st.selectbox("Filtrar por equipo:", ["Todos los equipos", home_name, away_name])
            filter_tid = None
            if team_filter == home_name:
                filter_tid = home_id
            elif team_filter == away_name:
                filter_tid = away_id

            players_summary = compute_player_props_summary(df_players, filter_tid)
            if not players_summary.empty:
                players_summary = players_summary.rename(columns={
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
                st.dataframe(players_summary.drop(columns=['player_id'], errors='ignore'), use_container_width=True, hide_index=True)
            else:
                st.info("No se encontraron registros de jugadores con los filtros seleccionados.")

    # --------------------------------------------------------------------------
    # TAB 4: DESCARGA FÁCIL DE DATOS
    # --------------------------------------------------------------------------
    with tab4:
        st.markdown("### 💾 Exportación Rápida de Datos")
        col_d1, col_d2, col_d3 = st.columns(3)

        combined_matches = pd.concat([df_home, df_away], ignore_index=True).drop_duplicates(subset=['match_id', 'team_id'])

        with col_d1:
            st.markdown("#### 1. Historial de Partidos (Gold)")
            csv_matches = combined_matches.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Descargar Partidos (CSV)",
                data=csv_matches,
                file_name=f"partidos_{home_name}_vs_{away_name}.csv",
                mime="text/csv",
                use_container_width=True
            )

            excel_buffer = io.BytesIO()
            with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                combined_matches.to_excel(writer, index=False, sheet_name='Partidos')
            st.download_button(
                label="📊 Descargar Partidos (Excel)",
                data=excel_buffer.getvalue(),
                file_name=f"partidos_{home_name}_vs_{away_name}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )

        with col_d2:
            st.markdown("#### 2. Estadísticas de Jugadores")
            if not df_players.empty:
                csv_players = df_players.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Descargar Jugadores (CSV)",
                    data=csv_players,
                    file_name=f"jugadores_{home_name}_vs_{away_name}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
            else:
                st.caption("No hay datos de jugadores para exportar.")

        with col_d3:
            st.markdown("#### 3. Reporte de Probabilidades")
            report_rows = [
                {"Mercado": f"Victoria {home_name} (1)", "Probabilidad": f"{model['1x2']['home_win']['prob']}%", "Cuota Justa": model['1x2']['home_win']['fair_odd']},
                {"Mercado": "Empate (X)", "Probabilidad": f"{model['1x2']['draw']['prob']}%", "Cuota Justa": model['1x2']['draw']['fair_odd']},
                {"Mercado": f"Victoria {away_name} (2)", "Probabilidad": f"{model['1x2']['away_win']['prob']}%", "Cuota Justa": model['1x2']['away_win']['fair_odd']},
                {"Mercado": "Ambos Marcan - Sí", "Probabilidad": f"{model['btts']['yes']['prob']}%", "Cuota Justa": model['btts']['yes']['fair_odd']},
                {"Mercado": "Ambos Marcan - No", "Probabilidad": f"{model['btts']['no']['prob']}%", "Cuota Justa": model['btts']['no']['fair_odd']},
                {"Mercado": "Más de 1.5 Goles", "Probabilidad": f"{model['over_under']['Over 1.5']['prob']}%", "Cuota Justa": model['over_under']['Over 1.5']['fair_odd']},
                {"Mercado": "Más de 2.5 Goles", "Probabilidad": f"{model['over_under']['Over 2.5']['prob']}%", "Cuota Justa": model['over_under']['Over 2.5']['fair_odd']},
                {"Mercado": "Menos de 2.5 Goles", "Probabilidad": f"{model['over_under']['Under 2.5']['prob']}%", "Cuota Justa": model['over_under']['Under 2.5']['fair_odd']},
            ]
            df_report = pd.DataFrame(report_rows)
            csv_report = df_report.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Descargar Probabilidades (CSV)",
                data=csv_report,
                file_name=f"probabilidades_{home_name}_vs_{away_name}.csv",
                mime="text/csv",
                use_container_width=True
            )
