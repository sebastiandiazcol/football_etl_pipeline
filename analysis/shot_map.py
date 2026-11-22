# analysis/shot_map.py
import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
from mplsoccer import VerticalPitch
import mplcursors

def plot_real_madrid_shots_interactive():
    # 1. Conectar a GOLD
    db_path = "data/03_gold.db"
    con = sqlite3.connect(db_path)
    
    # 2. SQL Avanzado: Obtenemos el tiro y calculamos quién era el rival en ese partido
    query = """
    SELECT 
        s.match_id,
        p.player_name,
        s.shot_minute,
        s.xg,
        s.outcome_name,
        s.position_x,
        s.position_y,
        CASE 
            WHEN fm.home_team_id = 131 THEN t_away.team_name 
            ELSE t_home.team_name 
        END as opponent_name
    FROM fact_shots s
    JOIN dim_players p ON s.player_id = p.player_id
    JOIN fact_matches fm ON s.match_id = fm.match_id
    JOIN dim_teams t_home ON fm.home_team_id = t_home.team_id
    JOIN dim_teams t_away ON fm.away_team_id = t_away.team_id
    WHERE s.team_id = 131
    """
    
    df_shots = pd.read_sql(query, con)
    con.close()
    
    if df_shots.empty:
        print("No se encontraron tiros para el equipo.")
        return

    # 3. Limpieza y separacion segura
    df_shots['xg'] = df_shots['xg'].fillna(0.05)
    
    # reset_index(drop=True) es VITAL para que el cursor interactivo encuentre la fila correcta
    df_goals = df_shots[df_shots['outcome_name'] == 'Gol'].reset_index(drop=True)
    df_non_goals = df_shots[df_shots['outcome_name'] != 'Gol'].reset_index(drop=True)

    # 4. Dibujar Cancha
    pitch = VerticalPitch(
        pitch_type='opta', 
        half=True, 
        pitch_color='#1e1e1e', 
        line_color='#ffffff', 
        line_zorder=2
    )
    
    fig, ax = pitch.draw(figsize=(10, 8))
    fig.patch.set_facecolor('#1e1e1e')

    # 5. Graficar guardando las referencias en variables (sc_non_goals y sc_goals)
    sc_non_goals = pitch.scatter(
        df_non_goals['position_y'], 
        df_non_goals['position_x'], 
        s=df_non_goals['xg'] * 1000, 
        c='#ea4335', 
        alpha=0.6, 
        ax=ax,
        label='Tiro (No Gol)',
        zorder=3
    )

    sc_goals = pitch.scatter(
        df_goals['position_y'], 
        df_goals['position_x'], 
        s=df_goals['xg'] * 1000, 
        c='#34a853', 
        alpha=0.9, 
        edgecolors='#ffffff',
        linewidth=2.5,
        ax=ax,
        label='Gol',
        zorder=4
    )

    plt.title("Mapa de Tiros Interactivo - Real Madrid\n(Pasa el mouse sobre los puntos)", color='white', fontsize=16, fontweight='bold', pad=20)
    ax.legend(loc='lower left', facecolor='#1e1e1e', edgecolor='none', labelcolor='white', fontsize=10)
    
    # 6. Lógica de Interactividad (Hover)
    cursor = mplcursors.cursor([sc_non_goals, sc_goals], hover=True)
    
    @cursor.connect("add")
    def on_add(sel):
        # Identificar a qué grupo pertenece el punto que el usuario está tocando
        if sel.artist == sc_goals:
            row = df_goals.iloc[sel.index]
        else:
            row = df_non_goals.iloc[sel.index]
            
        # Construir el texto emergente
        tooltip_text = (
            f"Jugador: {row['player_name']}\n"
            f"Minuto: {int(row['shot_minute'])}'\n"
            f"Rival: {row['opponent_name']}\n"
            f"Resultado: {row['outcome_name']}\n"
            f"xG (Probabilidad): {row['xg']:.2f}"
        )
        
        sel.annotation.set_text(tooltip_text)
        
        # Diseño de la caja emergente (Tooltip)
        sel.annotation.get_bbox_patch().set(facecolor='#2d2d2d', alpha=0.9, edgecolor='#ffffff', boxstyle='round,pad=0.5')
        sel.annotation.set_color('white')
        sel.annotation.set_fontsize(10)

    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
    plot_real_madrid_shots_interactive()