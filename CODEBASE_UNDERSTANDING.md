# VoltEdge codebase understanding

This guide is a map for developers and coding assistants working in this repository. It describes the implementation as it exists today; check the source and FastAPI `/docs` before relying on route behavior because the prototype is actively changing.

## Product model

VoltEdge is a factory energy monitoring and operations prototype with two roles:

- **Admin** configures machines, employees, assignments, devices, and model mappings; reviews plant-wide telemetry, alerts, tasks, reports, and recommendations.
- **Operator** sees assigned machines and handles work, alerts, approvals, reports, and analysis permitted for that operator.

The app has three distinct runtime modes. Do not assume every page is using the same source:

| Mode | Relevant frontend flags | Data source |
|---|---|---|
| Mock/demo | `VITE_USE_MOCK=true` and `VITE_USE_LIVE_AUTH=false` | Local browser services/sample data |
| Backend auth with mock machines | `VITE_USE_LIVE_AUTH=true`, `VITE_USE_LIVE_MACHINES=false` | FastAPI for auth and selected admin/operations APIs; mock machine readings |
| Full backend | `VITE_USE_LIVE_AUTH=true`, `VITE_USE_LIVE_MACHINES=true`, `VITE_USE_MOCK=false` | FastAPI + MongoDB for auth and machine data; telemetry arrives via HTTP simulator or MQTT |

Service-specific feature flags also affect whether reports, analytics, alerts, requests, or tasks use live endpoints. When debugging a page, inspect the corresponding service module and flags rather than assuming a single global switch controls every call.

## Runtime and request flow

```text
Browser (React + Vite, normally :5173)
  ├─ React Router: login, admin routes, operator routes
  ├─ AuthContext: current user/token and heartbeat
  ├─ DataProvider: shared machines, recommendations, requests, alerts, tariff
  └─ src/services/*: mock or JSON API calls
           │ /api/* (Vite proxy strips /api)
           ▼
FastAPI (normally :8000)
  ├─ auth/role checks and API schemas
  ├─ MongoDB Atlas collections
  ├─ MQTT subscriber → telemetry validation → MongoDB
  ├─ HTTP demo meter → telemetry persistence
  └─ ML service adapter → trained energy/anomaly models
```

The frontend does not currently receive a backend WebSocket stream. With live machine mode enabled and `VITE_WS_URL` empty, `machineService` polls `/machines` every five seconds. Some device/dashboard summaries also poll their API endpoints. Vite's `/api` proxy points to `http://localhost:8000` and removes the `/api` prefix before forwarding.

## Frontend map

- `frontend/src/main.jsx`: browser entry point and top-level providers.
- `frontend/src/App.jsx`: route table. `/login` is outside the authenticated shell; admin/operator application routes are protected.
- `frontend/src/components/Protected.jsx`: role and authentication gate.
- `frontend/src/components/Shell.jsx`: shared navigation shell for authenticated pages.
- `frontend/src/components/TopBar.jsx`: language/theme controls, signed-in identity, logout, admin demo meter button. This component may also render on login, outside `DataProvider`; code must tolerate `useData()` returning no value there.
- `frontend/src/context/AuthContext.jsx`: user state, login/logout, and live session heartbeat.
- `frontend/src/context/DataContext.jsx`: shared machines/recommendations/requests/alerts/tariff while the authenticated shell is mounted.
- `frontend/src/context/AppContext.jsx`: preferences, translation helpers, theme, and toasts.
- `frontend/src/services/`: API wrapper and feature services. Keep fetch/auth headers and mock-vs-live decisions here where practical.
- `frontend/src/services/mock/`: seeded sample data used by demo mode.
- `frontend/src/engine/`: frontend machine normalization and recommendation helpers.
- `frontend/src/pages/admin/`: administrator pages.
- `frontend/src/pages/operator/`: operator-specific pages; several analysis pages reuse admin page components with role-based filtering.
- `frontend/src/components/Ui.jsx`: shared cards, pills, charts, loading/empty states, and recommendation UI.

When adding a page, verify the route in `App.jsx`, the role behavior, the matching service, and whether the user needs DataProvider context. Do not make login routes depend on data that is only loaded after authentication.

## Backend map

