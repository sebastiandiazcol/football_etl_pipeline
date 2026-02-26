# transform/create_dim_date.py
import sqlite3
import pandas as pd
from datetime import date

def generate_dim_date(start_year=2020, end_year=2030, db_path="data/03_gold.db"):
    print("Generando Dimension Calendario (dim_date)...")
    
    start_date = f"{start_year}-01-01"
    end_date = f"{end_year}-12-31"
    
    df_date = pd.DataFrame({"date": pd.date_range(start_date, end_date)})
    
    # Derivar columnas analiticas
    df_date["date_key"] = df_date["date"].dt.strftime('%Y%m%d').astype(int)
    df_date["date_actual"] = df_date["date"].dt.date
    df_date["year"] = df_date["date"].dt.year
    df_date["month"] = df_date["date"].dt.month
    df_date["day"] = df_date["date"].dt.day
    df_date["quarter"] = df_date["date"].dt.quarter
    
    # Nombres en espanol para el analista
    meses = {1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril', 5: 'Mayo', 6: 'Junio', 
             7: 'Julio', 8: 'Agosto', 9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre'}
    dias = {0: 'Lunes', 1: 'Martes', 2: 'Miercoles', 3: 'Jueves', 4: 'Viernes', 5: 'Sabado', 6: 'Domingo'}
    
    df_date["month_name"] = df_date["month"].map(meses)
    df_date["day_name"] = df_date["date"].dt.dayofweek.map(dias)
    df_date["is_weekend"] = df_date["date"].dt.dayofweek.isin([5, 6]).astype(int)

    # Ordenar columnas
    df_date = df_date[["date_key", "date_actual", "year", "quarter", "month", "month_name", "day", "day_name", "is_weekend"]]

    # Guardar en SQLite (GOLD)
    con = sqlite3.connect(db_path)
    
    # Reemplazar si existe
    df_date.to_sql("dim_date", con, if_exists="replace", index=False)
    
    # Crear un indice para acelerar las consultas
    cursor = con.cursor()
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_dim_date_key ON dim_date(date_key);")
    con.commit()
    con.close()
    
    print(f"DimDate creada exitosamente con {len(df_date)} registros (Desde {start_year} hasta {end_year}).")

if __name__ == "__main__":
    generate_dim_date()