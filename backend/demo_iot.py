"""Generate changing demo IoT readings for VoltEdge without physical hardware."""

import json
import math
import os
import time
from getpass import getpass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from dotenv import load_dotenv

load_dotenv()

API = "http://127.0.0.1:8001"
INTERVAL_SECONDS = 5


def request_json(path, payload=None, token=None):
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    request = Request(
        API + path,
        data=body,
        headers=headers,
        method="GET" if body is None else "POST",
    )
    with urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def load_machines():
    employee_id = os.getenv("INITIAL_ADMIN_ID", "ADM0001").strip()
    password = getpass(f"Admin password for {employee_id} (input hidden): ")
    if not employee_id or not password:
        raise RuntimeError("Enter the admin employee ID and password to start the simulator.")
    session = request_json("/auth/login", {"employeeId": employee_id, "password": password})
    token = session["token"]
    machines = request_json("/machines", token=token)
    devices = request_json("/devices", token=token)
    device_by_machine = {
        device["machine_id"]: device["device_id"]
        for device in devices
        if device.get("enabled", True)
    }
    usable = [
        machine for machine in machines
        if machine.get("machine_id")
        and machine.get("name", "").strip().lower() != "string"
        and machine.get("machine_id", "").strip().lower() != "string"
    ]
    return usable, token, device_by_machine


def main():
    try:
        machines, token, device_by_machine = load_machines()
    except (HTTPError, URLError, TimeoutError, RuntimeError) as error:
        print("Could not start the VoltEdge demo IoT. Check the backend and admin settings.")
        print(f"Details: {error}")
        return

    if not machines:
        print("No machines found. Add a machine in VoltEdge before starting the simulator.")
        return

    states = []
    for index, machine in enumerate(machines):
        rated_power = float(machine.get("rated_power") or 0)
        current_power = float(machine.get("power") or 0)
        base_power = rated_power * 0.58 if rated_power > 0 else (current_power or 14.0)
        states.append({
            "machine_id": machine["machine_id"],
            "device_id": device_by_machine.get(machine["machine_id"]),
            "name": machine.get("name", machine["machine_id"]),
            "base_power": base_power,
            "base_pf": float(machine.get("power_factor") or 0.93),
            "base_temp": float(machine.get("temperature") or 48.0),
            "energy": float(machine.get("energy") or 0),
            "phase": index * 0.9,
        })

    print("VoltEdge demo IoT is publishing sample readings every 5 seconds.")
    print("Machines: " + ", ".join(state["name"] for state in states))
    print("Press Ctrl+C to stop. These are simulated readings, not real sensor data.")

    tick = 0
    try:
        while True:
            for state in states:
                angle = tick / 7 + state["phase"]
                power = max(0.1, state["base_power"] * (1 + 0.06 * math.sin(angle)))
                power_factor = min(0.99, max(0.80, state["base_pf"] + 0.01 * math.sin(angle / 2)))
                temperature = state["base_temp"] + 1.5 * math.sin(angle / 3)
                state["energy"] += power * INTERVAL_SECONDS / 3600
                payload = {
                    "machine_id": state["machine_id"],
                    "power_kw": round(power, 2),
                    "power_factor": round(power_factor, 2),
                    "temperature": round(temperature, 1),
                    "energy_kwh": round(state["energy"], 4),
                    "source": "demo_simulator",
                }
                if state.get("device_id"):
                    payload["device_id"] = state["device_id"]
                try:
                    request_json("/telemetry", payload, token=token)
                    print(
                        f"{state['name']}: {payload['power_kw']} kW, "
                        f"PF {payload['power_factor']}, {payload['temperature']} C"
                    )
                except (HTTPError, URLError, TimeoutError) as error:
                    print(f"Could not send a reading for {state['name']}: {error}")
            tick += 1
            time.sleep(INTERVAL_SECONDS)
    except KeyboardInterrupt:
        print("\nDemo IoT stopped.")


if __name__ == "__main__":
    main()