- `backend/app/main.py`: FastAPI app, startup/shutdown behavior, MongoDB-backed routes, report/analytics logic, demo meter thread, initial-admin seeding.
- `backend/app/models.py`: Pydantic request and response shapes and validation.
- `backend/app/core/database.py`: dotenv loading, MongoDB client and database handle, connection health check.
- `backend/app/core/security.py`: password hashing/verification, JWT creation, bearer authentication, admin dependency.
- `backend/app/mqtt_ingestion.py`: MQTT connection, topic/device checks, telemetry persistence, device last-seen updates.
- `backend/app/ml_service.py`: model loading, telemetry aggregation into 15-minute energy buckets, data readiness, forecasts, analysis caching, anomaly recommendations.
- `backend/app/ml/ml_inference.py`: handoff inference pipeline and feature preparation. Pickled model assets are in the same directory.
- `backend/demo_iot.py`: HTTP API simulator; authenticates as admin and generates readings for active machines every five seconds.
- `backend/demo_mqtt.py`: MQTT publisher; sends readings to one registered MQTT device topic every five seconds.
- `backend/reset_password.py`: interactive local helper to reset an existing user or provision the initial admin, asking for the password without echoing it.
- `backend/MQTT_SETUP.md`: broker, device registration, topic, payload, and troubleshooting details.

The FastAPI route decorators in `backend/app/main.py` and generated docs at `/docs` are authoritative. Routes are grouped by behavior rather than separate router files at present.

## MongoDB data model

MongoDB is document-oriented; there are collections, not SQL tables or ORM models. The main collection names are:

| Collection | Purpose / typical linkage |
|---|---|
| `users` | Employee ID, display name, role, password hash, assigned machine IDs, active state, login/heartbeat/logout timestamps. |
| `machines` | Machine ID, name, plant/type/location, status, operating limits/baselines, optional `ml_asset_id`. |
| `devices` | Device ID, name, linked machine ID, protocol, enabled state, latest `last_seen`. |
| `telemetry` | Machine/device IDs, timestamp, power, energy, voltage/current, power factor, temperature, source. |
| `alerts` | Anomaly/alert details, severity/status, machine, reporter/assignee IDs and names, timestamps/readings. |
| `tasks` | Work assigned to operator employee IDs and linked machine IDs, status and due date. |
| `requests` | Operator requests and admin decisions/approval transitions. |
| `recommendation_feedback` | Per-user feedback attached to recommendation IDs. |

Some supporting collections or feature-specific documents may be added in routes over time. Device and machine identifiers are plain strings and are the primary references between collections. MongoDB's generated `_id` is also present. API serialization may expose aliases such as `id`, `machine_id`, and `device_id`.

## Authentication and roles

- Login is by employee ID and password. Role is loaded from the MongoDB user record; the UI role selector is a login intent/check, not a means to grant a role.
- Passwords are stored as hashes through `pwdlib`'s recommended password hasher. JWT uses `JWT_SECRET_KEY` and expires after `ACCESS_TOKEN_MINUTES`.
- The reserved initial administrator is created during backend startup only if its ID is not already present. Changing `INITIAL_ADMIN_PASSWORD` does not overwrite an existing account's hash; use the reset utility to change it.
- Authenticated API calls use an `Authorization: Bearer <token>` header added by `frontend/src/services/api.js`.
- Operators are filtered against their `machines` assignment list in relevant routes. Admin-only routes use the `require_admin` dependency.
- Login sets `session_active` and login/seen timestamps. Heartbeats refresh last-seen state; logout marks the session inactive. A crashed browser may not send logout, so activity can depend on the heartbeat/freshness logic rather than a definitive sign-out event.

Never log or return raw passwords, JWTs, MongoDB URIs, MQTT secrets, or model credentials. Local `.env` files are private configuration and must not be committed.

## Telemetry and device behavior

An MQTT message uses topic `voltedge/telemetry/<DEVICE_ID>` (prefix is configurable) and JSON fields such as `power_kw`, `power_factor`, `temperature`, `voltage`, `current`, `energy_kwh`, and optional ISO timestamp. The MQTT topic's device ID must match an enabled MongoDB device configured for MQTT and linked to an active machine. Invalid/unregistered/device-mismatched messages are discarded. MongoDB Atlas stores readings; a separate service (for example EMQX) supplies MQTT transport.

The HTTP `demo_iot.py` tool simulates all active machines by posting through FastAPI. The `demo_mqtt.py` tool simulates a single MQTT device. The Admin top-bar Start Demo Meter controls a backend-generated HTTP-style demo loop for active machines. These are separate mechanisms; starting the HTTP demo meter does not start an external MQTT publisher.

