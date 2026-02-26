# transform/silver_to_gold.py
import logging
from sqlalchemy.orm import Session
from sqlalchemy.dialects.sqlite import insert

from db.models.silver_models import MatchSilver, MatchStatSilver, MatchShotSilver, MatchLineupSilver, MatchEventSilver
from db.models.gold_models import DimTeam, DimPlayer, DimCompetition, FactMatch, FactMatchStat, FactShot
from utils.logger import setup_logger

logger = setup_logger("SilverToGold")

class SilverToGoldETL:
    """
    Motor que transforma datos relacionales normalizados (Silver) 
    a un Esquema Estrella analítico (Gold) optimizado para Power BI.
    """
    def __init__(self, db_silver: Session, db_gold: Session):
        self.db_silver = db_silver
        self.db_gold = db_gold

    def _upsert_dimensions(self, match_silver: MatchSilver):
        """
        Garantiza que la Liga y los Equipos existan en las dimensiones GOLD.
        """
        comp = self.db_gold.query(DimCompetition).filter_by(competition_id=match_silver.competition_id).first()
        if not comp and match_silver.competition_id:
            new_comp = DimCompetition(
                competition_id=match_silver.competition_id,
                competition_name=match_silver.competition_name
            )
            self.db_gold.add(new_comp)

        for team_id, team_name in [
            (match_silver.home_team_id, match_silver.home_team_name), 
            (match_silver.away_team_id, match_silver.away_team_name)
        ]:
            if team_id:
                team = self.db_gold.query(DimTeam).filter_by(team_id=team_id).first()
                if not team:
                    new_team = DimTeam(team_id=team_id, team_name=team_name)
                    self.db_gold.add(new_team)
        
        self.db_gold.commit()

    def _upsert_players_from_silver(self, match_id: int):
        """
        Extrae TODOS los jugadores del partido (alineaciones, eventos, tiros)
        y actualiza la dimensión DimPlayer.
        """
        player_dict = {}
        
        lineups = self.db_silver.query(MatchLineupSilver).filter_by(match_id=match_id).all()
        for l in lineups:
            if l.player_id: player_dict[l.player_id] = l.player_name
            
        events = self.db_silver.query(MatchEventSilver).filter_by(match_id=match_id).all()
        for e in events:
            if e.primary_player_id: player_dict[e.primary_player_id] = e.primary_player_name
            if e.secondary_player_id: player_dict[e.secondary_player_id] = e.secondary_player_name
            
        shots = self.db_silver.query(MatchShotSilver).filter_by(match_id=match_id).all()
        for s in shots:
            if s.player_id: player_dict[s.player_id] = s.player_name

        for p_id, p_name in player_dict.items():
            if not p_id or p_name == 'Unknown': 
                continue 
                
            player = self.db_gold.query(DimPlayer).filter_by(player_id=p_id).first()
            if not player:
                new_player = DimPlayer(player_id=p_id, player_name=p_name)
                self.db_gold.add(new_player)
            elif player.player_name == 'Unknown' or player.player_name != p_name:
                player.player_name = p_name
                
        self.db_gold.commit()

    def process_match_to_gold(self, match_id: int):
        """
        Pasa un partido específico de Silver a Gold.
        """
        match_silver = self.db_silver.query(MatchSilver).filter_by(match_id=match_id).first()
        if not match_silver:
            logger.error(f"[{match_id}] No se encontro el partido en la capa SILVER.")
            return

        try:
            self._upsert_dimensions(match_silver)
            self._upsert_players_from_silver(match_id)
            
            existing_fact = self.db_gold.query(FactMatch).filter_by(match_id=match_id).first()
            if existing_fact:
                logger.info(f"[{match_id}] Reescribiendo partido en capa GOLD...")
                self.db_gold.query(FactMatchStat).filter_by(match_id=match_id).delete()
                self.db_gold.query(FactShot).filter_by(match_id=match_id).delete()
                self.db_gold.delete(existing_fact)
                self.db_gold.commit()

            home_score = int(match_silver.home_score) if match_silver.home_score is not None else 0
            away_score = int(match_silver.away_score) if match_silver.away_score is not None else 0
            
            is_draw = 1 if home_score == away_score else 0
            winning_team_id = None
            if home_score > away_score:
                winning_team_id = match_silver.home_team_id
            elif away_score > home_score:
                winning_team_id = match_silver.away_team_id

            fact_match = FactMatch(
                match_id=match_silver.match_id,
                match_date=match_silver.match_date,
                season_num=match_silver.season_num,
                competition_id=match_silver.competition_id,
                home_team_id=match_silver.home_team_id,
                away_team_id=match_silver.away_team_id,
                home_score=home_score,
                away_score=away_score,
                total_goals=(home_score + away_score),
                is_draw=is_draw,
                winning_team_id=winning_team_id
            )
            self.db_gold.add(fact_match)

            silver_stats = self.db_silver.query(MatchStatSilver).filter_by(match_id=match_id).all()
            gold_stats = []
            for stat in silver_stats:
                gold_stats.append({
                    "match_id": stat.match_id,
                    "team_id": stat.team_id,
                    "period": stat.period,
                    "stat_name": stat.stat_name,
                    "category_name": stat.category_name,
                    "value_numeric": stat.value_numeric 
                })
            
            if gold_stats:
                self.db_gold.bulk_insert_mappings(FactMatchStat, gold_stats)

            silver_shots = self.db_silver.query(MatchShotSilver).filter_by(match_id=match_id).all()
            gold_shots = []
            for shot in silver_shots:
                gold_shots.append({
                    "match_id": shot.match_id,
                    "team_id": shot.team_id,
                    "player_id": shot.player_id,
                    "shot_minute": shot.shot_minute,
                    "xg": shot.xg,
                    "xgot": shot.xgot,
                    "outcome_name": shot.outcome_name,
                    "position_x": shot.position_x,
                    "position_y": shot.position_y
                })
            
            if gold_shots:
                self.db_gold.bulk_insert_mappings(FactShot, gold_shots)

            self.db_gold.commit()
            logger.info(f"[{match_id}] Migracion a GOLD (Star Schema) exitosa.")

        except Exception as e:
            self.db_gold.rollback()
            logger.error(f"Error migrando partido {match_id} a GOLD: {e}")
            import traceback
            logger.error(traceback.format_exc())