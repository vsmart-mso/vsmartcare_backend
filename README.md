## Backend services (FastAPI)

This folder contains starter microservices for the selfservice system.

### Services

- `bff`: Backend-for-Frontend (single entrypoint for the frontend)
- `case-service`: create and track requests/cases
- `notification-service`: queue + send notifications (starter)
- `thaid-auth-service`: adapter for ThaiD login (starter/mock)

### Run locally

From this folder:

```bash
docker compose up --build
```

Services will be available on:

- `bff`: `http://localhost:8000`
- `case-service`: `http://localhost:8001`
- `notification-service`: `http://localhost:8002`
- `thaid-auth-service`: `http://localhost:8003`