The current backend stores telemetry in MongoDB. The UI derives charts, energy analytics, alerts, and reports from stored readings and related documents. Empty ranges or a newly created cluster can legitimately show little/no history until telemetry is generated.

## Trained AI model behavior

The provided handoff contains a trained energy regression model and 37 asset-specific Isolation Forest anomaly model packages. Asset IDs are in the model artifact; a machine must be mapped to its matching asset in Admin → AI Insights. The mapping is stored on its machine document as `ml_asset_id`.

The backend ML adapter:

1. Loads the handoff's model package lazily from `backend/app/ml/`.
2. Reads the machine's telemetry and integrates successive meter deltas (or power readings) into UTC quarter-hour energy windows. Clock reversals and long gaps are ignored rather than filled with guessed energy.
3. Uses only the uninterrupted, completed window tail. The handoff's `lag_96` feature needs 97 consecutive windows (about 24.25 hours including the current window) before a ready analysis is possible.
4. Computes expected energy and an asset-specific anomaly flag/score/severity for the latest available window. Anomaly recommendations are advisory and do not cause machine control.
5. Makes four recursive next-15-minute point estimates for a next-hour outlook. Each step after the first uses earlier predicted values, so error can compound. The model is not providing calibrated confidence bounds; the UI must not describe them as certainty.
6. Marks telemetry stale when the latest reading is older than 30 minutes. Freshness and contiguous-window readiness are different checks.

The Isolation Forest score is a model decision score, not a probability. Potential waste and rupee impact are model-derived estimates, not verified savings. Keep asset mapping, freshness, history length, and estimated-vs-measured labels visible when presenting results.

Model persistence uses joblib/pickle. The pinned scientific Python versions in `backend/requirements.txt` correspond to the handoff environment. Do not load pickle files from unknown or untrusted sources.

## Important routes

The following are a quick index; inspect `http://localhost:8000/docs` for required bodies, response shapes, and authorization details:

- Health: `/health`, `/health/database`, `/health/mqtt`.
- Authentication: `/auth/register`, `/auth/login`, `/auth/me`, `/auth/logout`, `/auth/heartbeat`.
- Overview: `/dashboard/overview`.
- People: `/users`, `/team`.
- Machines and devices: `/machines`, `/devices` and their item routes.
- Telemetry: `POST /telemetry`, `GET /telemetry/latest/{machine_id}`.
- Alerts, tasks, approvals/requests, maintenance: `/alerts`, `/tasks`, `/requests`, `/maintenance`.
- Machine analysis: `/analytics`, `/reports/generate`.
- ML: `/ml/assets`, `/ml/analysis/{machine_id}`, `/recommendations/{machine_id}`.
- Demo meter: `/demo-iot/status`, `/demo-iot/start`, `/demo-iot/stop` (admin protected).

## Change guide

- **Login, sessions, roles:** start with `AuthContext.jsx`, `authService.js`, `Protected.jsx`, then `backend/app/core/security.py` and auth routes in `main.py`.
- **Machine fields and device registration:** update `models.py`, the machine/device routes in `main.py`, corresponding service modules and forms; preserve ID linkage.
- **MQTT input:** inspect `mqtt_ingestion.py` and `MQTT_SETUP.md`; validate topic identity and MongoDB registration before storing.
- **Dashboard or analytics values:** find the UI page and its service, then trace to API aggregation and stored telemetry definitions. Check whether the page is in mock or live mode.
- **AI behavior:** inspect the supplied handoff `ml_inference.py` before changing feature order or assumptions; keep the adapter concerns in `ml_service.py`; expose provenance/data-readiness in API/UI.
- **New route:** validate request data with Pydantic in `models.py`, enforce authentication and role/assignment access in `main.py`, return safe JSON, and wire the frontend through a service.
- **New UI component using shared state:** confirm its route is under `DataProvider`. Components used on `/login` must not assume authenticated data context exists.

## Current prototype limitations

- This is not production-hardened. A local development server, prototype authentication, polling cadence, generated readings, and model estimates do not replace operational security or industrial controls.
- The browser does not currently have a live WebSocket route from this backend; live machine data refreshes by polling.
- MQTT operation requires its own external broker and valid registered devices.
- ML output depends on an appropriate asset mapping and enough continuous telemetry history; synthetic data is suitable for demos only.
- Human review is required for alert response, maintenance and stop/optimization actions. The software must not be presented as an automatic safety system.
