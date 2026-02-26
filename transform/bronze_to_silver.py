# transform/bronze_to_silver.py
import json
import logging
from datetime import datetime
from typing import Dict, List, Any

# Asumiendo que ya tienes tus modelos configurados como lo vimos
from db.database import SessionSilver
from db.models.silver_models import MatchSilver, MatchStatSilver, MatchEventSilver, MatchLineupSilver, MatchShotSilver

logger = logging.getLogger("BronzeToSilver")
#logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class BronzeToSilverETL:
    """
    Motor de transformación Medallion: De JSON Crudo (Bronze) a Modelo Relacional Limpio (Silver).
    """
    def __init__(self, db_session):
        self.db = db_session

    def _build_player_lookup(self, members_data: List[Dict]) -> Dict[int, Dict]:
        """
        Crea un diccionario en memoria para búsquedas O(1) de nombres de jugadores.
        Cruza el 'id' del jugador con su nombre y dorsal.
        """
        lookup = {}
        for member in members_data:
            player_id = member.get('id')
            if player_id:
                lookup[player_id] = {
                    'name': member.get('name', 'Desconocido'),
                    'short_name': member.get('shortName', ''),
                    'jersey_number': member.get('jerseyNumber')
                }
        return lookup

    def _parse_match_metadata(self, general_data: Dict) -> dict:
        """
        Extrae la metadata principal del partido (SilverMatches).
        """
        game = general_data.get('game', {})
        
        home_comp = game.get('homeCompetitor', {})
        away_comp = game.get('awayCompetitor', {})
        venue = game.get('venue', {})
        officials = game.get('officials', [])
        
        # Extracción segura de fecha
        start_time_str = game.get('startTime')
        match_date = None
        if start_time_str:
            try:
                # 365Scores usa formato ISO con timezone (ej. 2024-10-27T07:30:00-05:00)
                match_date = datetime.strptime(start_time_str[:19], "%Y-%m-%dT%H:%M:%S")
            except Exception as e:
                logger.warning(f"Error parseando fecha {start_time_str}: {e}")
                match_date = datetime.utcnow()

        # Extraer árbitro principal si existe
        referee = None
        if officials:
            referee = officials[0].get('name')

        return {
            "match_id": game.get('id'),
            "url": f"https://www.365scores.com/es/football/game/{game.get('id')}",
            "match_date": match_date,
            "competition_id": game.get('competitionId'),
            "competition_name": game.get('competitionDisplayName'),
            "season_num": game.get('seasonNum'),
            "round_num": game.get('roundNum'),
            "round_name": game.get('roundName'),
            
            "home_team_id": home_comp.get('id'),
            "home_team_name": home_comp.get('name'),
            "away_team_id": away_comp.get('id'),
            "away_team_name": away_comp.get('name'),
            
            "home_score": float(home_comp.get('score', 0)),
            "away_score": float(away_comp.get('score', 0)),
            "status_text": game.get('statusText'),
            
            "venue_name": venue.get('name'),
            "referee_name": referee
        }

    def _parse_lineups(self, match_id: int, team_comp: Dict, player_lookup: Dict) -> List[dict]:
        """
        Extrae las alineaciones, suplentes y la posición X/Y exacta en el campo.
        """
        lineups_list = []
        team_id = team_comp.get('id')
        members = team_comp.get('lineups', {}).get('members', [])
        
        for player in members:
            player_id = player.get('id')
            if not player_id:
                continue
                
            # Cruzar con el diccionario de jugadores para obtener el nombre real
            player_info = player_lookup.get(player_id, {})
            
            # Extraer coordenadas en el campo (yardFormation)
            yard = player.get('yardFormation', {})
            
            lineup_entry = {
                "match_id": match_id,
                "team_id": team_id,
                "player_id": player_id,
                "player_name": player_info.get('name', 'Unknown'),
                "jersey_number": player_info.get('jersey_number'),
                "status_text": player.get('statusText'), # "Starting", "Substitute", etc.
                "formation_line": yard.get('line'),      # 1=Portero, 2=Defensa, 3=Medio, 4=Delantero
                "field_line": yard.get('fieldLine'),     # Eje Y (0-100)
                "field_side": yard.get('fieldSide')      # Eje X (0-100)
            }
            lineups_list.append(lineup_entry)
            
        return lineups_list

    def _parse_events(self, match_id: int, events_data: List[Dict], player_lookup: Dict) -> List[dict]:
        """
        Extrae los eventos cronológicos: Goles, Tarjetas, Sustituciones, VAR.
        """
        events_list = []
        
        for event in events_data:
            event_type = event.get('eventType', {})
            player_id = event.get('playerId')
            
            # Obtener nombre del jugador principal
            player_name = player_lookup.get(player_id, {}).get('name', 'Unknown') if player_id else None
            
            # Buscar jugador secundario (ej. el que da la asistencia o el que sale de cambio)
            secondary_player_id = None
            secondary_player_name = None
            extra_players = event.get('extraPlayers', [])
            if extra_players:
                secondary_player_id = extra_players[0]
                secondary_player_name = player_lookup.get(secondary_player_id, {}).get('name', 'Unknown')

            # Extraer y limpiar el minuto del evento
            game_minute = None
            game_time_raw = event.get('gameTime')
            if game_time_raw is not None:
                try:
                    game_minute = float(game_time_raw)
                except ValueError:
                    logger.warning(f"No se pudo convertir gameTime: {game_time_raw}")

            event_entry = {
                "match_id": match_id,
                "team_id": event.get('competitorId'),
                "event_order": event.get('order'),
                "game_minute": game_minute,
                
                "event_type_id": event_type.get('id'),         # 1=Gol, 2=Amarilla, 1000=Cambio
                "event_type_name": event_type.get('name'),     # "Gol", "Tarjeta amarilla", "VAR"
                "event_sub_type": event_type.get('subTypeName'), # "Gol de campo", "Penalti"
                
                "primary_player_id": player_id,
                "primary_player_name": player_name,
                
                "secondary_player_id": secondary_player_id,
                "secondary_player_name": secondary_player_name,
                
                "is_major": event.get('isMajor', False)
            }
            events_list.append(event_entry)
            
        return events_list

    def _parse_shotmap(self, match_id: int, chart_events: List[Dict], home_team_id: int, away_team_id: int, player_lookup: Dict) -> List[dict]:
        """
        Extrae el mapa de tiros avanzado: Coordenadas, xG (Expected Goals), xGOT, Parte del cuerpo.
        Esta información es ORO puro para Power BI y análisis espacial en Python.
        """
        shotmap_list = []
        
        # Mapeo vital: 'competitorNum' 1 es Local, 2 es Visitante
        comp_map = {
            1: home_team_id,
            2: away_team_id
        }
        
        for idx, shot in enumerate(chart_events, start=1):
            comp_num = shot.get('competitorNum')
            team_id = comp_map.get(comp_num)
            
            player_id = shot.get('playerId')
            player_name = player_lookup.get(player_id, {}).get('name', 'Unknown') if player_id else 'Unknown'
            
            # Casteo seguro de xG (Expected Goals)
            xg_val = 0.0
            raw_xg = shot.get('xg')
            if raw_xg:
                try:
                    xg_val = float(str(raw_xg).replace('-', '0'))
                except ValueError:
                    pass
                    
            # Casteo seguro de xGOT (Expected Goals on Target)
            xgot_val = 0.0
            raw_xgot = shot.get('xgot')
            if raw_xgot:
                try:
                    xgot_val = float(str(raw_xgot).replace('-', '0'))
                except ValueError:
                    pass

            # Limpiar el tiempo (viene como "3'" a veces)
            shot_time = str(shot.get('time', '0')).replace("'", "")
            try:
                minute = float(shot_time)
            except ValueError:
                minute = 0.0

            shot_entry = {
                "match_id": match_id,
                "team_id": team_id,
                "player_id": player_id,
                "player_name": player_name,
                "shot_minute": minute,
                
                # Métricas Avanzadas
                "xg": xg_val,
                "xgot": xgot_val,
                
                # Contexto del Tiro
                "body_part": shot.get('bodyPart'),             # "Pie izquierdo", "Cabeza"
                "goal_description": shot.get('goalDescription'),# "Abajo al medio"
                "outcome_name": shot.get('outcome', {}).get('name', 'Unknown'), # "Bloqueado", "Gol", "Atajado"
                
                # Coordenadas X/Y
                "position_x": shot.get('line'), # Línea de profundidad
                "position_y": shot.get('side')  # Línea lateral
            }
            shotmap_list.append(shot_entry)
            
        return shotmap_list

    def _parse_statistics(self, match_id: int, stats_data: Dict, period_name: str, home_team_id: int) -> List[dict]:
        """
        Extrae las 118 métricas posibles y aplica Type Casting robusto.
        Limpia símbolos de porcentaje y formatos complejos como "36/46 (78%)".
        """
        stats_list = []
        statistics = stats_data.get('statistics', [])
        
        for stat in statistics:
            team_id = stat.get('competitorId')
            team_type = 'Local' if team_id == home_team_id else 'Visitante'
            
            # El valor crudo exacto de la API (ej. "80%", "5", "36/46 (78%)")
            raw_value = str(stat.get('value', '0')).strip()
            
            # Algoritmo de limpieza numérica
            numeric_value = 0.0
            try:
                if "%" in raw_value and "(" in raw_value:
                    # Caso: "36/46 (78%)" -> Extraemos el 78
                    val_split = raw_value.split('(')[1].replace('%', '').replace(')', '')
                    numeric_value = float(val_split)
                elif "%" in raw_value:
                    # Caso: "80%" -> Extraemos 80
                    numeric_value = float(raw_value.replace('%', ''))
                else:
                    # Caso normal: "5" o "1.5"
                    numeric_value = float(raw_value)
            except ValueError:
                # Si es un texto irrecuperable, lo dejamos en 0.0 en la columna numérica
                logger.debug(f"No se pudo castear el valor: {raw_value} para la métrica {stat.get('name')}")
                numeric_value = 0.0

            stat_entry = {
                "match_id": match_id,
                "team_id": team_id,
                "team_type": team_type,
                "period": period_name,
                
                "stat_id": stat.get('id'),
                "stat_name": stat.get('name'),
                "category_name": stat.get('categoryName', 'General'),
                
                "value_string": raw_value,       # Para mostrar en tooltips de Power BI
                "value_numeric": numeric_value   # Para sumar/promediar en DAX
            }
            stats_list.append(stat_entry)
            
        return stats_list

    def process_match(self, general_json: str, stats_json: str):
        """
        MÉTODO ORQUESTADOR COMPLETO.
        """
        general_data = json.loads(general_json)
        # Ahora stats_data es un diccionario con los 3 periodos
        stats_data = json.loads(stats_json) if stats_json else {}
        
        game_data = general_data.get('game', {})
        if not game_data:
            logger.error("No se encontró el nodo 'game' en el JSON general.")
            return

        try:
            # --- CORRECCIÓN 1: Extraer members de game_data ---
            members_list = game_data.get('members', [])
            player_lookup = self._build_player_lookup(members_list)
            
            match_meta_dict = self._parse_match_metadata(general_data)
            match_id = match_meta_dict['match_id']
            home_team_id = match_meta_dict['home_team_id']
            away_team_id = match_meta_dict['away_team_id']
            
            logger.info(f"[{match_id}] Procesando: {match_meta_dict['home_team_name']} vs {match_meta_dict['away_team_name']}")

            # 3. Alineaciones 
            home_lineup = self._parse_lineups(match_id, game_data.get('homeCompetitor', {}), player_lookup)
            away_lineup = self._parse_lineups(match_id, game_data.get('awayCompetitor', {}), player_lookup)
            all_lineups = home_lineup + away_lineup
            
            # 4. Eventos Cronológicos
            events_data = game_data.get('events', [])
            all_events = self._parse_events(match_id, events_data, player_lookup)
            
            # 5. Shotmap
            chart_events = game_data.get('chartEvents', {}).get('events', [])
            all_shots = self._parse_shotmap(match_id, chart_events, home_team_id, away_team_id, player_lookup)
            
            # --- CORRECCIÓN 2: Iterar sobre los 3 periodos ---
            all_stats = []
            for period_name, period_stats in stats_data.items():
                if period_stats:
                    parsed_stats = self._parse_statistics(match_id, period_stats, period_name, home_team_id)
                    all_stats.extend(parsed_stats)

            # ==========================================
            # 7. PERSISTENCIA EN BASE DE DATOS SILVER
            # ==========================================
            from db.models.silver_models import MatchSilver, MatchStatSilver, MatchEventSilver, MatchLineupSilver, MatchShotSilver
            
            existing_match = self.db.query(MatchSilver).filter_by(match_id=match_id).first()
            if existing_match:
                self.db.delete(existing_match)
                self.db.flush() 
            
            new_match = MatchSilver(**match_meta_dict)
            self.db.add(new_match)
            
            if all_lineups:
                self.db.bulk_insert_mappings(MatchLineupSilver, all_lineups)
            if all_events:
                self.db.bulk_insert_mappings(MatchEventSilver, all_events)
            if all_shots:
                self.db.bulk_insert_mappings(MatchShotSilver, all_shots)
            if all_stats:
                self.db.bulk_insert_mappings(MatchStatSilver, all_stats)
            
            self.db.commit()
            logger.info(f"[{match_id}] Guardado en SILVER exitosamente.")
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error crítico procesando partido {match_id}: {e}")

    