# app.py
"""
Football Analytics & Pure Probability Engine
Web App interactiva para:
1. Búsqueda y descarga fácil de estadísticas de fútbol (API 365scores).
2. Procesamiento Medallion automatizado (Bronze -> Silver -> Gold).
3. Motor de Probabilidades Estadísticas Puras (Distribución de Poisson, 1X2, Over/Under, BTTS).
4. Análisis descriptivo de rendimiento y Player Props (tiros a puerta, faltas, tarjetas).
5. Exportación instantánea en Excel y CSV sin requerir bases de datos externas.
"""

import os
import io
import time
import requests
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

# Estilos CSS personalizados
st.markdown("""
<style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 700;
        color: #1E3A8A;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        font-size: 1.05rem;
        color: #4B5563;
        margin-bottom: 1.5rem;
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
        font-size: 0.9rem;
        color: #64748B;
        font-weight: 600;
        text-transform: uppercase;
    }
    .metric-value {
        font-size: 1.8rem;
        font-weight: 700;
        color: #0F172A;
    }
    .metric-odd {
        font-size: 0.95rem;
        color: #2563EB;
        font-weight: 600;
        margin-top: 4px;
    }
    .badge-win { background-color: #DCFCE7; color: #166534; padding: 3px 8px; border-radius: 6px; font-weight: 600; }
    .badge-draw { background-color: #FEF9C3; color: #854D0E; padding: 3px 8px; border-radius: 6px; font-weight: 600; }
    .badge-loss { background-color: #FEE2E2; color: #991B1B; padding: 3px 8px; border-radius: 6px; font-weight: 600; }
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


# ==============================================================================
# FUNCIONES DE ASISTENCIA Y API
# ==============================================================================
@st.cache_data(ttl=3600)
def search_teams_api(query: str):
    """Busca equipos en la API de 365scores."""
    if not query or len(query.strip()) < 2:
        return []
    
    url = "https://webws.365scores.com/web/search/"
    params = {
        'appTypeId': 5,
        'langId': 14,
        'timezoneName': 'America/Bogota',
        'q': query.strip()
    }
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
        st.error(f"Error consultando API de búsqueda: {e}")
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
    except Exception as e:
        return pd.DataFrame()


def load_players_gold_data(team_ids: list):
    """Carga las estadísticas de jugadores de los equipos indicados."""
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
    except Exception as e:
        return pd.DataFrame()


# ==============================================================================
# BARRA LATERAL (CONTROLES Y BÚSQUEDA)
# ==============================================================================
st.sidebar.markdown("## ⚽ Selección de Partido")
st.sidebar.markdown("Busca los dos equipos para descargar sus estadísticas y proyectar las probabilidades.")

# 1. Buscador Equipo Local
home_query = st.sidebar.text_input("🏠 Equipo Local:", value="Real Madrid")
home_results = search_teams_api(home_query)

home_selected = None
if home_results:
    home_options = {item['display']: item for item in home_results}
    selected_label = st.sidebar.selectbox("Selecciona Equipo Local confirmado:", list(home_options.keys()), key="home_select")
    home_selected = home_options[selected_label]
else:
    # Soporte para ingreso de ID numérico directo
    if home_query.isdigit():
        home_selected = {'id': int(home_query), 'name': f"Equipo {home_query}", 'display': f"ID {home_query}"}
    else:
        st.sidebar.caption("Escribe el nombre del equipo y presiona Enter.")

# 2. Buscador Equipo Visitante
away_query = st.sidebar.text_input("✈️ Equipo Visitante:", value="Barcelona")
away_results = search_teams_api(away_query)

away_selected = None
if away_results:
    away_options = {item['display']: item for item in away_results}
    selected_label = st.sidebar.selectbox("Selecciona Equipo Visitante confirmado:", list(away_options.keys()), key="away_select")
    away_selected = away_options[selected_label]
else:
    if away_query.isdigit():
        away_selected = {'id': int(away_query), 'name': f"Equipo {away_query}", 'display': f"ID {away_query}"}
    else:
        st.sidebar.caption("Escribe el nombre del equipo y presiona Enter.")

# Configuración de Partidos
st.sidebar.markdown("---")
n_matches = st.sidebar.slider("📊 Historial a descargar (partidos por equipo):", min_value=3, max_value=25, value=10, step=1)
force_redownload = st.sidebar.checkbox("Forzar nueva descarga (actualizar API)", value=False)

# Botón de Descarga
start_pipeline_btn = st.sidebar.button("🚀 Descargar y Analizar Partidos", use_container_width=True, type="primary")

st.sidebar.markdown("---")
st.sidebar.info("""
**Metodología Matemática:**
- **Modelo Poisson:** Calcula la probabilidad de cada marcador $(x, y)$ a partir del promedio ponderado de ataque y defensa.
- **Cuota Justa:** $1 / P$. Representa la probabilidad matemática pura sin comisión de casas de apuestas.
""")


# ==============================================================================
# LÓGICA DE EXTRACCIÓN Y PIPELINE
# ==============================================================================
if home_selected and away_selected:
    home_id = home_selected['id']
    away_id = away_selected['id']
    home_name = home_selected['name']
    away_name = away_selected['name']

    # Verificar si ya existen partidos en Gold
    df_home_exist = load_gold_data(home_id)
    df_away_exist = load_gold_data(away_id)

    need_download = force_redownload or df_home_exist.empty or df_away_exist.empty

    if start_pipeline_btn or (need_download and not force_redownload and df_home_exist.empty):
        progress_bar = st.progress(0, text="Iniciando descarga de estadísticas...")
        status_text = st.empty()

        # 1. Descarga Local
        status_text.text(f"Descargando últimos {n_matches} partidos de {home_name}...")
        def home_cb(curr, tot, desc):
            progress_bar.progress(int((curr / (tot * 2)) * 100), text=f"[{home_name}] {desc}")
        process_team_matches(home_id, max_matches=n_matches, progress_callback=home_cb)

        # 2. Descarga Visitante
        status_text.text(f"Descargando últimos {n_matches} partidos de {away_name}...")
        def away_cb(curr, tot, desc):
            progress_bar.progress(int(50 + (curr / (tot * 2)) * 100), text=f"[{away_name}] {desc}")
        process_team_matches(away_id, max_matches=n_matches, progress_callback=away_cb)

        # 3. Postprocesamiento Gold
        status_text.text("Calculando promedios móviles y variables Gold...")
        compute_rolling_averages()
        compute_dim_referee()
        generate_dim_date()

        progress_bar.progress(100, text="¡Procesamiento finalizado exitosamente!")
        time.sleep(1)
        progress_bar.empty()
        status_text.empty()
        st.success(f"Estadísticas actualizadas para **{home_name}** y **{away_name}**.")

    # Cargar datos procesados
    df_home = load_gold_data(home_id)
    df_away = load_gold_data(away_id)
    df_players = load_players_gold_data([home_id, away_id])

    # ==============================================================================
    # HEADER PRINCIPAL
    # ==============================================================================
    st.markdown(f"<div class='main-header'>⚽ {home_name} vs {away_name}</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='sub-header'>Análisis Estadístico Puro y Proyección de Probabilidades | Muestra: {len(df_home)} partidos ({home_name}) y {len(df_away)} partidos ({away_name})</div>", unsafe_allow_html=True)

    if df_home.empty or df_away.empty:
        st.warning("No hay suficientes partidos descargados aún. Haz clic en **'Descargar y Analizar Partidos'** en la barra lateral.")
        st.stop()

    # Cálculo del modelo estadístico
    lambda_home, lambda_away = estimate_lambdas_from_history(df_home, df_away, home_id, away_id)
    model = compute_poisson_match_probabilities(lambda_home, lambda_away)
    stats_home = compute_empirical_team_stats(df_home, home_id)
    stats_away = compute_empirical_team_stats(df_away, away_id)

    # TABS PRINCIPALES
    tab1, tab2, tab3, tab4 = st.tabs([
        "🎲 Probabilidades Matemáticas (Poisson)",
        "📊 Estadísticas Descriptivas & Frecuencias",
        "🏃 Rendimiento Jugadores (Player Props)",
        "💾 Descarga Fácil de Datos (Excel / CSV)"
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

        # Matriz de Marcadores Exactos y Marcadores más probables
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

        # Mercados de Goles y Ambos Marcan
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

            st.caption("""
            *Nota Estadística:* Las cuotas justas se calculan como $1 / P$. Si encuentras una cuota en el mercado superior a la cuota justa calculada, el evento tiene **Valor Esperado Positivo (+EV)**.
            """)

    # --------------------------------------------------------------------------
    # TAB 2: ESTADÍSTICAS DESCRIPTIVAS Y FRECUENCIAS
    # --------------------------------------------------------------------------
    with tab2:
        st.markdown("### Métricas Comparativas de Rendimiento Real (Datos Observados)")
        
        # Comparativa gráfica de métricas clave
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

        # Tablas de frecuencia observada
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
                # Renombrar columnas para lectura amigable
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
        st.markdown("Descarga los datos limpios y el modelo de probabilidades sin complicaciones.")

        col_d1, col_d2, col_d3 = st.columns(3)

        # 1. Exportar Partidos Gold (Excel y CSV)
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

            # Botón Excel
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

        # 2. Exportar Jugadores
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

        # 3. Exportar Reporte de Probabilidades
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

        st.markdown("---")
        st.markdown("""
        #### 💡 ¿Cómo usar estos datos descargados?
        1. **Excel / Google Sheets:** Abre cualquiera de los archivos CSV o Excel directamente para crear tablas dinámicas, correlaciones o filtros propios.
        2. **Power BI Desktop:** Puedes cargar directamente el archivo Excel o conectarte a la base de datos SQLite `data/03_gold.db` usando el conector ODBC sin necesidad de Docker ni SQL Server.
        """)

else:
    st.info("👈 Por favor selecciona los dos equipos en la barra lateral para comenzar.")
