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

## Deployment

Repo prep only right now — `render.yaml` exists but nothing is deployed yet.
Two platforms, split by env var:

**Render (backend + Postgres)** — configured via `render.yaml`:
- `DATABASE_URL` — auto-filled from the linked Postgres resource, not set by hand
- `FRONTEND_ORIGIN` — the deployed Vercel URL (CORS). Not known until the
  frontend is deployed — see the order below.
- `GROQ_API_KEY` — same key used locally, for the agent harness only

**Vercel (frontend)** — set as project env vars, not in `render.yaml`:
- `NEXT_PUBLIC_API_BASE_URL` — the deployed Render backend's URL
  (`https://...`). Baked in at build time since it's `NEXT_PUBLIC_`, so it
  must be set before the Vercel build runs, not after.
- `NEXT_PUBLIC_DEMO_USER_ID` — same as local (`demo-user` default)

Deploy order (chicken-and-egg: each side's URL is the other side's input):
1. Deploy the backend to Render first. `FRONTEND_ORIGIN` won't have its real
   value yet — leave it unset or pointed at `http://localhost:7009`
   temporarily. Note the backend's Render URL once live.
2. Deploy the frontend to Vercel with `NEXT_PUBLIC_API_BASE_URL` set to that
   Render URL. Note the frontend's Vercel URL once live.
3. Update `FRONTEND_ORIGIN` on Render to the real Vercel URL and redeploy
   the backend once, so CORS accepts requests from the live frontend.

`docker-compose.yml` is unaffected — it stays as the local dev path.
