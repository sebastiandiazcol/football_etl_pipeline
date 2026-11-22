# analysis/player_heatmap_props.py
import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
from mplsoccer import VerticalPitch

def plot_betting_heatmap(player_id, shot_line=2.5):
    con = sqlite3.connect("data/03_gold.db")
    
    # Consulta de tiros
    query = """
    SELECT position_x, position_y, outcome_name, xg, match_id
    FROM fact_shots
    WHERE player_id = ?
    """
    df_shots = pd.read_sql(query, con, params=(player_id,))
    con.close()

    if df_shots.empty:
        print(f"No hay datos para el ID {player_id}.")
        return

    # Cálculos rápidos de mercado por partido
    df_matches = df_shots.groupby('match_id').agg(
        total_shots=('outcome_name', 'count'),
        shots_on_target=('outcome_name', lambda x: x.isin(['Gol', 'Parada']).sum())
    ).reset_index()

    matches = len(df_matches)
    avg_shots = df_matches['total_shots'].mean()
    avg_sot = df_matches['shots_on_target'].mean()
    hit_rate_shots = (df_matches['total_shots'] > shot_line).mean() * 100
    hit_rate_sot = (df_matches['shots_on_target'] > shot_line).mean() * 100

    # Configuración del campo Opta Vertical
    pitch = VerticalPitch(
        pitch_type='opta', 
        line_color='#404040', 
        pitch_color='#0f0f0f', 
        half=True,
        line_zorder=2
    )
    fig, ax = pitch.draw(figsize=(10, 12))
    fig.patch.set_facecolor('#0f0f0f')

    # 1. Mapa de Calor (Orden Natural)
    pitch.kdeplot(
        x=df_shots['position_x'], 
        y=df_shots['position_y'], 
        ax=ax, levels=100, fill=True, zorder=1,
        thresh=0.2, cmap='magma', alpha=0.5
    )

    # 2. Scatter de tiros (Orden Natural)
    for _, shot in df_shots.iterrows():
        color = '#00ff00' if shot['outcome_name'] == 'Gol' else '#ff4d4d'
        pitch.scatter(
            x=shot['position_x'], 
            y=shot['position_y'], 
            s=shot['xg'] * 500 + 20, 
            edgecolors='white', c=color, alpha=0.7, ax=ax, zorder=3
        )

    # 3. Caja de Métricas de Mercado
    stats_text = (
        f"MERCADO: Over {shot_line} Tiros\n"
        f"----------------------------\n"
        f"Partidos: {matches}\n"
        f"Promedio Tiros: {avg_shots:.2f}\n"
        f"Hit Rate Tiros: {hit_rate_shots:.1f}%\n"
        f"----------------------------\n"
        f"Promedio a Puerta: {avg_sot:.2f}\n"
        f"Hit Rate a Puerta: {hit_rate_sot:.1f}%"
    )
    
    plt.text(
        2, 55, stats_text, 
        color='white', fontsize=12, 
        bbox=dict(facecolor='#1a1a1a', edgecolor='#404040', boxstyle='round,pad=1'),
        zorder=4
    )

    plt.title(f"Análisis de Finalización | Player: {player_id}", color='white', fontsize=18, fontweight='bold', pad=20)
    plt.show()

if __name__ == "__main__":
    p_id = input("Ingresa el ID del jugador: ")
    linea = float(input("Ingresa la línea de apuestas (ej. 2.5): "))
    if p_id.isdigit():
        plot_betting_heatmap(int(p_id), linea)