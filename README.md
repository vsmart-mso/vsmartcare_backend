## Backend services (FastAPI)

This folder contains starter microservices for the selfservice system.

### Deploy to Beta / demo (vsmart-demo)

See [BETA_DEPLOYMENT.md](BETA_DEPLOYMENT.md) — step-by-step Beta deploy for `https://vsmart-demo.m-society.go.th` (prerequisites, env per service, **Beta Docker commands**, nginx, ThaiD, frontend `VITE_*`, post-deploy checks).

### Services

- `bff`: Backend-for-Frontend (single entrypoint for the frontend)
- `case-service`: create and track requests/cases
- `notification-service`: queue + send notifications (starter)
- `thaid-auth-service`: adapter for ThaiD login (real OIDC or mock; see `thaid-auth-service/.env.example`)

### Run locally

Copy `thaid-auth-service/.env.example` to `thaid-auth-service/.env` and set ThaiD credentials (Docker Compose loads that file into `thaid-auth-service`).

Run from this folder (`service/`). Use both compose files: base [`docker-compose.yml`](docker-compose.yml) plus dev overlay [`docker-compose.dev.yml`](docker-compose.dev.yml) (hot-reload, `alembic upgrade head` on case-service).

**Docker Compose (daily use)**

| Task | Command |
|------|---------|
| Build images and start (detached) | `docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build` |
| Start without rebuild | `docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d` |
| Stop and remove containers | `docker compose -f docker-compose.yml -f docker-compose.dev.yml down` |

Optional:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml ps
docker compose -f docker-compose.yml -f docker-compose.dev.yml logs -f
```

Services will be available on:

- `bff`: `http://localhost:8000`
- `case-service`: `http://localhost:8001`
- `notification-service`: `http://localhost:8002`
- `thaid-auth-service`: `http://localhost:8003`

