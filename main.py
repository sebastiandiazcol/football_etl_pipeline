# main.py
import argparse
import logging
import json
import requests
from datetime import datetime

from db.database import init_db, SessionBronze, SessionSilver, SessionGold
from db.models.bronze_models import RawMatchData

from transform.bronze_to_silver import BronzeToSilverETL
from transform.silver_to_gold import SilverToGoldETL, compute_rolling_averages, compute_dim_referee, generate_dim_date

from utils.logger import setup_logger

logger = setup_logger("MainPipeline")

def fetch_and_save_bronze(match_id: int, db_bronze) -> tuple:
    """Extrae datos de la API (incluyendo los 3 periodos) y los guarda en Bronze."""
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    url_general = f"https://webws.365scores.com/web/game/?appTypeId=5&langId=14&timezoneName=America/Bogota&gameId={match_id}"
    
    try:
        logger.info(f"[{match_id}] Descargando datos crudos de la API...")
        res_general = requests.get(url_general, headers=headers, timeout=15)
        res_general.raise_for_status()
        general_json_dict = res_general.json()
        
        # Lógica para extraer los 3 periodos
        period_filters = {
            "Partido_Completo": None,
            "Primer_Tiempo": 6,
            "Segundo_Tiempo": 8
        }
        stats_json_dict = {}
        
        for period_name, filter_id in period_filters.items():
            url_stats = f"https://webws.365scores.com/web/game/stats/?appTypeId=5&langId=14&timezoneName=America/Bogota&games={match_id}"
            if filter_id:
                url_stats += f"&filterId={filter_id}"
                
            res_stats = requests.get(url_stats, headers=headers, timeout=15)
            if res_stats.status_code == 200:
                stats_json_dict[period_name] = res_stats.json()
            else:
                stats_json_dict[period_name] = {}

        # Guardar en Bronze
        existing_raw = db_bronze.query(RawMatchData).filter_by(match_id=str(match_id)).first()
        if existing_raw:
            db_bronze.delete(existing_raw)
            db_bronze.flush()

        raw_data_general = RawMatchData(
            match_id=str(match_id),
            endpoint_source="general_and_stats_all_periods",
            raw_json=json.dumps({
                "general": general_json_dict,
                "stats": stats_json_dict
            })
        )
        db_bronze.add(raw_data_general)
        db_bronze.commit()
        logger.info(f"[{match_id}] Guardado en BRONZE exitoso.")
        
        return json.dumps(general_json_dict), json.dumps(stats_json_dict)

    except Exception as e:
        logger.error(f"[{match_id}] Error en la extraccion a Bronze: {e}")
        db_bronze.rollback()
        return None, None

def run_full_pipeline(match_id: int):
    """Orquestador principal del ETL para un partido especifico."""
    logger.info(f"{'='*50}")
    logger.info(f"INICIANDO PIPELINE MEDALLION PARA MATCH ID: {match_id}")
    logger.info(f"{'='*50}")

    db_bronze = SessionBronze()
    db_silver = SessionSilver()
    db_gold = SessionGold()

    try:
        general_json, stats_json = fetch_and_save_bronze(match_id, db_bronze)
        
        if not general_json:
            logger.error("Abortando pipeline por fallo en extraccion.")
            return

        silver_etl = BronzeToSilverETL(db_silver)
        silver_etl.process_match(general_json, stats_json)
        
        gold_etl = SilverToGoldETL(db_silver, db_gold)
        gold_etl.process_match_to_gold(match_id)
        
        logger.info(f"PIPELINE COMPLETADO CON EXITO PARA MATCH {match_id}")

    finally:
        db_bronze.close()
        db_silver.close()
        db_gold.close()

def process_team_matches(team_id: int, max_matches: int = 10):
    """Busca los ultimos N partidos finalizados de un equipo y los procesa en el pipeline."""
    logger.info(f"Buscando los ultimos {max_matches} partidos del equipo {team_id}...")
    url = "https://webws.365scores.com/web/games/results/"
    params = {
        'appTypeId': 5,
        'langId': 14,
        'timezoneName': 'America/Bogota',
        'competitors': team_id,
        'showOdds': 'true'
    }
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    
    try:
        response = requests.get(url, params=params, headers=headers, timeout=15)
        response.raise_for_status()
        data = response.json()
        games = data.get('games', [])
        
        if not games:
            logger.warning(f"No se encontraron partidos para el equipo {team_id}")
            return
            
        finished_games = [g for g in games if g.get('statusGroup') == 4]
        logger.info(f"Se encontraron {len(finished_games)} partidos finalizados en el historial reciente.")
        
        games_to_process = finished_games[:max_matches]
        
        for i, game in enumerate(games_to_process, 1):
            match_id = game.get('id')
            home = game.get('homeCompetitor', {}).get('name', 'Local')
            away = game.get('awayCompetitor', {}).get('name', 'Visitante')
            
            logger.info(f"\n[{i}/{len(games_to_process)}] Iniciando pipeline para: {home} vs {away} (ID: {match_id})")
            run_full_pipeline(match_id)
            
        logger.info(f"\nPROCESAMIENTO MASIVO COMPLETADO PARA EL EQUIPO {team_id}.")
        
    except Exception as e:
        logger.error(f"Error buscando partidos del equipo {team_id}: {e}")
        import traceback
        logger.error(traceback.format_exc())

def main():
    parser = argparse.ArgumentParser(description="Football Data Medallion ETL Pipeline")
    
    parser.add_argument(
        '--mode', 
        choices=['process_match', 'process_team'], 
        required=True, 
        help="Modo de ejecucion."
    )
    parser.add_argument('--match', type=int, help="ID del partido especifico a procesar (para process_match)")
    parser.add_argument('--team', type=int, help="ID del equipo a procesar (para process_team)")
    parser.add_argument('--matches', type=int, default=10, help="Numero de partidos a extraer (por defecto 10)")
    
    args = parser.parse_args()

    init_db()

    if args.mode == 'process_match':
        if not args.match:
            logger.error("[ERROR] Debes proporcionar el ID del partido con --match")
            return
        run_full_pipeline(args.match)
        
    elif args.mode == 'process_team':
        if not args.team:
            logger.error("[ERROR] Debes proporcionar el ID del equipo con --team")
            return
        process_team_matches(args.team, args.matches)
        
        # Post-procesamiento Gold
        logger.info("Ejecutando post-procesamiento Gold...")
        compute_rolling_averages()
        compute_dim_referee()
        generate_dim_date()
        logger.info("Post-procesamiento completado.")

if __name__ == "__main__":
    main()