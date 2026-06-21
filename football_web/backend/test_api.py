import httpx
import asyncio

async def test():
    # Login to get token
    login_url = "http://localhost:8000/auth/login"
    login_data = {
        "email": "sebastian@futbol.com",
        "password": "Password123!" 
    }
    
    print("Attempting login...")
    async with httpx.AsyncClient() as client:
        resp = await client.post(login_url, json=login_data)
        if resp.status_code != 200:
            print(f"Login failed: {resp.status_code} {resp.text}")
            return

        print("Login successful. Hitting /api/dashboard/stats...")
        # Get cookies from login response
        cookies = resp.cookies
        resp = await client.get("http://localhost:8000/api/dashboard/stats", cookies=cookies)
        print(f"Stats Status: {resp.status_code}")
        print(f"Stats Body: {resp.text}")

if __name__ == "__main__":
    asyncio.run(test())
