import requests
import json
import os

def download_match_json(game_id: int):
    """
    Descarga los JSONs crudos de 365Scores para un partido específico 
    y los guarda en formato legible.
    """
    print(f"🔍 Iniciando extracción de prueba para el partido ID: {game_id}")
    
    # Asegurarnos de tener una carpeta para guardar esto
    os.makedirs("data_samples", exist_ok=True)

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }

    # ---------------------------------------------------------
    # 1. ENDPOINT PRINCIPAL (Info general, alineaciones, shotmap)
    # ---------------------------------------------------------
    url_game = "https://webws.365scores.com/web/game/"
    params_game = {
        'appTypeId': 5,
        'langId': 14,
        'timezoneName': 'America/Bogota',
        'gameId': game_id
    }

    try:
        response_game = requests.get(url_game, params=params_game, headers=headers)
        response_game.raise_for_status()
        game_data = response_game.json()
        
        # Guardar JSON con indentación para que sea human-readable
        with open(f"data_samples/match_{game_id}_general.json", "w", encoding="utf-8") as f:
            json.dump(game_data, f, indent=4, ensure_ascii=False)
        print(f"✅ General Data guardado: data_samples/match_{game_id}_general.json")
        
    except Exception as e:
        print(f"❌ Error descargando datos generales: {e}")

    # ---------------------------------------------------------
    # 2. ENDPOINT DE ESTADÍSTICAS (Las 118 variables)
    # ---------------------------------------------------------
    url_stats = "https://webws.365scores.com/web/game/stats/"
    params_stats = {
        'appTypeId': 5,
        'langId': 14,
        'timezoneName': 'America/Bogota',
        'games': game_id
        # Nota: Sin filterId nos trae todo, o puedes probar agregando 'filterId': 6 para el 1T
    }

    try:
        response_stats = requests.get(url_stats, params=params_stats, headers=headers)
        response_stats.raise_for_status()
        stats_data = response_stats.json()
        
        with open(f"data_samples/match_{game_id}_stats.json", "w", encoding="utf-8") as f:
            json.dump(stats_data, f, indent=4, ensure_ascii=False)
        print(f"✅ Stats Data guardado: data_samples/match_{game_id}_stats.json")
            
    except Exception as e:
        print(f"❌ Error descargando estadísticas: {e}")

# ==========================================
# EJECUCIÓN
# ==========================================
if __name__ == "__main__":
    # ⚠️ REEMPLAZA ESTE NÚMERO POR UN ID DE PARTIDO REAL QUE TENGAS EN TU BD
    # Por ejemplo, busca en tu SQLite actual un 'id' de la tabla 'matches'
    ID_DEL_PARTIDO_DE_PRUEBA = 4044230 
    
    download_match_json(ID_DEL_PARTIDO_DE_PRUEBA)
