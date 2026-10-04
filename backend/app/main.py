import os
import random
import threading
from datetime import date, datetime, time, timedelta, timezone
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from pymongo import ASCENDING, DESCENDING
from pymongo.errors import DuplicateKeyError, PyMongoError

from app.core.database import MONGODB_DATABASE, check_database_connection, database
from app.mqtt_ingestion import mqtt_status, start_mqtt_subscriber, stop_mqtt_subscriber
from app.ml_service import MLServiceUnavailable, analyze_machine as analyze_ml_machine, available_asset_ids, recommendation_from_analysis
from app.core.security import (
    create_access_token,
    get_current_user,
    get_jwt_secret,
    hash_password,
    require_admin,
    verify_password,
)
from app.models import (
    AlertCreate,
    AlertUpdate,
    LoginRequest,
    DeviceCreate,
    DeviceUpdate,
    MachineCreate,
    MachineUpdate,
    PublicUser,
    RegistrationRequest,
    ReportRequest,
    RequestCreate,
    RequestStatusUpdate,
    TaskCreate,
    TaskStatusUpdate,
    TelemetryCreate,
    TokenResponse,
    UserUpdate,
    UserDocument,
)

app = FastAPI(
    title="VoltEdge Backend",
    description="Energy Management and Sustainability Platform",
    version="1.0.0",
)

_demo_iot_stop = threading.Event()
_demo_iot_thread = None
_demo_iot_state = {"active": False, "started_at": None, "last_reading_at": None, "machines": 0, "devices": 0,
                   "readings": 0, "last_error": None,
                   "owner_employee_id": None, "owner_role": None}
_demo_iot_lock = threading.Lock()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def require_database():
    if database is None:
        raise HTTPException(status_code=503, detail="Database is not configured")
    return database


def iso_timestamp(value):
    if value is None:
        return None
    return value.isoformat()


def public_user(user):
    return PublicUser(
        id=user["employee_id"],
        name=user["name"],
        role=user["role"],
        machines=user.get("machines", []),
    )


def seed_initial_admin():
    if database is None:
        return
    employee_id = os.getenv("INITIAL_ADMIN_ID", "").strip().upper()
    name = os.getenv("INITIAL_ADMIN_NAME", "").strip()
    password = os.getenv("INITIAL_ADMIN_PASSWORD", "")
    if not employee_id or not name or len(password) < 12:
        print("Initial admin not seeded: set INITIAL_ADMIN_ID, INITIAL_ADMIN_NAME, and a 12+ character INITIAL_ADMIN_PASSWORD in backend/.env.")
        return
    try:
        users = database["users"]
        users.create_index([("employee_id", ASCENDING)], unique=True)
        if users.find_one({"employee_id": employee_id}):
            return
        document = UserDocument(
            employee_id=employee_id,
            name=name,
            role="admin",
            password_hash=hash_password(password),
            created_at=datetime.now(timezone.utc),
        ).dict()
        users.insert_one(document)
        print(f"Initial admin account created for {employee_id}.")
    except PyMongoError:
        print("Could not initialize the users collection; check the MongoDB connection.")


@app.on_event("startup")
def startup():
    seed_initial_admin()
    start_mqtt_subscriber()


@app.on_event("shutdown")
def shutdown():
    stop_demo_iot()
    stop_mqtt_subscriber()


def _run_demo_iot(db, allowed_machine_ids=None):
    energy_by_device = {}
    energy_by_machine = {}
    allowed_machine_ids = set(allowed_machine_ids) if allowed_machine_ids is not None else None
    while not _demo_iot_stop.is_set():
        try:
            machine_query = {"status": {"$ne": "inactive"}}
            if allowed_machine_ids is not None:
                machine_query["machine_id"] = {"$in": list(allowed_machine_ids)}
            machines = list(db["machines"].find(machine_query))
            machine_by_id = {machine["machine_id"]: machine for machine in machines}
            # Query devices on every cycle so devices registered while the demo is
            # running begin receiving simulated telemetry automatically.
            device_query = {"enabled": {"$ne": False}}
            if allowed_machine_ids is not None:
                device_query["machine_id"] = {"$in": list(allowed_machine_ids)}
            devices = list(db["devices"].find(device_query))
            now = datetime.now(timezone.utc)
            active_device_machines = set()
            sent_devices = 0
            sent_readings = 0

            for device in devices:
                device_id = device.get("device_id")
                machine_id = device.get("machine_id")
                machine = machine_by_id.get(machine_id)
                if not device_id or not machine:
                    continue
                latest = db["telemetry"].find_one({"device_id": device_id}, sort=[("timestamp", DESCENDING)])
                if device_id not in energy_by_device:
                    energy_by_device[device_id] = float((latest or {}).get("energy_kwh", 0) or 0)
                rated = float(machine.get("rated_power", 30) or 30)
                center = max(0.2, min(rated * 0.62, 120))
                power = max(0.1, center * random.uniform(0.88, 1.12))
                energy_by_device[device_id] += power * 5 / 3600
                db["telemetry"].insert_one({
                    "device_id": device_id,
                    "machine_id": machine_id,
                    "power_kw": round(power, 3),
                    "power_factor": round(random.uniform(0.91, 0.99), 3),
                    "temperature": round(random.uniform(43, 61), 1),
                    "voltage": round(random.uniform(228, 234), 1),
                    "current": round(power * 1000 / 230, 2),
                    "energy_kwh": round(energy_by_device[device_id], 5),
                    "source": "demo_iot",
                    "timestamp": now,
                })
                db["devices"].update_one({"device_id": device_id}, {"$set": {"last_seen": now}})
                active_device_machines.add(machine_id)
                sent_devices += 1
                sent_readings += 1

            # Keep machine dashboards useful when a machine has no registered
            # device. Device-linked machines receive exactly their device readings.
            for machine in machines:
                machine_id = machine["machine_id"]
                if machine_id in active_device_machines:
                    continue
                latest = db["telemetry"].find_one({"machine_id": machine_id}, sort=[("timestamp", DESCENDING)])
                if machine_id not in energy_by_machine:
                    energy_by_machine[machine_id] = float((latest or {}).get("energy_kwh", 0) or 0)
                rated = float(machine.get("rated_power", 30) or 30)
                center = max(0.2, min(rated * 0.62, 120))
                power = max(0.1, center * random.uniform(0.88, 1.12))
                energy_by_machine[machine_id] += power * 5 / 3600
                db["telemetry"].insert_one({
                    "machine_id": machine_id,
                    "power_kw": round(power, 3),
                    "power_factor": round(random.uniform(0.91, 0.99), 3),
                    "temperature": round(random.uniform(43, 61), 1),
                    "voltage": round(random.uniform(228, 234), 1),
                    "current": round(power * 1000 / 230, 2),
                    "energy_kwh": round(energy_by_machine[machine_id], 5),
                    "source": "demo_iot",
                    "timestamp": now,
                })
                sent_readings += 1

            with _demo_iot_lock:
                _demo_iot_state.update({
                    "active": True,
                    "last_reading_at": iso_timestamp(now),
                    "machines": len(machines),
                    "devices": sent_devices,
                    "readings": _demo_iot_state.get("readings", 0) + sent_readings,
                    "last_error": None,
                })
        except Exception as exc:
            print(f"Demo IoT reading error: {exc}")
            with _demo_iot_lock:
                _demo_iot_state["last_error"] = str(exc)
        _demo_iot_stop.wait(5)
    with _demo_iot_lock:
        _demo_iot_state["active"] = False
        _demo_iot_state["owner_employee_id"] = None
        _demo_iot_state["owner_role"] = None
        _demo_iot_state["machines"] = 0
        _demo_iot_state["last_reading_at"] = None
        _demo_iot_state["devices"] = 0


