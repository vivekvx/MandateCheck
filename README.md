# MandateCheck

A deterministic gate that checks every AI-agent payment request against a user-defined mandate before it executes, and a dashboard so the user can watch it happen and revoke access instantly.

Status: early development

## Getting started

Requires Docker + Docker Compose.

```
cp .env.example .env   # optional — defaults work as-is; set GROQ_API_KEY for the harness
docker compose up --build
```

This brings up three services:

| Service  | Host port | URL                    |
|----------|-----------|-------------------------|
| postgres | 5432      | localhost:5432          |
| backend  | 8000      | http://localhost:8000   |
| frontend | 7009      | http://localhost:7009   |

(Frontend is mapped to host port 7009, not Next.js's usual 3000, to avoid
colliding with other local dev servers — the container itself still runs
on 3000 internally.)

Postgres starts first and must report healthy before the backend starts. The
backend runs the Alembic migration on startup, then serves the API. The
frontend waits for the backend to be healthy, builds, and serves the
dashboard. Open http://localhost:7009 once `docker compose up` settles.

To reset everything, including the database volume:

```
docker compose down -v
```
