import aiosqlite
import asyncio
import os

async def test():
    db_path = 'data/03_gold.db'
    print(f"Checking {db_path}...")
    try:
        conn = await aiosqlite.connect(db_path)
        conn.row_factory = aiosqlite.Row
        print("Connected successfully!")
        query = """
            SELECT
                COUNT(*) AS total_matches,
                COUNT(DISTINCT team_id) AS total_teams,
                ROUND(AVG(CAST(is_btts AS FLOAT)) * 100, 2) AS btts_percentage,
                ROUND(AVG(CAST(is_over_2_5 AS FLOAT)) * 100, 2) AS over25_percentage,
                ROUND(AVG(CAST(goals_for + goals_against AS FLOAT)), 2) AS avg_goals_per_match
            FROM fact_team_match
        """
        async with conn.execute(query) as cursor:
            row = await cursor.fetchone()
            print(f"Result: {dict(row)}")
        await conn.close()
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test())
