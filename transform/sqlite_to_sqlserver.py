import sqlite3
import pandas as pd
from sqlalchemy import create_engine
import urllib
import os

def migrate_to_sqlserver():
    # Usar las rutas correctas usando os.path
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sqlite_db_path = os.path.join(base_dir, "data", "03_gold.db")
    
    print("Conectando a SQLite Gold...")
    sqlite_conn = sqlite3.connect(sqlite_db_path)
    
    # === ¡AQUÍ PONES TU CONTRASEÑA DE DOCKER! ===
    # El usuario por defecto en Docker es siempre 'sa'
    usuario = "sa"
    password = "SuperSecret123!" 
    servidor = "localhost,1433"
    base_datos = "FootballGold"
    
    print(f"Test de conexión al servidor {servidor} con usuario {usuario}...")
    
    # Creamos un engine de conexión para sqlalchemy usando pyodbc
    # Es muy importante el driver correcto. En este sistema tenemos la versión 18.
    driver = "{ODBC Driver 18 for SQL Server}"
    
    params = urllib.parse.quote_plus(
        f'DRIVER={driver};'
        f'SERVER={servidor};'
        f'DATABASE={base_datos};'
        f'UID={usuario};'
        f'PWD={password};'
        f'TrustServerCertificate=yes;'
    )
    
    # Si la base de datos FootballGold no existe, sqlalchemy fallará al conectar directamente a ella.
    # Por lo que es mejor conectarse a 'master', crear la base y luego conectar a ella.
    try:
        from sqlalchemy import text
        engine_master = create_engine(f"mssql+pyodbc:///?odbc_connect=" + urllib.parse.quote_plus(
            f'DRIVER={driver};SERVER={servidor};DATABASE=master;UID={usuario};PWD={password};TrustServerCertificate=yes;'
        ))
        with engine_master.connect() as conn:
            conn.execution_options(isolation_level="AUTOCOMMIT").execute(
                text(f"IF NOT EXISTS (SELECT * FROM sys.databases WHERE name = '{base_datos}') "
                f"BEGIN CREATE DATABASE {base_datos} END")
            )
        print(f"Base de datos {base_datos} verificada/creada exitosamente en SQL Server.")
    except Exception as e:
        print("ERROR AL CONECTAR A SQL SERVER. Probablemente la contraseña es incorrecta o no tienes el Driver ODBC 17.")
        print("Detalle:", e)
        return
        
    # Conectamos ahora a la base correcta
    sql_engine = create_engine(f"mssql+pyodbc:///?odbc_connect={params}", fast_executemany=True)
    
    # Leemos las tablas
    tablasdf = pd.read_sql("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'", sqlite_conn)
    
    print("\n--- INICIANDO MIGRACIÓN ---")
    for tabla in tablasdf['name']:
        print(f"[*] Migrando tabla: {tabla}...")
        df = pd.read_sql(f"SELECT * FROM {tabla}", sqlite_conn)
        
        # Guardamos en SQL Server, si la tabla existe la reemplazamos con los datos más nuevos
        df.to_sql(tabla, con=sql_engine, if_exists='replace', index=False)
        print(f"    -> {len(df)} filas copiadas cruzando SQLite a SQL Server.")
        
    print("\n--- ¡TODAS LAS TABLAS HAN SIDO ACTUALIZADAS EN SQL SERVER! ---")
    sqlite_conn.close()

if __name__ == "__main__":
    migrate_to_sqlserver()