def _public_demo_iot_state(user):
    with _demo_iot_lock:
        state = dict(_demo_iot_state)
    state["can_control"] = user.get("role") == "admin" or state.get("owner_employee_id") == user.get("employee_id")
    state.pop("owner_employee_id", None)
    state.pop("owner_role", None)
    return state


def stop_demo_iot():
    global _demo_iot_thread
    _demo_iot_stop.set()
    if _demo_iot_thread and _demo_iot_thread.is_alive():
        _demo_iot_thread.join(timeout=2)
    _demo_iot_thread = None
    with _demo_iot_lock:
        _demo_iot_state["active"] = False


@app.get("/")
def root():
    return {"message": "VoltEdge backend is running"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/health/database")
def database_health():
    return {"status": check_database_connection(), "database": MONGODB_DATABASE}


@app.get("/health/mqtt")
def mqtt_health():
    return mqtt_status()


@app.get("/demo-iot/status")
def demo_iot_status(user=Depends(get_current_user)):
    return _public_demo_iot_state(user)


@app.post("/demo-iot/start")
def demo_iot_start(user=Depends(get_current_user)):
    global _demo_iot_thread
    db = require_database()
    allowed_ids = None if user.get("role") == "admin" else list(dict.fromkeys(user.get("machines", [])))
    machine_query = {"status": {"$ne": "inactive"}}
    if allowed_ids is not None:
        machine_query["machine_id"] = {"$in": allowed_ids}
    machines = list(db["machines"].find(machine_query, {"machine_id": 1}))
    if not machines:
        raise HTTPException(status_code=400, detail="An active machine must be assigned to you before starting the demo meter")
    with _demo_iot_lock:
        if _demo_iot_thread and _demo_iot_thread.is_alive():
            if user.get("role") != "admin" and _demo_iot_state.get("owner_employee_id") != user.get("employee_id"):
                raise HTTPException(status_code=409, detail="The shared demo meter is already running. Ask its owner or an admin to stop it first.")
            return _public_demo_iot_state(user)
        _demo_iot_stop.clear()
        _demo_iot_state.update({"active": True, "started_at": iso_timestamp(datetime.now(timezone.utc)),
                                "last_reading_at": None, "machines": len(machines), "devices": 0,
                                "readings": 0, "last_error": None,
                                "owner_employee_id": user.get("employee_id"), "owner_role": user.get("role")})
        _demo_iot_thread = threading.Thread(target=_run_demo_iot, args=(db, allowed_ids), daemon=True, name="VoltEdgeDemoIoT")
        _demo_iot_thread.start()
        return _public_demo_iot_state(user)


@app.post("/demo-iot/stop")
def demo_iot_stop(user=Depends(get_current_user)):
    with _demo_iot_lock:
        owner_id = _demo_iot_state.get("owner_employee_id")
    if user.get("role") != "admin" and owner_id != user.get("employee_id"):
        raise HTTPException(status_code=403, detail="Only the operator who started this demo meter or an admin can stop it")
    stop_demo_iot()
    return _public_demo_iot_state(user)


@app.get("/dashboard/overview")
def dashboard_overview(
    tariff: float = Query(default=8.5, ge=0, le=1000),
    user=Depends(get_current_user),
):
    """Return a factory summary; operators only receive machines assigned to them."""
    db = require_database()
    now = datetime.now(timezone.utc)
    machines_out, alerts, telemetry_alerts = [], [], []
    try:
        machine_query = {"status": {"$ne": "inactive"}}
        if user["role"] == "operator":
            machine_query["machine_id"] = {"$in": user.get("machines", [])}
        machines = list(db["machines"].find(machine_query).sort("name", ASCENDING))
        for machine in machines:
            mid = machine["machine_id"]
            reading = db["telemetry"].find_one({"machine_id": mid}, sort=[("timestamp", DESCENDING)])
            stamp = reading.get("timestamp") if reading else None
            if stamp and stamp.tzinfo is None:
                stamp = stamp.replace(tzinfo=timezone.utc)
            online = bool(stamp and (now - stamp).total_seconds() < 60)
            kw = float(reading.get("power_kw", 0)) if reading and online else 0.0
            temp = float(reading.get("temperature", machine.get("temperature", 0))) if reading else float(machine.get("temperature", 0))
            pf = float(reading.get("power_factor", machine.get("power_factor", 1))) if reading else float(machine.get("power_factor", 1))
            issues = []
            if online and temp >= 85:
                issues.append(("critical", f"Temperature is {temp:.1f} °C; inspect the machine immediately."))
            elif online and temp > float(machine.get("baseline_temp", temp)) + 5:
                issues.append(("warning", f"Temperature is {temp:.1f} °C, above its usual range."))
            if online and pf < 0.92:
                issues.append(("warning", f"Power factor is {pf:.2f}; target is 0.92 or higher."))
            units = float(machine.get("units_per_hour", 0) or 0)
            baseline = float(machine.get("baseline_kwh_per_unit", 0) or 0)
            if online and units > 0 and baseline > 0 and kw / units > baseline * 1.08:
                issues.append(("warning", "Energy per unit is above its configured baseline."))
            health = "critical" if any(level == "critical" for level, _ in issues) else "attention" if issues else "normal"
            for idx, (level, text_value) in enumerate(issues):
                detected = {
                    "id": f"{mid}-{idx}", "machine_id": mid,
                    "machine_name": machine.get("name", mid),
                    "severity": level, "txt": text_value, "source": "telemetry",
                    "created_at": iso_timestamp(stamp),
                }
                alerts.append(detected)
                telemetry_alerts.append(detected)
            machines_out.append({
                "machine_id": mid, "name": machine.get("name", mid),
                "machine_type": machine.get("machine_type", "Other"),
                "status": machine.get("status", "active"), "online": online,
                "power_kw": round(kw, 3), "rated_power": machine.get("rated_power", 0),
                "temperature": round(temp, 1), "power_factor": round(pf, 3),
                "health": health, "last_reading_at": iso_timestamp(stamp),
                "operational_constraint": machine.get("operational_constraint"),
            })
        report_query = {"status": {"$ne": "Resolved"}}
        if user["role"] == "operator":
            report_query["machine_id"] = {"$in": user.get("machines", [])}
        open_reports = list(db["alerts"].find(report_query).sort("created_at", DESCENDING).limit(50))
        for report in open_reports:
            machine = next((item for item in machines_out if item["machine_id"] == report["machine_id"]), None)
            alerts.append({
                "id": report["alert_id"], "machine_id": report["machine_id"],
                "machine_name": machine["name"] if machine else report.get("machine_name", report["machine_id"]),
                "severity": report["severity"], "txt": report["message"],
                "source": "operator", "status": report["status"],
                "reported_by": report["reported_by"], "reported_by_name": report["reported_by_name"],
                "assigned_to": report.get("assigned_to"),
            })
        alerts.sort(key=lambda item: 0 if item["severity"] == "critical" else 1)
        current_demand = sum(item["power_kw"] for item in machines_out)
        return {
            "generated_at": iso_timestamp(now), "source": "mongodb",
            "metrics": {
                "current_demand_kw": round(current_demand, 3),
                "estimated_cost_per_hour": round(current_demand * tariff, 2),
                "online_machines": sum(1 for item in machines_out if item["online"]),
                "machine_count": len(machines_out),
                "critical_issues": sum(1 for item in alerts if item["severity"] == "critical"),
                "open_alerts": len(alerts),
                "improvement_ideas": sum(1 for item in alerts if item["severity"] == "warning"),
            },
            "machines": machines_out, "alerts": alerts[:10], "telemetry_alerts": telemetry_alerts[:10],
        }
    except PyMongoError:
        raise HTTPException(status_code=503, detail="Could not reach the database")


@app.get("/alerts")
def list_alerts(user=Depends(get_current_user)):
    db = require_database()
    try:
        if user["role"] == "admin":
            live = dashboard_overview(8.5, user)["telemetry_alerts"]
            reports = list(db["alerts"].find().sort("created_at", DESCENDING).limit(100))
        else:
            live = []
            reports = list(db["alerts"].find({"$or": [
                {"reported_by": user["employee_id"]}, {"assigned_to": user["employee_id"]},
            ]}).sort("created_at", DESCENDING).limit(100))
        output = [{
            "id": item["id"], "m": item["machine_id"], "machine_name": item["machine_name"],
            "s": "bad" if item["severity"] == "critical" else "warn", "severity": item["severity"],
            "txt": item["txt"], "pr": 0 if item["severity"] == "critical" else 1,
            "source": "Telemetry detection", "status": "Detected", "reported_by": None,
            "reported_by_name": None, "assigned_to": None, "created_at": item.get("created_at"),
        } for item in live if item.get("source") == "telemetry"]
        for item in reports:
            machine = db["machines"].find_one({"machine_id": item["machine_id"]}, {"name": 1})
            output.append({
                "id": item["alert_id"], "m": item["machine_id"],
                "machine_name": machine.get("name", item["machine_id"]) if machine else item["machine_id"],
                "s": "bad" if item["severity"] == "critical" else "warn", "severity": item["severity"],
                "txt": item["message"], "pr": 0 if item["severity"] == "critical" else 1,
                "source": "Operator report", "status": item["status"],
                "reported_by": item["reported_by"], "reported_by_name": item["reported_by_name"],
                "assigned_to": item.get("assigned_to"), "assigned_to_name": item.get("assigned_to_name"),
                "rule_id": item["rule_id"], "occurrences": item.get("occurrences", 1),
                "created_at": iso_timestamp(item.get("created_at")),
                "last_detected_at": iso_timestamp(item.get("last_detected_at")),
                "reading": item.get("latest_reading", {}),
            })
        return sorted(output, key=lambda item: (item["pr"], item.get("created_at") or ""), reverse=False)
    except PyMongoError:
        raise HTTPException(status_code=503, detail="Could not reach the database")


@app.post("/alerts", status_code=status.HTTP_201_CREATED)
def create_alert(report: AlertCreate, user=Depends(get_current_user)):
    if user["role"] != "operator":
        raise HTTPException(status_code=403, detail="Only operators can send an anomaly report")
    if report.machine_id not in user.get("machines", []):
        raise HTTPException(status_code=403, detail="You can only report anomalies for a machine assigned to you")
    db = require_database()
    try:
        machine = db["machines"].find_one({"machine_id": report.machine_id, "status": {"$ne": "inactive"}})
        if machine is None:
            raise HTTPException(status_code=404, detail="Active machine not found")
        alerts = db["alerts"]
        alerts.create_index("alert_id", unique=True)
        open_item = alerts.find_one({
            "machine_id": report.machine_id, "rule_id": report.rule_id,
            "reported_by": user["employee_id"], "status": {"$ne": "Resolved"},
        })
        now = datetime.now(timezone.utc)
        if open_item:
            alerts.update_one({"alert_id": open_item["alert_id"]}, {"$set": {
                "last_detected_at": now, "latest_reading": report.reading,
                "message": report.message, "severity": report.severity,
            }, "$inc": {"occurrences": 1}})
            result = alerts.find_one({"alert_id": open_item["alert_id"]})
        else:
            result = {
                "alert_id": "A-" + uuid4().hex[:12].upper(), "machine_id": report.machine_id,
                "machine_name": machine.get("name", report.machine_id), "rule_id": report.rule_id,
                "title": report.title.strip(), "message": report.message.strip(),
                "severity": report.severity, "status": "Open", "reported_by": user["employee_id"],
                "reported_by_name": user["name"], "assigned_to": None, "assigned_to_name": None,
                "latest_reading": report.reading, "occurrences": 1,
                "created_at": now, "last_detected_at": now,
            }
            alerts.insert_one(result)
        return {"id": result["alert_id"], "status": result["status"], "occurrences": result["occurrences"]}
    except HTTPException:
        raise
    except PyMongoError:
        raise HTTPException(status_code=503, detail="Could not save anomaly report")


@app.patch("/alerts/{alert_id}")
def update_alert(alert_id: str, updates: AlertUpdate, admin=Depends(require_admin)):
    values = updates.dict(exclude_unset=True)
    if not values:
        raise HTTPException(status_code=400, detail="Provide an alert status or operator assignment")
    db = require_database()
    try:
        alert = db["alerts"].find_one({"alert_id": alert_id})
        if alert is None:
            raise HTTPException(status_code=404, detail="Saved operator alert not found")
        assigned_id = values.get("assigned_to")
        if assigned_id:
            assigned_id = assigned_id.strip().upper()
            operator = db["users"].find_one({"employee_id": assigned_id, "active": True, "role": "operator"})
            if operator is None:
                raise HTTPException(status_code=404, detail="Active operator not found")
            if alert["machine_id"] not in operator.get("machines", []):
                raise HTTPException(status_code=400, detail="Assign this machine to the operator first in People")
            values["assigned_to"] = assigned_id
            values["assigned_to_name"] = operator["name"]
        elif "assigned_to" in values:
            values["assigned_to_name"] = None
        values["updated_at"] = datetime.now(timezone.utc)
        db["alerts"].update_one({"alert_id": alert_id}, {"$set": values})
        return {"id": alert_id, **{key: value for key, value in values.items() if key != "updated_at"}}
    except HTTPException:
        raise
    except PyMongoError:
        raise HTTPException(status_code=503, detail="Could not update anomaly report")


@app.post("/auth/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(credentials: RegistrationRequest):
    get_jwt_secret()
    employee_id = credentials.employeeId.strip().upper()
    reserved_admin_id = os.getenv("INITIAL_ADMIN_ID", "").strip().upper()
    if reserved_admin_id and employee_id == reserved_admin_id:
        raise HTTPException(status_code=409, detail="This ID is reserved for the initial administrator")
    users = require_database()["users"]
    try:
        users.create_index([("employee_id", ASCENDING)], unique=True)
        document = UserDocument(
            employee_id=employee_id,
            name=credentials.name.strip(),
            role="operator",
            password_hash=hash_password(credentials.password),
            created_at=datetime.now(timezone.utc),
        ).dict()
        users.insert_one(document)
        now = datetime.now(timezone.utc)
        users.update_one({"employee_id": employee_id}, {"$set": {"session_active": True, "last_login_at": now, "last_seen_at": now}})
    except DuplicateKeyError:
        raise HTTPException(status_code=409, detail="This employee ID is already registered")
    except PyMongoError:
        raise HTTPException(status_code=503, detail="Could not reach the database")
    user = public_user(document)
    return {"token": create_access_token(employee_id), "user": user}


@app.post("/auth/login", response_model=TokenResponse)
def login(credentials: LoginRequest):
    employee_id = credentials.employeeId.strip().upper()
    try:
        user = require_database()["users"].find_one(
            {"employee_id": employee_id, "active": True}
        )
    except PyMongoError:
        raise HTTPException(status_code=503, detail="Could not reach the database")
    if user is None or not verify_password(credentials.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid employee ID or password")
    if credentials.role and credentials.role != user["role"]:
        raise HTTPException(
            status_code=403,
            detail=f"This account is registered as {user['role']}. Choose {user['role']} login.",
        )
    now = datetime.now(timezone.utc)
    require_database()["users"].update_one(
        {"employee_id": employee_id},
        {"$set": {"session_active": True, "last_login_at": now, "last_seen_at": now}},
    )
    return {"token": create_access_token(employee_id), "user": public_user(user)}


@app.get("/auth/me", response_model=PublicUser)
def auth_me(user=Depends(get_current_user)):
    return public_user(user)


@app.post("/auth/logout")
def auth_logout(user=Depends(get_current_user)):
    require_database()["users"].update_one(
        {"employee_id": user["employee_id"]},
        {"$set": {"session_active": False, "last_logout_at": datetime.now(timezone.utc)}},
    )
    return {"status": "logged_out"}


@app.post("/auth/heartbeat")
def auth_heartbeat(user=Depends(get_current_user)):
    now = datetime.now(timezone.utc)
    require_database()["users"].update_one(
        {"employee_id": user["employee_id"]},
        {"$set": {"session_active": True, "last_seen_at": now}},
    )
    return {"status": "active", "last_seen_at": iso_timestamp(now)}


@app.get("/users")
def list_users(_admin=Depends(require_admin)):
    try:
        users = list(require_database()["users"].find({}, {"password_hash": 0}).sort("name", ASCENDING))
        return [{
            "id": u["employee_id"], "name": u["name"], "role": u["role"],
            "machines": u.get("machines", []),
            "sessionActive": bool(u.get("session_active", False) and u.get("last_seen_at") and
                                   (datetime.now(timezone.utc) - (u["last_seen_at"].replace(tzinfo=timezone.utc) if u["last_seen_at"].tzinfo is None else u["last_seen_at"])).total_seconds() < 75),
            "active": bool(u.get("active", True)),
            "lastLoginAt": iso_timestamp(u.get("last_login_at")),
        } for u in users]
    except PyMongoError:
        raise HTTPException(status_code=503, detail="Could not reach the database")


@app.patch("/users/{employee_id}")
def update_user(employee_id: str, updates: UserUpdate, admin=Depends(require_admin)):
    target_id = employee_id.strip().upper()
    if target_id == admin["employee_id"] and updates.role and updates.role != "admin":
        raise HTTPException(status_code=400, detail="You cannot change your own role")
    values = updates.dict(exclude_unset=True, exclude_none=True)
    if "name" in values:
        values["name"] = values["name"].strip()
        if not values["name"]:
            raise HTTPException(status_code=422, detail="Employee name cannot be blank")
    if "machines" in values:
        values["machines"] = list(dict.fromkeys(values["machines"]))
    if not values:
        raise HTTPException(status_code=400, detail="Provide a name, role, or machine assignment")
    try:
        db = require_database()
        if "machines" in values:
            for machine_id in values["machines"]:
                if not db["machines"].find_one({"machine_id": machine_id, "status": {"$ne": "inactive"}}):
                    raise HTTPException(status_code=404, detail=f"Active machine {machine_id} not found")
        result = db["users"].update_one({"employee_id": target_id}, {"$set": values})
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Employee not found")
        return {"id": target_id, **values}
    except HTTPException:
        raise
    except PyMongoError:
        raise HTTPException(status_code=503, detail="Could not reach the database")


@app.get("/team")
def list_operator_team(user=Depends(get_current_user)):
    if user["role"] != "operator":
        raise HTTPException(status_code=403, detail="Team view is available to operators")
    shared_machines = user.get("machines", [])
    if not shared_machines:
        return []
    try:
        members = list(require_database()["users"].find(
            {"active": True, "machines": {"$in": shared_machines}},
            {"password_hash": 0},
        ).sort("name", ASCENDING))
        return [{
            "id": member["employee_id"], "name": member["name"], "role": member["role"],
            "machines": [machine_id for machine_id in member.get("machines", []) if machine_id in shared_machines],
            "sessionActive": bool(member.get("session_active", False)),
        } for member in members]
    except PyMongoError:
        raise HTTPException(status_code=503, detail="Could not load your machine team")


@app.get("/requests")
def list_requests(user=Depends(get_current_user)):
    query = {} if user["role"] == "admin" else {"by": user["employee_id"]}
    try:
        requests = list(require_database()["requests"].find(query).sort("created_at", DESCENDING).limit(200))
        return [{
            "id": item["request_id"], "m": item["m"], "by": item["by"], "type": item["type"],
            "reason": item["reason"], "obs": item.get("obs", []), "fb": item.get("fb", ""),
            "acts": item.get("acts", []), "status": item["status"], "log": item.get("log", []),
            "created_at": iso_timestamp(item.get("created_at")),
        } for item in requests]
    except PyMongoError:
        raise HTTPException(status_code=503, detail="Could not load approval requests")


@app.post("/requests", status_code=status.HTTP_201_CREATED)
def create_request(request: RequestCreate, user=Depends(get_current_user)):
    if user["role"] != "operator":
        raise HTTPException(status_code=403, detail="Only operators can submit approval requests")
    if request.m not in user.get("machines", []):
        raise HTTPException(status_code=403, detail="You can only submit requests for machines assigned to you")
    db = require_database()
    try:
        machine = db["machines"].find_one({"machine_id": request.m, "status": {"$ne": "inactive"}})
        if machine is None:
            raise HTTPException(status_code=404, detail="Active machine not found")
        now = datetime.now(timezone.utc)
        document = {
            "request_id": "R-" + uuid4().hex[:10].upper(), "m": request.m,
            "by": user["employee_id"], "type": request.type, "reason": request.reason.strip(),
            "obs": request.obs, "fb": request.fb.strip(), "acts": request.acts,
            "status": "Pending", "log": [f"Pending · {user['name']}"],
            "created_at": now, "updated_at": now,
        }
        db["requests"].insert_one(document)
        return {key: value for key, value in document.items() if key != "_id"}
    except HTTPException:
        raise
    except PyMongoError:
        raise HTTPException(status_code=503, detail="Could not save approval request")


@app.patch("/requests/{request_id}")
def update_request_status(request_id: str, updates: RequestStatusUpdate, admin=Depends(require_admin)):
    db = require_database()
    try:
        request = db["requests"].find_one({"request_id": request_id})
        if request is None:
            raise HTTPException(status_code=404, detail="Approval request not found")
        now = datetime.now(timezone.utc)
        db["requests"].update_one({"request_id": request_id}, {
            "$set": {"status": updates.status, "updated_at": now},
            "$push": {"log": f"{updates.status} · {admin['name']}"},
        })
        return {"id": request_id, "status": updates.status}
    except HTTPException:
        raise
    except PyMongoError:
        raise HTTPException(status_code=503, detail="Could not update approval request")


def public_task(task, db):
    task_id = task["task_id"]
    operator = db["users"].find_one({"employee_id": task["assigned_to"]}, {"name": 1})
    machine = db["machines"].find_one({"machine_id": task["machine_id"]}, {"name": 1})
    return {
        "id": task_id, "title": task["title"], "description": task.get("description", ""),
        "machine_id": task["machine_id"], "machine_name": machine.get("name", task["machine_id"]) if machine else task["machine_id"],
        "assigned_to": task["assigned_to"], "assigned_to_name": operator.get("name", task["assigned_to"]) if operator else task["assigned_to"],
        "assigned_by": task["assigned_by"], "status": task["status"],
        "due_date": task["due_date"].isoformat() if hasattr(task.get("due_date"), "isoformat") else task.get("due_date"),
        "created_at": iso_timestamp(task.get("created_at")),
    }


@app.get("/tasks")
def list_tasks(user=Depends(get_current_user)):
    db = require_database()
    query = {} if user["role"] == "admin" else {"assigned_to": user["employee_id"]}
    try:
        tasks = list(db["tasks"].find(query).sort("created_at", DESCENDING))
        return [public_task(task, db) for task in tasks]
    except PyMongoError:
        raise HTTPException(status_code=503, detail="Could not reach the database")


@app.post("/tasks", status_code=status.HTTP_201_CREATED)
def create_task(task: TaskCreate, admin=Depends(require_admin)):
    db = require_database()
    machine_id, employee_id = task.machine_id.strip(), task.assigned_to.strip().upper()
    try:
        machine = db["machines"].find_one({"machine_id": machine_id, "status": {"$ne": "inactive"}})
        if machine is None:
            raise HTTPException(status_code=404, detail="Active machine not found")
        operator = db["users"].find_one({"employee_id": employee_id, "active": True, "role": "operator"})
        if operator is None:
            raise HTTPException(status_code=404, detail="Registered operator not found")
        if machine_id not in operator.get("machines", []):
            db["users"].update_one(
                {"employee_id": employee_id},
                {"$addToSet": {"machines": machine_id}},
            )
        document = {
            "task_id": "T-" + uuid4().hex[:10].upper(), "title": task.title.strip(),
            "description": task.description.strip(), "machine_id": machine_id,
            "assigned_to": employee_id, "assigned_by": admin["employee_id"],
            "status": "Pending", "due_date": task.due_date.isoformat() if task.due_date else None,
            "created_at": datetime.now(timezone.utc),
        }
        db["tasks"].insert_one(document)
        return public_task(document, db)
    except HTTPException:
        raise
    except PyMongoError:
        raise HTTPException(status_code=503, detail="Could not reach the database")


@app.patch("/tasks/{task_id}")
def update_task(task_id: str, updates: TaskStatusUpdate, user=Depends(get_current_user)):
    db = require_database()
    try:
        query = {"task_id": task_id}
        task = db["tasks"].find_one(query)
        if task is None:
            raise HTTPException(status_code=404, detail="Task not found")
        if user["role"] != "admin" and task["assigned_to"] != user["employee_id"]:
            raise HTTPException(status_code=403, detail="This task is assigned to another operator")
        db["tasks"].update_one(query, {"$set": {"status": updates.status, "updated_at": datetime.now(timezone.utc)}})
        return public_task(db["tasks"].find_one(query), db)
    except HTTPException:
        raise
    except PyMongoError:
        raise HTTPException(status_code=503, detail="Could not reach the database")


@app.post("/machines", status_code=status.HTTP_201_CREATED)
def create_machine(machine: MachineCreate, _admin=Depends(require_admin)):
    collection = require_database()["machines"]
    try:
        collection.create_index("machine_id", unique=True)
        document = machine.dict(exclude_none=True)
        document["machine_id"] = document.get("machine_id") or "M-" + uuid4().hex[:10]
        document["created_at"] = datetime.now(timezone.utc)
        result = collection.insert_one(document)
        document["_id"] = str(result.inserted_id)
        document["created_at"] = iso_timestamp(document["created_at"])
        return document
    except DuplicateKeyError:
        raise HTTPException(status_code=409, detail="A machine with this machine_id already exists")
    except PyMongoError:
        raise HTTPException(status_code=503, detail="Could not reach the database")


@app.get("/machines")
def list_machines(user=Depends(get_current_user)):
    db = require_database()
    try:
        query = {"status": {"$ne": "inactive"}}
        if user["role"] != "admin":
            query["machine_id"] = {"$in": user.get("machines", [])}
        machines = list(db["machines"].find(query).sort("created_at", DESCENDING))
        for machine in machines:
            machine["_id"] = str(machine["_id"])
            machine["created_at"] = iso_timestamp(machine.get("created_at"))
            reading = db["telemetry"].find_one(
                {"machine_id": machine["machine_id"]}, sort=[("timestamp", DESCENDING)]
            )
            if reading:
                machine["power"] = reading["power_kw"]
                machine["power_factor"] = reading["power_factor"]
                machine["temperature"] = reading["temperature"]
                machine["voltage"] = reading.get("voltage")
                machine["current"] = reading.get("current")
                machine["energy"] = reading.get("energy_kwh")
                machine["last_reading_at"] = iso_timestamp(reading["timestamp"])
        return machines
    except PyMongoError:
        raise HTTPException(status_code=503, detail="Could not reach the database")


@app.get("/machines/{machine_id}")
def get_machine(machine_id: str, user=Depends(get_current_user)):
    try:
        if user["role"] != "admin" and machine_id not in user.get("machines", []):
            raise HTTPException(status_code=403, detail="This machine is not assigned to you")
        machine = require_database()["machines"].find_one({"machine_id": machine_id})
        if machine is None:
            raise HTTPException(status_code=404, detail="Machine not found")
        machine["_id"] = str(machine["_id"])
        machine["created_at"] = iso_timestamp(machine.get("created_at"))
        reading = require_database()["telemetry"].find_one(
            {"machine_id": machine_id}, sort=[("timestamp", DESCENDING)]
        )
        if reading:
            machine.update({
                "power": reading.get("power_kw"), "power_factor": reading.get("power_factor"),
                "temperature": reading.get("temperature"), "energy": reading.get("energy_kwh"),
                "voltage": reading.get("voltage"), "current": reading.get("current"),
                "last_reading_at": iso_timestamp(reading.get("timestamp")),
            })
        return machine
    except HTTPException:
        raise
    except PyMongoError:
        raise HTTPException(status_code=503, detail="Could not reach the database")


@app.patch("/machines/{machine_id}")
def update_machine(machine_id: str, updates: MachineUpdate, _admin=Depends(require_admin)):
    db = require_database()
    values = updates.dict(exclude_unset=True, exclude_none=True)
    if not values:
        raise HTTPException(status_code=400, detail="Provide at least one machine field to update")
    try:
        result = db["machines"].update_one({"machine_id": machine_id}, {"$set": values})
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Machine not found")
        machine = db["machines"].find_one({"machine_id": machine_id})
        machine["_id"] = str(machine["_id"])
        machine["created_at"] = iso_timestamp(machine.get("created_at"))
        return machine
    except HTTPException:
        raise
    except PyMongoError:
        raise HTTPException(status_code=503, detail="Could not reach the database")


@app.delete("/machines/{machine_id}")
def deactivate_machine(machine_id: str, _admin=Depends(require_admin)):
    try:
        result = require_database()["machines"].update_one(
            {"machine_id": machine_id}, {"$set": {"status": "inactive"}}
        )
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Machine not found")
        return {"machine_id": machine_id, "status": "inactive"}
    except HTTPException:
        raise
    except PyMongoError:
        raise HTTPException(status_code=503, detail="Could not reach the database")


def device_document(device, db):
    device["_id"] = str(device["_id"])
    last = db["telemetry"].find_one(
        {"device_id": device["device_id"]}, sort=[("timestamp", DESCENDING)]
    )
    last_seen = last.get("timestamp") if last else None
    if last_seen and last_seen.tzinfo is None:
        last_seen = last_seen.replace(tzinfo=timezone.utc)
    fresh = bool(last_seen and (datetime.now(timezone.utc) - last_seen).total_seconds() < 60)
    demo_stopped = bool(last and last.get("source") == "demo_iot" and not _demo_iot_state.get("active"))
    connected = fresh and not demo_stopped
    device.update({
        "status": "Disabled" if not device.get("enabled", True) else "Connected" if connected else "Offline",
        "last_seen": iso_timestamp(last_seen),
    })
    machine = db["machines"].find_one({"machine_id": device["machine_id"]}, {"name": 1, "status": 1})
    device["machine_name"] = machine.get("name", device["machine_id"]) if machine else device["machine_id"]
    if machine and machine.get("status") == "inactive":
        device["status"] = "Machine inactive"
    return device


@app.get("/devices")
def list_devices(user=Depends(get_current_user)):
    db = require_database()
    try:
        query = {} if user["role"] == "admin" else {"machine_id": {"$in": user.get("machines", [])}}
        devices = list(db["devices"].find(query).sort("created_at", DESCENDING))
        return [device_document(device, db) for device in devices]
    except PyMongoError:
        raise HTTPException(status_code=503, detail="Could not reach the database")


@app.post("/devices", status_code=status.HTTP_201_CREATED)
def create_device(device: DeviceCreate, _admin=Depends(require_admin)):
    db = require_database()
    device_id = device.device_id.strip()
    machine_id = device.machine_id.strip()
    try:
        if not db["machines"].find_one({"machine_id": machine_id, "status": {"$ne": "inactive"}}):
            raise HTTPException(status_code=404, detail="Choose an active machine")
        devices = db["devices"]
        devices.create_index("device_id", unique=True)
        document = {
            "device_id": device_id, "machine_id": machine_id,
            "name": device.name.strip(), "protocol": device.protocol.strip(),
            "enabled": True, "created_at": datetime.now(timezone.utc),
        }
        result = devices.insert_one(document)
        document["_id"] = result.inserted_id
        return device_document(document, db)
    except DuplicateKeyError:
        raise HTTPException(status_code=409, detail="That device ID is already registered")
    except HTTPException:
        raise
    except PyMongoError:
        raise HTTPException(status_code=503, detail="Could not reach the database")


@app.patch("/devices/{device_id}")
def update_device(device_id: str, updates: DeviceUpdate, _admin=Depends(require_admin)):
    db = require_database()
    values = updates.dict(exclude_unset=True, exclude_none=True)
    if not values:
        raise HTTPException(status_code=400, detail="Provide at least one device field to update")
    if "machine_id" in values and not db["machines"].find_one(
        {"machine_id": values["machine_id"], "status": {"$ne": "inactive"}}
    ):
        raise HTTPException(status_code=404, detail="Choose an active machine")
    try:
        result = db["devices"].update_one({"device_id": device_id}, {"$set": values})
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Device not found")
        device = db["devices"].find_one({"device_id": device_id})
        return device_document(device, db)
    except HTTPException:
        raise
    except PyMongoError:
        raise HTTPException(status_code=503, detail="Could not reach the database")


@app.delete("/devices/{device_id}")
def delete_device(device_id: str, _admin=Depends(require_admin)):
    try:
        result = require_database()["devices"].delete_one({"device_id": device_id})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Device not found")
        return {"device_id": device_id, "status": "unregistered"}
    except HTTPException:
        raise
    except PyMongoError:
        raise HTTPException(status_code=503, detail="Could not reach the database")


@app.get("/maintenance")
def list_maintenance(user=Depends(get_current_user)):
    db = require_database()
    query = {"status": {"$ne": "inactive"}}
    if user["role"] != "admin":
        query["machine_id"] = {"$in": user.get("machines", [])}
    try:
        machines = list(db["machines"].find(query).sort("name", ASCENDING))
        return [{
            "machine_id": machine["machine_id"], "machine_name": machine.get("name", machine["machine_id"]),
            "status": machine.get("maintenance_status", "Not scheduled"),
            "next_due": iso_timestamp(machine.get("next_maintenance_at")) if isinstance(machine.get("next_maintenance_at"), datetime) else machine.get("next_maintenance_at"),
            "notes": machine.get("maintenance_notes", ""),
        } for machine in machines]
    except PyMongoError:
        raise HTTPException(status_code=503, detail="Could not reach the database")


@app.post("/telemetry", status_code=status.HTTP_201_CREATED)
def create_telemetry(reading: TelemetryCreate, _user=Depends(get_current_user)):
    if _user.get("role") != "admin" and reading.machine_id not in _user.get("machines", []):
        raise HTTPException(status_code=403, detail="This machine is not assigned to you")
    db = require_database()
    try:
        machine = db["machines"].find_one({"machine_id": reading.machine_id, "status": {"$ne": "inactive"}})
        if machine is None:
            raise HTTPException(status_code=404, detail="Active machine not found")
        if reading.device_id:
            device = db["devices"].find_one({"device_id": reading.device_id, "machine_id": reading.machine_id, "enabled": True})
            if device is None:
                raise HTTPException(status_code=404, detail="Device is not registered to this machine")
        timestamp = reading.timestamp or datetime.now(timezone.utc)
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        document = reading.dict(exclude_none=True)
        document["timestamp"] = timestamp
        db["telemetry"].create_index([("machine_id", ASCENDING), ("timestamp", DESCENDING)])
        result = db["telemetry"].insert_one(document)
        if reading.device_id:
            db["devices"].update_one({"device_id": reading.device_id}, {"$set": {"last_seen": timestamp}})
        document["_id"] = str(result.inserted_id)
        document["timestamp"] = iso_timestamp(timestamp)
        return document
    except HTTPException:
        raise
    except PyMongoError:
        raise HTTPException(status_code=503, detail="Could not reach the database")


@app.get("/telemetry/latest/{machine_id}")
def latest_telemetry(machine_id: str, user=Depends(get_current_user)):
    db = require_database()
    try:
        if user["role"] != "admin" and machine_id not in user.get("machines", []):
            raise HTTPException(status_code=403, detail="This machine is not assigned to you")
        reading = db["telemetry"].find_one(
            {"machine_id": machine_id}, sort=[("timestamp", DESCENDING)]
        )
        if reading is None:
            raise HTTPException(status_code=404, detail="No readings found for this machine")
        reading["_id"] = str(reading["_id"])
        reading["timestamp"] = iso_timestamp(reading["timestamp"])
        return reading
    except HTTPException:
        raise
    except PyMongoError:
        raise HTTPException(status_code=503, detail="Could not reach the database")


@app.get("/ml/assets")
def ml_assets(_admin=Depends(require_admin)):
    try:
        return {"assets": available_asset_ids()}
    except MLServiceUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc))


def _machine_ml_analysis(machine_id, user, tariff=8.0):
    db = require_database()
    if user["role"] != "admin" and machine_id not in user.get("machines", []):
        raise HTTPException(status_code=403, detail="This machine is not assigned to you")
    machine = db["machines"].find_one({"machine_id": machine_id, "status": {"$ne": "inactive"}})
    if machine is None:
        raise HTTPException(status_code=404, detail="Active machine not found")
    try:
        return analyze_ml_machine(db, machine, tariff_rupees_per_kwh=tariff)
    except MLServiceUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@app.get("/ml/analysis/{machine_id}")
def ml_analysis(machine_id: str, tariff: float = Query(default=8.0, ge=0, le=1000), user=Depends(get_current_user)):
    return _machine_ml_analysis(machine_id, user, tariff)


@app.get("/recommendations/{machine_id}")
def machine_recommendations(machine_id: str, tariff: float = Query(default=8.5, ge=0, le=1000), user=Depends(get_current_user)):
    analysis = _machine_ml_analysis(machine_id, user, tariff)
    return recommendation_from_analysis(analysis)


@app.post("/recommendations/{recommendation_id}/feedback")
def recommendation_feedback(recommendation_id: str, payload: dict, user=Depends(get_current_user)):
    value = payload.get("value")
    if value not in {"up", "dn", ""}:
        raise HTTPException(status_code=422, detail="Feedback value must be up, dn, or empty")
    db = require_database()
    query = {"recommendation_id": recommendation_id, "employee_id": user["employee_id"]}
    if not value:
        db["recommendation_feedback"].delete_one(query)
        return {"saved": False}
    db["recommendation_feedback"].update_one(
        query,
        {"$set": {**query, "value": value, "updated_at": datetime.now(timezone.utc)}},
        upsert=True,
    )
    return {"saved": True, "value": value}


@app.get("/analytics")
def analytics(
    rg: str = "7D",
    from_date: str = Query(default="", alias="from"),
    to_date: str = Query(default="", alias="to"),
    machines: str = "",
    user=Depends(get_current_user),
):
    db = require_database()
    now = datetime.now(timezone.utc)
    if rg == "1Y":
        month_start = date(now.year, now.month, 1)
        first = month_start
        for _ in range(11):
            first = date(first.year - (first.month == 1), 12 if first.month == 1 else first.month - 1, 1)
        last = (month_start.replace(day=28) + timedelta(days=4)).replace(day=1)
        starts = []
        cursor = first
        while cursor < last:
            starts.append(datetime.combine(cursor, time.min, tzinfo=timezone.utc))
            nxt = (cursor.replace(day=28) + timedelta(days=4)).replace(day=1)
            cursor = nxt
        ends = starts[1:] + [datetime.combine(last, time.min, tzinfo=timezone.utc)]
        labels = [start.strftime("%b") for start in starts]
        mode = "month"
    elif rg == "Today":
        today = now.date()
        start = datetime.combine(today, time.min, tzinfo=timezone.utc)
        starts = [start + timedelta(hours=i) for i in range(24)]
        ends = starts[1:] + [start + timedelta(days=1)]
        labels = [f"{hour:02d}h" for hour in range(24)]
        mode = "hour"
    else:
        first, last, _, _ = report_window({"rg": rg, "from": from_date, "to": to_date})
        count = min((last - first).days + 1, 366)
        if count < 1:
            raise HTTPException(status_code=422, detail="Choose a valid date range")
        if (last - first).days + 1 > 366:
            raise HTTPException(status_code=422, detail="Choose a date range shorter than one year")
        starts = [datetime.combine(first + timedelta(days=i), time.min, tzinfo=timezone.utc) for i in range(count)]
        ends = starts[1:] + [starts[-1] + timedelta(days=1)]
        labels = [f"{(first + timedelta(days=i)).day}/{(first + timedelta(days=i)).month}" for i in range(count)]
        mode = "day"
    ids = [value for value in machines.split(",") if value]
    if user["role"] != "admin":
        assigned = user.get("machines", [])
        if ids and any(machine_id not in assigned for machine_id in ids):
            raise HTTPException(status_code=403, detail="Analytics may only include your assigned machines")
        ids = ids or assigned
    query = {"status": {"$ne": "inactive"}}
    if ids:
        query["machine_id"] = {"$in": ids}
    try:
        machine_docs = list(db["machines"].find(query).sort("name", ASCENDING))
        totals_energy = [0.0] * len(starts)
        totals_eff, machine_series = [[] for _ in starts], []
        for machine in machine_docs:
            mid = machine["machine_id"]
            first_start, last_end = starts[0], ends[-1]
            previous = db["telemetry"].find_one(
                {"machine_id": mid, "timestamp": {"$lt": first_start}}, sort=[("timestamp", DESCENDING)]
            )
            samples = list(db["telemetry"].find(
                {"machine_id": mid, "timestamp": {"$gte": first_start, "$lt": last_end}}
            ).sort("timestamp", ASCENDING))
            energy_by_bucket, units_by_bucket = [0.0] * len(starts), [0.0] * len(starts)
            sequence = ([previous] if previous else []) + samples
            for before, after in zip(sequence, sequence[1:]):
                before_time, after_time = before["timestamp"], after["timestamp"]
                if before_time.tzinfo is None: before_time = before_time.replace(tzinfo=timezone.utc)
                if after_time.tzinfo is None: after_time = after_time.replace(tzinfo=timezone.utc)
                if mode == "hour":
                    bucket = int((after_time - starts[0]).total_seconds() // 3600)
                elif mode == "month":
                    bucket = (after_time.year - starts[0].year) * 12 + after_time.month - starts[0].month
                else:
                    bucket = (after_time.date() - starts[0].date()).days
                if not 0 <= bucket < len(starts) or after_time >= ends[bucket]:
                    continue
                hours = max(0.0, (after_time - before_time).total_seconds() / 3600)
                old_kwh, new_kwh = before.get("energy_kwh"), after.get("energy_kwh")
                if old_kwh is not None and new_kwh is not None and new_kwh >= old_kwh:
                    energy = new_kwh - old_kwh
                else:
                    energy = (float(before.get("power_kw", 0)) + float(after.get("power_kw", 0))) * 0.5 * hours
                energy_by_bucket[bucket] += energy
                units_by_bucket[bucket] += float(machine.get("units_per_hour", 0) or 0) * hours if float(after.get("power_kw", 0)) > 0 else 0
            baseline = float(machine.get("baseline_kwh_per_unit", 0) or 0)
            points = []
            for index, energy in enumerate(energy_by_bucket):
                units = units_by_bucket[index]
                kwu = energy / units if units > 0 else 0.0
                efficiency = min(100.0, baseline / kwu * 100) if baseline > 0 and kwu > 0 else 0.0
                totals_energy[index] += energy
                if efficiency > 0: totals_eff[index].append(efficiency)
                points.append({"l": labels[index], "e": round(energy, 3), "kwu": round(kwu, 3), "eff": round(efficiency, 1)})
            machine_series.append({"machineId": mid, "points": points})
        total_series = [{"l": label, "e": round(totals_energy[i], 3), "eff": round(sum(totals_eff[i]) / len(totals_eff[i]), 1) if totals_eff[i] else 0}
                        for i, label in enumerate(labels)]
        return {"per": machine_series, "total": total_series}
    except PyMongoError:
        raise HTTPException(status_code=503, detail="Could not reach the database")


def report_window(selection):
    today = datetime.now(timezone.utc).date()
    choice = selection.get("rg", "7D")
    if choice == "Custom":
        try:
            first = date.fromisoformat(selection["from"])
            last = date.fromisoformat(selection["to"])
        except (KeyError, TypeError, ValueError):
            raise HTTPException(status_code=422, detail="Choose a valid start and end date")
    else:
        days = {"Today": 1, "7D": 7, "30D": 30, "1Y": 365}.get(choice)
        if days is None:
            raise HTTPException(status_code=422, detail="Unsupported report date range")
        first, last = today - timedelta(days=days - 1), today
    if first > last:
        raise HTTPException(status_code=422, detail="Start date must be before end date")
    start = datetime.combine(first, time.min, tzinfo=timezone.utc)
    end = datetime.combine(last + timedelta(days=1), time.min, tzinfo=timezone.utc)
    return first, last, start, end


@app.post("/reports/generate")
def generate_report(request: ReportRequest, user=Depends(get_current_user)):
    db = require_database()
    first, last, start, end = report_window(request.range)
    try:
        query = {"status": {"$ne": "inactive"}}
        if user["role"] != "admin":
            assigned = user.get("machines", [])
            if request.machineId != "all" and request.machineId not in assigned:
                raise HTTPException(status_code=403, detail="Reports may only include your assigned machines")
            query["machine_id"] = {"$in": assigned if request.machineId == "all" else [request.machineId]}
        elif request.machineId != "all":
            query["machine_id"] = request.machineId
        machines = list(db["machines"].find(query).sort("name", ASCENDING))
        if request.machineId != "all" and not machines:
            raise HTTPException(status_code=404, detail="Machine not found")
        if request.type == "Anomalies":
            machine_ids = [machine["machine_id"] for machine in machines]
            anomaly_query = {
                "machine_id": {"$in": machine_ids},
                "created_at": {"$gte": start, "$lt": end},
            }
            if user["role"] != "admin":
                anomaly_query["$or"] = [
                    {"reported_by": user["employee_id"]},
                    {"assigned_to": user["employee_id"]},
                ]
            alert_count = db["alerts"].count_documents(anomaly_query)
            alerts = list(db["alerts"].find(anomaly_query).sort("created_at", DESCENDING).limit(2000))
            employee_ids = {
                employee_id
                for alert in alerts
                for employee_id in (alert.get("reported_by"), alert.get("assigned_to"))
                if employee_id
            }
            people = {
                person["employee_id"]: person
                for person in db["users"].find(
                    {"employee_id": {"$in": list(employee_ids)}},
                    {"employee_id": 1, "name": 1},
                )
            } if employee_ids else {}
            machine_names = {machine["machine_id"]: machine.get("name", machine["machine_id"]) for machine in machines}
            cols = [
                "Alert ID", "First reported", "Last detected", "Machine", "Machine ID",
                "Rule", "Anomaly details", "Severity", "Status", "Occurrences",
                "Employee ID", "Employee name", "Assigned operator ID", "Assigned operator name",
                "Power (kW)", "Power factor", "Temperature (°C)", "Voltage (V)",
                "Current (A)", "Energy (kWh)",
            ]
            rows = []
            for alert in alerts:
                reading = alert.get("latest_reading") or {}
                reporter = people.get(alert.get("reported_by"), {})
                assignee = people.get(alert.get("assigned_to"), {})
                machine_id = alert.get("machine_id", "")
                rows.append([
                    alert.get("alert_id", ""), iso_timestamp(alert.get("created_at")),
                    iso_timestamp(alert.get("last_detected_at")),
                    machine_names.get(machine_id, alert.get("machine_name", machine_id)), machine_id,
                    alert.get("rule_id", ""), alert.get("message", ""), alert.get("severity", ""),
                    alert.get("status", ""), int(alert.get("occurrences", 1)),
                    alert.get("reported_by", ""), reporter.get("name") or alert.get("reported_by_name", ""),
                    alert.get("assigned_to", ""), assignee.get("name") or alert.get("assigned_to_name", ""),
                    reading.get("power_kw", ""), reading.get("power_factor", ""),
                    reading.get("temperature", ""), reading.get("voltage", ""),
                    reading.get("current", ""), reading.get("energy_kwh", ""),
                ])
            severity_counts = {
                severity: sum(1 for alert in alerts if alert.get("severity") == severity)
                for severity in ("warning", "critical")
            }
            generated_at = datetime.now(timezone.utc)
            result = {
                "type": request.type, "title": "Anomaly incident report",
                "range": f"{first.isoformat()} → {last.isoformat()}",
                "mname": "All machines" if request.machineId == "all" else machines[0].get("name", request.machineId),
                "cols": cols, "rows": rows,
                "sum": [
                    ["Anomaly reports", alert_count],
                    ["Open / in progress", sum(1 for alert in alerts if alert.get("status") != "Resolved")],
                    ["Critical", severity_counts["critical"]],
                    ["Employees reporting", len({alert.get("reported_by") for alert in alerts if alert.get("reported_by")})],
                ],
                "chart": [severity_counts["warning"], severity_counts["critical"]],
                "chartRows": [["Warning"], ["Critical"]],
                "generatedAt": iso_timestamp(generated_at),
                "totalRecords": alert_count,
                "truncated": alert_count > 2000,
            }
            db["reports"].insert_one({**result, "machineId": request.machineId, "created_by": user["employee_id"], "created_at": generated_at})
            return result
        daily = {}
        per_machine = []
        for machine in machines:
            mid = machine["machine_id"]
            previous = db["telemetry"].find_one(
                {"machine_id": mid, "timestamp": {"$lt": start}}, sort=[("timestamp", DESCENDING)]
            )
            samples = list(db["telemetry"].find(
                {"machine_id": mid, "timestamp": {"$gte": start, "$lt": end}}
            ).sort("timestamp", ASCENDING))
            sequence = ([previous] if previous else []) + samples
            energy = 0.0
            for before, after in zip(sequence, sequence[1:]):
                before_time, after_time = before["timestamp"], after["timestamp"]
                if before_time.tzinfo is None:
                    before_time = before_time.replace(tzinfo=timezone.utc)
                if after_time.tzinfo is None:
                    after_time = after_time.replace(tzinfo=timezone.utc)
                hours = max(0, (after_time - before_time).total_seconds() / 3600)
                old_kwh, new_kwh = before.get("energy_kwh"), after.get("energy_kwh")
                if old_kwh is not None and new_kwh is not None and new_kwh >= old_kwh:
                    delta = new_kwh - old_kwh
                else:
                    delta = (float(before.get("power_kw", 0)) + float(after.get("power_kw", 0))) * 0.5 * hours
                energy += delta
                bucket = after_time.astimezone(timezone.utc).date().isoformat()
                daily[bucket] = daily.get(bucket, 0.0) + delta
            per_machine.append({"machine": machine, "energy": energy, "samples": len(samples)})

        total_energy = sum(item["energy"] for item in per_machine)
        co2 = total_energy * 0.82
        if request.type == "Energy":
            cols = ["Period", "kWh", "Cost (₹)", "CO₂ (kg)"]
            rows = [[day, round(value, 3), round(value * request.tariff, 2), round(value * 0.82, 3)]
                    for day, value in sorted(daily.items())]
            summary = [["Total kWh", round(total_energy, 3)], ["Cost ₹", round(total_energy * request.tariff, 2)], ["CO₂ kg", round(co2, 3)]]
            chart = [round(value, 3) for _, value in sorted(daily.items())]
        elif request.type == "Machine":
            cols = ["Machine", "Type", "Stoppable", "kWh", "kWh/unit", "Efficiency %"]
            rows = [[item["machine"].get("name", item["machine"]["machine_id"]), item["machine"].get("machine_type", "Other"),
                     "No" if item["machine"].get("operational_constraint") == "continuous_operation_required" else "Yes",
                     round(item["energy"], 3), "—", "—"] for item in per_machine]
            summary = [["Machines", len(machines)], ["Total kWh", round(total_energy, 3)], ["Telemetry samples", sum(x["samples"] for x in per_machine)]]
            chart = [round(item["energy"], 3) for item in per_machine]
        elif request.type == "Sustainability":
            cols = ["Machine", "kWh", "CO₂ (kg)", "kWh/unit", "Vs baseline %"]
            rows = [[item["machine"].get("name", item["machine"]["machine_id"]), round(item["energy"], 3), round(item["energy"] * 0.82, 3), "—", "—"] for item in per_machine]
            summary = [["CO₂ kg", round(co2, 3)], ["Total kWh", round(total_energy, 3)]]
            chart = [round(item["energy"] * 0.82, 3) for item in per_machine]
        else:
            cols = ["Machine", "Status", "Maintenance"]
            rows = [[item["machine"].get("name", item["machine"]["machine_id"]), item["machine"].get("status", "active"), item["machine"].get("maintenance_status", "Not scheduled")] for item in per_machine]
            summary = [["Machines", len(machines)], ["Maintenance schedules", sum(1 for x in per_machine if x["machine"].get("maintenance_status"))]]
            chart = [1 if item["machine"].get("maintenance_status") else 0 for item in per_machine]

        generated_at = datetime.now(timezone.utc)
        result = {
            "type": request.type, "title": request.type + " report",
            "range": f"{first.isoformat()} → {last.isoformat()}",
            "mname": "All machines" if request.machineId == "all" else machines[0].get("name", request.machineId),
            "cols": cols, "rows": rows, "sum": summary, "chart": chart,
            "generatedAt": iso_timestamp(generated_at),
        }
        db["reports"].insert_one({**result, "machineId": request.machineId, "created_by": user["employee_id"], "created_at": generated_at})
        return result
    except HTTPException:
        raise
    except PyMongoError:
        raise HTTPException(status_code=503, detail="Could not reach the database")



