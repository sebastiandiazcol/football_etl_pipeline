# 🚀 Guía de Despliegue — Football Analytics Dashboard

Esta guía explica cómo correr el proyecto **localmente** (en tu computador) y cómo desplegarlo en **Vercel** (frontend en la nube) + un servicio de hosting para el backend.

---

## Tabla de contenidos

1. [Requisitos previos](#1-requisitos-previos)
2. [Despliegue local con Docker (recomendado)](#2-despliegue-local-con-docker-recomendado)
3. [Despliegue local sin Docker](#3-despliegue-local-sin-docker)
4. [Despliegue en Vercel (frontend)](#4-despliegue-en-vercel-frontend)
5. [Despliegue del backend en la nube](#5-despliegue-del-backend-en-la-nube)
6. [Variables de entorno](#6-variables-de-entorno)
7. [Agregar un nuevo módulo al dashboard](#7-agregar-un-nuevo-módulo-al-dashboard)

---

## 1. Requisitos previos

| Herramienta | Versión mínima | Para qué |
|---|---|---|
| [Docker Desktop](https://www.docker.com/products/docker-desktop/) | 24+ | Opción local con Docker |
| [Node.js](https://nodejs.org/) | 20+ | Frontend sin Docker |
| [Python](https://www.python.org/) | 3.12+ | Backend sin Docker |
| [PostgreSQL](https://www.postgresql.org/) | 15+ | Base de datos sin Docker |
| Cuenta en [Vercel](https://vercel.com/) | — | Frontend en la nube |

---

## 2. Despliegue local con Docker (recomendado)

> Esta es la forma más sencilla. Solo necesitas tener Docker Desktop instalado.

### 2.1 Clonar el repositorio

```bash
git clone https://github.com/sebastiandiazcol/football_etl_pipeline.git
cd football_etl_pipeline/football_web
```

### 2.2 Configurar variables de entorno

```bash
cp backend/.env.example backend/.env
```

Abre `backend/.env` con cualquier editor de texto y cambia al menos estas líneas:

```env
SECRET_KEY=cambia-esto-por-una-clave-larga-y-segura
POSTGRES_PASSWORD=una_contraseña_segura
```

### 2.3 Iniciar todos los servicios

```bash
docker compose up --build
```

Esto levanta automáticamente:
- 🗄️ **PostgreSQL** en el puerto 5432
- ⚙️ **Backend FastAPI** en el puerto 8000
- 🌐 **Frontend React** en el puerto 5173
- 🔀 **Nginx** (proxy) en el puerto 80

### 2.4 Abrir la aplicación

Visita **http://localhost** en tu navegador.

Para detener todo:

```bash
docker compose down
```

---

### Modo desarrollo (hot reload)

Si quieres que los cambios que hagas en el código se reflejen al instante:

```bash
docker compose -f docker-compose.dev.yml up --build
```

---

## 3. Despliegue local sin Docker

### 3.1 Base de datos PostgreSQL

Crea una base de datos llamada `football_db`:

```sql
CREATE DATABASE football_db;
CREATE USER football_user WITH PASSWORD 'tu_password';
GRANT ALL PRIVILEGES ON DATABASE football_db TO football_user;
```

### 3.2 Backend (FastAPI)

```bash
cd football_web/backend

# Instalar dependencias
pip install -r requirements.txt

# Configurar variables de entorno
cp .env.example .env
# Edita .env con los datos de tu base de datos

# Aplicar migraciones de la base de datos
alembic upgrade head

# Iniciar el servidor
uvicorn main:app --reload --port 8000
```

El backend estará disponible en **http://localhost:8000**

### 3.3 Frontend (React + Vite)

Abre una nueva terminal:

```bash
cd football_web/frontend

# Instalar dependencias
npm install

# Iniciar en modo desarrollo
npm run dev
```

El frontend estará disponible en **http://localhost:5173**

> **Nota:** El frontend espera que el backend esté en `http://localhost:8000`. Si lo cambias, edita `frontend/src/hooks/useApi.ts`.

---

## 4. Despliegue en Vercel (frontend)

Vercel es un servicio gratuito para alojar aplicaciones web. El frontend se puede desplegar ahí fácilmente.

### 4.1 Preparar la variable de entorno de producción

El frontend necesita saber la URL de tu backend (verás cómo obtenerla en la siguiente sección).

### 4.2 Conectar Vercel con GitHub

1. Ve a [vercel.com](https://vercel.com) e inicia sesión con tu cuenta de GitHub
2. Haz clic en **"Add New Project"**
3. Selecciona el repositorio `football_etl_pipeline`
4. En la pantalla de configuración:
   - **Framework Preset:** `Vite`
   - **Root Directory:** `football_web/frontend`
   - **Build Command:** `npm run build`
   - **Output Directory:** `dist`

5. En la sección **"Environment Variables"** añade:

   | Nombre | Valor |
   |---|---|
   | `VITE_API_BASE_URL` | URL de tu backend (ej: `https://mi-backend.railway.app`) |

6. Haz clic en **"Deploy"**

Cada vez que hagas `git push` a la rama `main`, Vercel re-desplegará automáticamente.

### 4.3 Dominio personalizado (opcional)

En el panel de Vercel → Settings → Domains, puedes añadir tu propio dominio.

---

## 5. Despliegue del backend en la nube

El backend (FastAPI + PostgreSQL) necesita un servidor. Las opciones más sencillas son:

### Opción A — Railway (recomendado para principiantes)

1. Ve a [railway.app](https://railway.app) y conéctalo con tu GitHub
2. Crea un nuevo proyecto → **"Deploy from GitHub repo"**
3. Selecciona el repositorio y configura:
   - **Root Directory:** `football_web/backend`
   - **Start Command:** `uvicorn main:app --host 0.0.0.0 --port $PORT`
4. Añade un servicio de **PostgreSQL** desde el panel de Railway
5. Railway pondrá automáticamente la variable `DATABASE_URL` en tu servicio
6. Añade el resto de variables de entorno (ver sección 6)

### Opción B — Render

1. Ve a [render.com](https://render.com) y crea un **"Web Service"**
2. Conecta tu repositorio
3. Configura:
   - **Root Directory:** `football_web/backend`
   - **Build Command:** `pip install -r requirements.txt && alembic upgrade head`
   - **Start Command:** `uvicorn main:app --host 0.0.0.0 --port $PORT`
4. Crea una base de datos PostgreSQL gratuita desde Render y copia la URL de conexión

### Opción C — Fly.io

Fly.io tiene un nivel gratuito generoso y es más avanzado. Consulta su [documentación oficial](https://fly.io/docs/languages-and-frameworks/python/).

---

## 6. Variables de entorno

Todas las variables van en `football_web/backend/.env`. Copia `backend/.env.example` como punto de partida.

| Variable | Descripción | Ejemplo |
|---|---|---|
| `SECRET_KEY` | Clave secreta para firmar JWT. **Cámbiala siempre.** | `openssl rand -hex 32` |
| `DATABASE_URL` | URL de conexión a PostgreSQL | `postgresql+asyncpg://user:pass@host/db` |
| `POSTGRES_USER` | Usuario de PostgreSQL | `football_user` |
| `POSTGRES_PASSWORD` | Contraseña de PostgreSQL | `mi_contraseña` |
| `POSTGRES_DB` | Nombre de la base de datos | `football_db` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Duración del token de sesión (minutos) | `30` |
| `REFRESH_TOKEN_EXPIRE_DAYS` | Duración del refresh token (días) | `7` |
| `ALLOWED_ORIGINS` | Dominios permitidos (CORS) | `https://mi-app.vercel.app` |

### Generar una SECRET_KEY segura

En Linux/Mac:
```bash
openssl rand -hex 32
```

En Windows (PowerShell):
```powershell
-join ((48..57 + 65..90 + 97..122) | Get-Random -Count 64 | % {[char]$_})
```

---

## 7. Agregar un nuevo módulo al dashboard

El dashboard está diseñado para ser extensible. Agregar una nueva sección es muy simple:

### Paso 1 — Crear el archivo del módulo

Crea `football_web/frontend/src/modules/MiNuevoModulo.tsx`:

```tsx
import type { ModuleProps } from './types';

export default function MiNuevoModulo({ stats, matches, user }: ModuleProps) {
  return (
    <div style={{ background: '#1e293b', borderRadius: '12px', padding: '1.5rem', marginBottom: '2rem' }}>
      <h2 style={{ color: '#94a3b8' }}>Mi Nuevo Módulo</h2>
      {/* Tu contenido aquí */}
    </div>
  );
}
```

### Paso 2 — Registrarlo

Abre `football_web/frontend/src/modules/registry.ts` y añade dos líneas:

```ts
// 1. Importa tu módulo (arriba, con los demás imports)
import MiNuevoModulo from './MiNuevoModulo';

// 2. Añádelo al array donde quieras que aparezca
export const dashboardModules: ModuleDefinition[] = [
  ...
  { id: 'mi-nuevo-modulo', component: MiNuevoModulo },  // ← esta línea
];
```

### Datos disponibles en ModuleProps

| Prop | Tipo | Descripción |
|---|---|---|
| `stats` | `DashboardStats \| null` | Totales globales (partidos, equipos, BTTS…) |
| `matches` | `TeamMatch[]` | Partidos recientes |
| `teams` | `Team[]` | Lista de equipos |
| `players` | `PlayerStat[]` | Estadísticas de jugadores |
| `selectedTeamId` | `string` | Equipo seleccionado en Analytics |
| `teamStats` | `TeamMatch[]` | Historial del equipo seleccionado |
| `onTeamChange` | `(id: string) => void` | Cambiar equipo seleccionado |
| `user` | `User \| null` | Usuario autenticado (email, role…) |

---

## Solución de problemas comunes

| Problema | Solución |
|---|---|
| `Error: connect ECONNREFUSED 127.0.0.1:8000` | El backend no está corriendo. Revisa los logs con `docker compose logs backend` |
| `CORS error` en el navegador | Añade el dominio del frontend a `ALLOWED_ORIGINS` en `.env` |
| `alembic: command not found` | Ejecuta dentro del entorno virtual de Python: `source venv/bin/activate` |
| Los cambios en el código no se reflejan | Usa el modo desarrollo: `docker compose -f docker-compose.dev.yml up` |
| `SECRET_KEY must be set` al iniciar el backend | Copia `.env.example` a `.env` y rellena `SECRET_KEY` |
