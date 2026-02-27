import sqlite3
import json
import logging
import sys
import os

sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from db.database import SessionSilver, SessionGold, init_db
from transform.bronze_to_silver import BronzeToSilverETL
from transform.silver_to_gold import SilverToGoldETL
from transform.create_powerbi_mart import create_powerbi_mart
import pandas as pd

def reprocess_all():
    print("Iniciando reprocesamiento de Bronze a Silver y Gold para arreglar minutes_played...")
    init_db()
    conn = sqlite3.connect('data/01_bronze.db')
    try:
        df = pd.read_sql("SELECT match_id, raw_json FROM raw_match_data", conn)
    except Exception as e:
        print("Error leyendo raw_match_data:", e)
        return
        
    db_silver = SessionSilver()
    db_gold = SessionGold()

    silver_etl = BronzeToSilverETL(db_silver)
    gold_etl = SilverToGoldETL(db_silver, db_gold)

    for _, row in df.iterrows():
        match_id = int(row['match_id'])
        data = json.loads(row['raw_json'])
        gen_json = json.dumps(data.get('general', {}))
        stats_json = json.dumps(data.get('stats', {}))
        
        print(f"Reprocesando Match ID: {match_id}")
        try:
            silver_etl.process_match(gen_json, stats_json)
            gold_etl.process_match_to_gold(match_id)
        except Exception as e:
            print(f"Error procesando {match_id}: {e}")

    db_silver.close()
    db_gold.close()
    
    print("Reprocesamiento completado. Actualizando PowerBI Mart...")
    create_powerbi_mart()
    
if __name__ == '__main__':
    reprocess_all()
