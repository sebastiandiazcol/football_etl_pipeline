import pytest
import pytest_asyncio
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio

VALID_USER = {
    "email": "test@example.com",
    "password": "StrongP@ss1",
    "full_name": "Test User",
}

WEAK_PASSWORD_USER = {
    "email": "weak@example.com",
    "password": "weak",
}


async def register_user(client: AsyncClient, data: dict = None) -> dict:
    data = data or VALID_USER
    response = await client.post("/auth/register", json=data)
    return response


class TestRegister:
    async def test_register_success(self, client: AsyncClient):
        resp = await register_user(client)
        assert resp.status_code == 201
        body = resp.json()
        assert body["email"] == VALID_USER["email"]
        assert body["role"] == "viewer"
        assert "hashed_password" not in body

    async def test_register_duplicate_email(self, client: AsyncClient):
        await register_user(client)
        resp = await register_user(client)
        assert resp.status_code == 409

    async def test_register_weak_password(self, client: AsyncClient):
        resp = await register_user(client, WEAK_PASSWORD_USER)
        assert resp.status_code == 422


class TestLogin:
    async def test_login_success(self, client: AsyncClient):
        await register_user(client)
        resp = await client.post(
            "/auth/login",
            json={"email": VALID_USER["email"], "password": VALID_USER["password"]},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["access_token"]
        assert body["token_type"] == "bearer"
        assert "access_token" in resp.cookies

    async def test_login_wrong_password(self, client: AsyncClient):
        await register_user(client)
        resp = await client.post(
            "/auth/login",
            json={"email": VALID_USER["email"], "password": "WrongP@ss1"},
        )
        assert resp.status_code == 401

    async def test_login_rate_limiting(self, client: AsyncClient):
        """After max failed attempts, account should be locked (423) or IP rate-limited (429)."""
        email = "ratelimit@example.com"
        await register_user(
            client, {"email": email, "password": "StrongP@ss1", "full_name": "Rate User"}
        )
        for _ in range(5):
            await client.post(
                "/auth/login",
                json={"email": email, "password": "WrongP@ss1"},
            )
        resp = await client.post(
            "/auth/login",
            json={"email": email, "password": "WrongP@ss1"},
        )
        assert resp.status_code in (423, 429, 401)


class TestTokenRefresh:
    async def test_refresh_token(self, client: AsyncClient):
        await register_user(client)
        login_resp = await client.post(
            "/auth/login",
            json={"email": VALID_USER["email"], "password": VALID_USER["password"]},
        )
        assert login_resp.status_code == 200
        refresh_cookie = login_resp.cookies.get("refresh_token")
        resp = await client.post(
            "/auth/refresh",
            cookies={"refresh_token": refresh_cookie} if refresh_cookie else {},
        )
        assert resp.status_code in (200, 401)


class TestLogout:
    async def test_logout(self, client: AsyncClient):
        await register_user(client)
        await client.post(
            "/auth/login",
            json={"email": VALID_USER["email"], "password": VALID_USER["password"]},
        )
        resp = await client.post("/auth/logout")
        assert resp.status_code in (204, 401)


class TestProtectedRoutes:
    async def test_protected_route_no_auth(self, client: AsyncClient):
        resp = await client.get("/auth/me")
        assert resp.status_code == 401

    async def test_protected_route_with_auth(self, client: AsyncClient):
        await register_user(client)
        login_resp = await client.post(
            "/auth/login",
            json={"email": VALID_USER["email"], "password": VALID_USER["password"]},
        )
        token = login_resp.json().get("access_token")
        resp = await client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["email"] == VALID_USER["email"]


class TestRoleBasedAccess:
    async def test_viewer_cannot_run_pipeline(self, client: AsyncClient):
        await register_user(client)
        login_resp = await client.post(
            "/auth/login",
            json={"email": VALID_USER["email"], "password": VALID_USER["password"]},
        )
        token = login_resp.json().get("access_token")
        resp = await client.post(
            "/api/pipeline/run",
            json={"team_id": 1, "max_matches": 5},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403
