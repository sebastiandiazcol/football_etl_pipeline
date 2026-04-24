# ⚽ Football Analytics Dashboard

A full-stack web application for visualising football ETL pipeline data with JWT authentication, MFA support, role-based access control, and interactive charts.

## Features

- 🔐 **JWT Auth** — short-lived access tokens (15 min) + long-lived refresh tokens (7 d) in HttpOnly cookies
- 🛡️ **MFA / TOTP** — optional two-factor authentication via authenticator apps
- 👥 **Role-Based Access** — `admin` and `viewer` roles; only admins can trigger ETL pipelines
- 📊 **Dashboard** — stats cards, goals bar chart, goals trend line chart, recent matches table
- 📈 **Analytics** — per-team performance charts, top players by xG, CSV export
- ⚙️ **Pipeline Runner** — admin UI to trigger the ETL pipeline and track run history
- 🚦 **Rate Limiting** — login endpoint limited to 5 requests/minute via slowapi
- 🔒 **Security Headers** — HSTS, CSP, X-Frame-Options, etc.
- 🐳 **Docker** — production-ready multi-service compose + dev compose with hot reload

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | FastAPI 0.111 + Python 3.11 |
| Frontend | React 18 + TypeScript + Vite 5 |
| Database (users) | PostgreSQL 16 via SQLAlchemy 2 async |
| Auth | JWT (python-jose) + TOTP (pyotp) |
| Migrations | Alembic |
| Proxy | Nginx (TLS termination) |
| Containers | Docker Compose |

## Getting Started

### Prerequisites

- Docker & Docker Compose
- (Dev) Node 20 + Python 3.11

### Development

```bash
cd football_web

# Copy env and fill in values
cp backend/.env.example backend/.env

# Start all services with hot reload
docker compose -f docker-compose.dev.yml up --build
```

- Backend: http://localhost:8000
- Frontend: http://localhost:5173
- API docs: http://localhost:8000/docs (DEBUG=true only)

### Running backend standalone

```bash
cd football_web/backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # edit DATABASE_URL + SECRET_KEY
alembic upgrade head
uvicorn app.main:app --reload
```

### Running frontend standalone

```bash
cd football_web/frontend
npm install
npm run dev
```

### Production

```bash
cd football_web
# Set required env vars
export POSTGRES_PASSWORD=...
export SECRET_KEY=...
export DOMAIN=yourdomain.com

# Place TLS certs in nginx/ssl/fullchain.pem + nginx/ssl/privkey.pem

docker compose up -d --build
```

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SECRET_KEY` | ✅ | — | JWT signing key (≥ 32 chars) |
| `DATABASE_URL` | ✅ | — | `postgresql+asyncpg://user:pass@host/db` |
| `ALLOWED_ORIGINS` | | `["http://localhost:5173"]` | CORS origins JSON array |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | | 15 | Access token lifetime |
| `REFRESH_TOKEN_EXPIRE_DAYS` | | 7 | Refresh token lifetime |
| `DEBUG` | | false | Enables /docs |
| `MFA_ISSUER` | | FootballAnalytics | TOTP issuer name |

## API Overview

### Auth endpoints (`/auth`)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/auth/register` | Create new account |
| POST | `/auth/login` | Authenticate, sets HttpOnly cookies |
| POST | `/auth/logout` | Clear cookies, write audit log |
| POST | `/auth/refresh` | Issue new access token from refresh cookie |
| GET | `/auth/me` | Current user info |
| POST | `/auth/mfa/setup` | Generate TOTP secret + QR code |
| POST | `/auth/mfa/verify` | Enable MFA after verifying code |
| DELETE | `/auth/mfa/disable` | Disable MFA |
| POST | `/auth/change-password` | Change password |

### Dashboard (`/api/dashboard`) — viewer + admin

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/dashboard/stats` | Aggregated stats |
| GET | `/api/dashboard/recent-matches` | Last 20 matches |
| GET | `/api/dashboard/teams` | All teams |

### Analytics (`/api/analytics`) — viewer + admin

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/analytics/team/{id}` | Team stats over time |
| GET | `/api/analytics/players` | Top 50 players by xG |
| GET | `/api/analytics/export/teams` | CSV download |
| GET | `/api/analytics/export/players` | CSV download |

### Pipeline (`/api/pipeline`) — admin only

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/pipeline/run` | Trigger ETL |
| GET | `/api/pipeline/runs` | Run history |
| GET | `/api/pipeline/runs/{id}` | Run details |

## Security Features

- Passwords hashed with bcrypt (12 rounds)
- Password strength validation (uppercase, lowercase, digit, special char)
- Account lockout after 5 failed login attempts (15-minute lock)
- JWT access tokens expire in 15 minutes
- Refresh tokens stored in HttpOnly, SameSite cookies
- TOTP-based MFA with QR code setup
- Audit log for all auth events
- Rate limiting on login endpoint
- Full security header suite (HSTS, CSP, X-Frame-Options, …)

## Running Tests

```bash
cd football_web/backend
pip install -r requirements.txt
pytest tests/ -v
```
