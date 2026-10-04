# VoltEdge MQTT telemetry setup

## Configure the broker

MongoDB Atlas stores the readings; it is not an MQTT broker. VoltEdge needs an MQTT broker reachable by both the FastAPI computer and the IoT device. Add the broker settings from `.env.mqtt.example` to the existing `backend/.env` file. Keep the MongoDB and JWT values already in that file. Use the host name only (no `mqtts://` prefix). TLS is enabled by default on port 8883; for a trusted local broker without TLS, set `MQTT_TLS=false` and use port 1883.

Install the backend dependencies from the `backend` folder:

```powershell
pip install -r requirements.txt
```

Restart FastAPI, then open `http://localhost:8001/health/mqtt`. The response should show `configured: true` and `connected: true`. If it is not connected, check the broker hostname, port, credentials, TLS choice, and that the broker allows connections from this computer.

## Register a device

Sign in as admin, open **Devices**, choose protocol **MQTT**, enter the device ID and link it to an active machine. The publish topic is:

```text
voltedge/telemetry/<DEVICE_ID>
```

For example, device `ESP32-101` publishes to `voltedge/telemetry/ESP32-101`. The broker subscriber listens to `MQTT_TOPIC_PREFIX/+`. The backend looks up the device in the `devices` collection and rejects telemetry if it is missing, disabled, set to another protocol, linked to an inactive machine, or if a supplied machine/device ID does not match the registration.

Publish a JSON object with these required fields:

```json
{
  "power_kw": 2.7,
  "power_factor": 0.93,
  "temperature": 48.2,
  "voltage": 231.4,
  "current": 12.6,
  "energy_kwh": 1834.5,
  "timestamp": "2026-10-03T12:30:00Z"
}
```

`voltage`, `current`, `energy_kwh`, and `timestamp` are optional. The registered device and machine IDs are taken from the MQTT topic and MongoDB device record. The backend adds the MQTT source and a current UTC timestamp when no timestamp is provided. Readings are stored in MongoDB's `telemetry` collection.

## Run the demo publisher

Register an MQTT device first. Set `MQTT_DEVICE_ID` to that device ID in the environment where the simulator runs. From the backend folder, run:

```powershell
python demo_mqtt.py
```

The simulator publishes changing values every five seconds. Stop it with Ctrl+C. The same broker host, TLS, and credentials configured for the backend are used by this local demo publisher.

## Confirm telemetry

The device status changes to **Connected** after a reading arrives and remains connected while a reading has arrived within the last minute. The admin dashboard refreshes live demand and alert summaries every five seconds. Analytics uses the stored telemetry history; choose a date range containing the readings. The operator machine view refreshes from the API every five seconds unless a WebSocket URL has separately been configured.

For a deployed broker, use TLS, strong credentials, and broker ACLs that limit device publish access to that device's topic. Do not commit `.env` or share its passwords.
