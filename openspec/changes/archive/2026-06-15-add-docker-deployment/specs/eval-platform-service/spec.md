## ADDED Requirements

### Requirement: Container deployment

The platform MUST support deployment via Docker: a multi-stage image that builds the frontend and runs the FastAPI application with static asset hosting on port 8000.

The repository MUST provide `docker-compose.yml` orchestrating the application service with PostgreSQL, persistent volumes for `outputs/` and `uploads/`, and a health check against `GET /api/health`.

Production container runs MUST set `MEDEVAL_ENV=production` and MUST NOT use the default `SESSION_SECRET`; secrets and `config.yaml` SHALL be supplied via environment variables or mounted files, not baked into the image.

#### Scenario: Compose startup with health check

- **WHEN** an operator runs `docker compose up --build` with a valid `.env` and `SESSION_SECRET`
- **THEN** the `app` service SHALL start uvicorn on port 8000, serve the built frontend, and respond `{"status":"ok"}` from `GET /api/health`
- **AND** `outputs/` and `uploads/` data SHALL persist across container restarts via mounted volumes
