# VoltEdge

VoltEdge is a React and FastAPI prototype for monitoring factory energy use, detecting unusual machine consumption, and coordinating work between operators and administrators. MongoDB Atlas stores users, machines, devices, telemetry, alerts, tasks, approvals, and other app data. MQTT can carry readings from a real or simulated device.

> Demo IoT readings are synthetic. The trained ML models provide estimates and anomaly flags; they are not safety controls and do not automatically stop equipment.

## Repository map

```text
voltedge/
├── frontend/                 React 18 + Vite application
│   └── src/
│       ├── pages/admin/      Admin views
│       ├── pages/operator/   Operator views
│       ├── components/       Shared layout and UI components
│       ├── context/          Authentication, app preferences, shared data
│       ├── services/         API and mock-data access
│       └── engine/           Frontend machine/recommendation helpers
└── backend/                  FastAPI application and Python environment
    ├── app/main.py           Routes, application startup, demo meter
    ├── app/models.py         Pydantic request/response models
    ├── app/core/             MongoDB and authentication setup
    ├── app/mqtt_ingestion.py MQTT subscription and telemetry validation
    ├── app/ml_service.py     Adapter from VoltEdge to the trained models
    ├── app/ml/               Model inference code and trained model files
    ├── demo_iot.py           HTTP API simulator for all active machines
    ├── demo_mqtt.py          MQTT publisher simulator for one registered device
    └── reset_password.py     Local interactive password reset utility
```

For a deeper walkthrough of data flow, roles, collections, and prediction behavior, see [CODEBASE_UNDERSTANDING.md](CODEBASE_UNDERSTANDING.md).

## Requirements

- Windows with Python and Node.js/npm installed.
- A MongoDB Atlas cluster and database user, or another reachable MongoDB deployment.
- For MQTT, an MQTT broker and credentials. MongoDB Atlas is a database; it does not provide the MQTT broker.

## Configure the backend

Open a terminal in `backend` and create the local environment file from the example:

```powershell
Copy-Item .env.example .env
```

Edit `backend/.env` and set `MONGODB_URI`, `MONGODB_DATABASE`, `JWT_SECRET_KEY`, and the initial administrator values. The initial admin password must be at least 12 characters. Keep `.env` private and never paste credentials into source files or commit it.

Install dependencies and start FastAPI (PowerShell):

```powershell
cd C:\Users\ASUS\Downloads\voltedge-fixed\voltedge\backend
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8001
```

If PowerShell blocks virtual-environment activation, run the interpreter directly instead:

```powershell
.\venv\Scripts\python.exe -m pip install -r requirements.txt
.\venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8001
```

The backend is at `http://localhost:8001`; interactive API documentation is at `http://localhost:8001/docs`. Check `http://localhost:8001/health`, `/health/database`, and `/health/mqtt` for service status. The first successful startup creates the initial admin if that ID does not already exist.

## Configure and start the frontend

Open a second terminal in `frontend`:

```powershell
cd C:\Users\ASUS\Downloads\voltedge-fixed\voltedge\frontend
npm install
Copy-Item .env.example .env.local
```

For the full backend-connected app, set these values in `frontend/.env.local`:

```dotenv
VITE_USE_MOCK=false
VITE_USE_LIVE_AUTH=true
VITE_USE_LIVE_MACHINES=true
VITE_API_URL=/api
VITE_WS_URL=
```

The Vite development server proxies `/api` to FastAPI at port 8001. Leave `VITE_WS_URL` empty; the current backend does not expose the frontend WebSocket feed, so live machine views poll the API. Start the frontend:

```powershell
npm run dev
```

Open the local URL Vite prints, usually `http://localhost:5173`. If port 5173 is already in use, Vite may choose another port; use the URL it prints. Vite reads environment variables when it starts, so restart it after changing `.env.local`.

For a frontend-only walkthrough with mock data, set `VITE_USE_MOCK=true` and `VITE_USE_LIVE_AUTH=false`. In that mode, backend login and MongoDB data are not used.

## Demo IoT readings

There are two different simulators:

1. **Start Demo Meter button in the admin top bar** (or the HTTP simulator below) sends generated readings through the local FastAPI app for active machines. It needs the backend and MongoDB; it does not need MQTT.
2. **`demo_mqtt.py`** publishes to your configured MQTT broker. Register an enabled MQTT device in Admin → Devices and link it to an active machine first.

To start the HTTP demo publisher in a third terminal:

```powershell
cd C:\Users\ASUS\Downloads\voltedge-fixed\voltedge\backend
.\venv\Scripts\python.exe demo_iot.py
```

It asks for admin credentials without displaying the password, then publishes simulated readings every five seconds. Stop it with Ctrl+C.

To connect an MQTT broker, copy the **placeholder** MQTT settings from `backend/.env.mqtt.example` into `backend/.env`, then fill them with your own broker host, port, username, and password. Restart FastAPI. `/health/mqtt` should report configured and connected. Do not replace the MongoDB or JWT settings in `.env`.

