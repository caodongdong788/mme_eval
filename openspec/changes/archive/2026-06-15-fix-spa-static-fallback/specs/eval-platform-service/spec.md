## ADDED Requirements

### Requirement: Production static hosting MUST fallback SPA routes to index.html

When `frontend/dist` exists, the platform MUST serve built static files and MUST return `index.html` with HTTP 200 for client-side routes (e.g. `/runs`, `/runs/1`) that do not map to a physical file under `dist/`. Requests under `/api/` MUST continue to be handled by API routers and MUST NOT be overridden by the SPA fallback.

#### Scenario: Direct navigation to /runs

- **WHEN** a GET request is made to `/runs` and `frontend/dist/index.html` exists
- **THEN** the response MUST be HTTP 200 with the `index.html` body

#### Scenario: Static asset still served

- **WHEN** a GET request is made to `/assets/main.js` and the file exists under `frontend/dist/assets/`
- **THEN** the response MUST be HTTP 200 with the file contents
