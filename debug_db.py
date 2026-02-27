import sqlite3
import pandas as pd

print("\n--- SILVER DB ---")
conn_silver = sqlite3.connect('data/02_silver.db')
tables_silver = pd.read_sql("SELECT name FROM sqlite_master WHERE type='table';", conn_silver)
print("Silver tables:", tables_silver)

if 'silver_lineups' in tables_silver['name'].values:
    print(pd.read_sql("SELECT * FROM silver_lineups LIMIT 1", conn_silver).columns)

print("\n--- BRONZE DB ---")
conn_bronze = sqlite3.connect('data/01_bronze.db')
tables_bronze = pd.read_sql("SELECT name FROM sqlite_master WHERE type='table';", conn_bronze)
print("Bronze tables:", tables_bronze)

if 'bronze_match_data' in tables_bronze['name'].values:
    pass