For MQTT simulation, set `MQTT_DEVICE_ID` in `backend/.env` to an enabled device ID whose protocol is MQTT, then run:

```powershell
cd C:\Users\ASUS\Downloads\voltedge-fixed\voltedge\backend
.\venv\Scripts\python.exe demo_mqtt.py
```

It publishes changing sample readings every five seconds to `voltedge/telemetry/<DEVICE_ID>` by default. Stop it with Ctrl+C. See [backend/MQTT_SETUP.md](backend/MQTT_SETUP.md) for payload and broker details.

## Roles and main features

- **Admin:** manages users, machine assignments, machines, devices, alerts, tasks, approvals, settings, reports, and trained-asset mappings. Admin login sessions are tracked as active and are marked inactive on logout; heartbeats update the session activity.
- **Operator:** sees assigned machines and operational views, reports anomalies, reviews alerts, and works on assigned tasks and requests.
- **Reports and analytics:** use stored MongoDB telemetry when live mode is enabled. Demo or mock mode can show generated sample data.
- **Recommendations:** trained asset-specific anomaly models feed the ML analysis/recommendation flow when the machine is mapped to the correct model asset. Rule-based demo recommendations are separate from trained-model results.

## Trained ML predictions

Model files are loaded from `backend/app/ml/`. The analysis endpoint requires a machine-to-model-asset mapping in Admin → AI Insights. Choose the trained asset that corresponds to that machine; an incorrect mapping makes comparisons unreliable.

The energy model predicts one 15-minute step. VoltEdge derives the next four 15-minute estimates recursively, so each future step uses earlier predicted values. These are estimates, not guaranteed energy usage or calibrated confidence intervals. The Isolation Forest models flag unusual asset-specific patterns. A prediction needs at least 97 consecutive completed 15-minute windows (about 24 hours) for the model's lag features. Sparse or stale telemetry can keep the model warming up or make its output less useful.

Model loading uses joblib/pickle artifacts and the pinned NumPy, pandas, joblib, and scikit-learn versions in `backend/requirements.txt`. Only load model artifacts from a trusted source.

## Important API routes

All routes are served by FastAPI on port 8001. Most data routes require a bearer token; the frontend adds it after login.

| Area | Routes |
|---|---|
| Health | `GET /health`, `GET /health/database`, `GET /health/mqtt` |
| Login and sessions | `POST /auth/login`, `POST /auth/register`, `GET /auth/me`, `POST /auth/logout`, `POST /auth/heartbeat` |
| Dashboard | `GET /dashboard/overview` |
| People and assignments | `GET /users`, `PATCH /users/{employee_id}`, `GET /team` |
| Machines and devices | `/machines`, `/devices` (list/create/update/delete routes) |
| Telemetry | `POST /telemetry`, `GET /telemetry/latest/{machine_id}` |
| Alerts and operations | `/alerts`, `/tasks`, `/requests`, `GET /maintenance` |
| ML | `GET /ml/assets`, `GET /ml/analysis/{machine_id}`, `GET /recommendations/{machine_id}` |
| Analytics and reports | `GET /analytics`, `POST /reports/generate` |
| Demo meter | `GET /demo-iot/status`, `POST /demo-iot/start`, `POST /demo-iot/stop` (admin only) |

See `http://localhost:8001/docs` for request schemas and the complete current route list.

## Common issues

- **`ModuleNotFoundError` starting FastAPI:** activate `backend/venv`, or use `venv\\Scripts\\python.exe` to install requirements and run Uvicorn.
- **MongoDB authentication failure:** verify the Atlas database username/password in `backend/.env`, URL-encode reserved characters in the password, and confirm the computer's IP is allowed by Atlas.
- **`/health/mqtt` says not configured:** set `MQTT_BROKER_HOST` in `backend/.env` and restart FastAPI. If configured but disconnected, confirm broker status, TLS, port, credentials, and network access.
- **MQTT readings are discarded:** check that the device ID in the topic is registered, enabled, configured for MQTT, and linked to an active machine.
- **`vite` is not recognized:** run `npm install` in `frontend`, then `npm run dev` from that same folder.
- **Port 5173 is busy:** open the alternate local URL printed by Vite, or stop the other Vite server.
- **Login fails:** confirm `VITE_USE_LIVE_AUTH=true`, the initial admin ID/password, MongoDB status, and that the frontend restarted after environment changes. Use `backend/reset_password.py` for a local interactive password reset.
- **AI panel says mapping required or building history:** map the machine to its correct trained asset and collect enough consecutive 15-minute telemetry.

## Safety and deployment notes

VoltEdge is a prototype. Recommendations do not actuate machinery. Stop requests require an admin approval path; keep operational decisions with qualified personnel. Before exposing this app beyond local development, add HTTPS, secure secret management, restricted MongoDB and broker network access, broker ACLs, rate limiting, audit and backup policies, and deployment-specific access controls. Never commit `.env` files or paste passwords, JWT secrets, or connection URIs into chat or screenshots.
