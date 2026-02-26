# transform/silver_to_gold.py
import logging
from sqlalchemy.orm import Session
from sqlalchemy.dialects.sqlite import insert

from db.models.silver_models import MatchSilver, MatchStatSilver, MatchShotSilver, MatchLineupSilver, MatchEventSilver
from db.models.gold_models import DimTeam, DimPlayer, DimCompetition, FactMatch, FactMatchStat, FactShot, FactLineup, FactEvent
from utils.logger import setup_logger

logger = setup_logger("SilverToGold")

class SilverToGoldETL:
    def __init__(self, db_silver: Session, db_gold: Session):
        self.db_silver = db_silver
        self.db_gold = db_gold

    def _upsert_dimensions(self, match_silver: MatchSilver):
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
                self.db_gold.query(FactLineup).filter_by(match_id=match_id).delete()
                self.db_gold.query(FactEvent).filter_by(match_id=match_id).delete()
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
            gold_stats = [{"match_id": s.match_id, "team_id": s.team_id, "period": s.period, "stat_name": s.stat_name, "category_name": s.category_name, "value_numeric": s.value_numeric} for s in silver_stats]
            if gold_stats:
                self.db_gold.bulk_insert_mappings(FactMatchStat, gold_stats)

            silver_shots = self.db_silver.query(MatchShotSilver).filter_by(match_id=match_id).all()
            gold_shots = [{"match_id": s.match_id, "team_id": s.team_id, "player_id": s.player_id, "shot_minute": s.shot_minute, "xg": s.xg, "xgot": s.xgot, "outcome_name": s.outcome_name, "position_x": s.position_x, "position_y": s.position_y} for s in silver_shots]
            if gold_shots:
                self.db_gold.bulk_insert_mappings(FactShot, gold_shots)

            silver_lineups = self.db_silver.query(MatchLineupSilver).filter_by(match_id=match_id).all()
            gold_lineups = [{"match_id": l.match_id, "team_id": l.team_id, "player_id": l.player_id, "jersey_number": l.jersey_number, "status_text": l.status_text, "formation_line": l.formation_line, "field_line": l.field_line, "field_side": l.field_side, "minutes_played": l.minutes_played} for l in silver_lineups]
            if gold_lineups:
                self.db_gold.bulk_insert_mappings(FactLineup, gold_lineups)

            silver_events = self.db_silver.query(MatchEventSilver).filter_by(match_id=match_id).all()
            gold_events = [{"match_id": e.match_id, "team_id": e.team_id, "event_order": e.event_order, "game_minute": e.game_minute, "event_type_name": e.event_type_name, "event_sub_type": e.event_sub_type, "primary_player_id": e.primary_player_id, "secondary_player_id": e.secondary_player_id, "is_major": e.is_major} for e in silver_events]
            if gold_events:
                self.db_gold.bulk_insert_mappings(FactEvent, gold_events)

            self.db_gold.commit()
            logger.info(f"[{match_id}] Migracion a GOLD (Star Schema) exitosa.")

        except Exception as e:
            self.db_gold.rollback()
            logger.error(f"Error migrando partido {match_id} a GOLD: {e}")
            import traceback
            logger.error(traceback.format_exc())