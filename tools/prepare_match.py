# tools/prepare_match.py
import sys
import os
import requests

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from main import process_team_matches
from transform.create_betting_facts import create_betting_tables
from db.database import init_db

def search_team(team_query: str) -> int:
    """Busca un equipo o procesa directamente el ID, cruzando Pais y Liga."""
    
    # 1. Bypass Directo
    if team_query.isdigit():
        print(f"  Usando ID directo: {team_query}")
        return int(team_query)
        
    url = "https://webws.365scores.com/web/search/"
    params = {
        'appTypeId': 5,
        'langId': 14,
        'timezoneName': 'America/Bogota',
        'q': team_query
    }
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    try:
        response = requests.get(url, params=params, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        # Diccionarios en memoria para traducir los IDs de Pais y Liga a Texto
        countries = {c.get('id'): c.get('name') for c in data.get('countries', [])}
        competitions = {c.get('id'): c.get('name') for c in data.get('competitions', [])}
        
        competitors = [c for c in data.get('competitors', []) if c.get('sportId') == 1]
        
        matched = []
        for c in competitors:
            name_lower = c.get('name', '').lower()
            query_lower = team_query.lower()
            if any(word in name_lower for word in query_lower.split()) or query_lower in name_lower:
                matched.append(c)
        
        if not matched:
            print(f"  La API no encontro '{team_query}'.")
            print(f"  TRUCO: Ve a 365scores.com, busca a tu equipo en la pagina web.")
            print(f"  El ID es el ultimo numero de la URL. Vuelve a ejecutar y pega solo el numero.")
            return None
            
        print(f"\nResultados para '{team_query}':")
        # Mostraremos hasta 8 opciones para tener mejor visibilidad
        for i, comp in enumerate(matched[:8], 1):
            # Buscar el nombre del pais y la liga usando los diccionarios, con fallback a 'Desconocido'
            country_name = countries.get(comp.get('countryId'), 'Pais Desconocido')
            comp_name = competitions.get(comp.get('mainCompetitionId'), 'Liga Desconocida')
            
            # Formateamos la salida en consola para que sea facil de leer
            print(f"  [{i}] {comp.get('name')} | Pais: {country_name} | Torneo: {comp_name} | ID: {comp.get('id')}")
            
        seleccion = input(f"\nSeleccione el numero del equipo correcto (1-{min(8, len(matched))}) o 0 para cancelar: ")
        
        if seleccion.isdigit():
            idx = int(seleccion)
            if 0 < idx <= len(matched):
                selected_team = matched[idx-1]
                print(f"  Equipo confirmado: {selected_team.get('name')} (ID: {selected_team.get('id')})")
                return selected_team.get('id')
                
        print("  Seleccion cancelada.")
        return None
        
    except Exception as e:
        print(f"  Error al buscar el equipo: {e}")
        return None

def main():
    print("="*65)
    print(" PREPARADOR DE PARTIDOS - ANALITICA DE APUESTAS (H2H)")
    print("="*65)
    
    print("\n1. BUSCAR EQUIPO LOCAL")
    home_query = input("Ingrese el nombre del equipo local o su ID directo (ej: Estrella Roja o 115): ")
    home_id = search_team(home_query)
    
    if not home_id:
        return
        
    print("\n2. BUSCAR EQUIPO VISITANTE")
    away_query = input("Ingrese el nombre del equipo visitante o su ID directo (ej: Millonarios o 2178): ")
    away_id = search_team(away_query)
    
    if not away_id:
        return
        
    print("\n3. CONFIGURACION DE EXTRACCION")
    matches_str = input("Cuantos partidos historicos desea extraer por equipo? (Por defecto 10): ")
    matches_to_fetch = int(matches_str) if matches_str.isdigit() else 10
    
    print(f"\nResumen: Se descargaran los ultimos {matches_to_fetch} partidos de ambos equipos.")
    confirm = input("Desea iniciar el pipeline ETL ahora? (S/N): ")
    
    if confirm.lower() == 's':
        init_db()
        print("\n--- INICIANDO EXTRACCION: EQUIPO LOCAL ---")
        process_team_matches(home_id, matches_to_fetch)
        
        print("\n--- INICIANDO EXTRACCION: EQUIPO VISITANTE ---")
        process_team_matches(away_id, matches_to_fetch)
        
        print("\n--- ACTUALIZANDO TABLAS DE APUESTAS (POWER BI) ---")
        create_betting_tables()
        
        print("\n=======================================================")
        print(" PIPELINE FINALIZADO. DATOS LISTOS PARA POWER BI.")
        print("=======================================================")
    else:
        print("Operacion cancelada.")

if __name__ == "__main__":
    main()