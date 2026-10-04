"""Publish sample VoltEdge telemetry to a registered MQTT device topic."""
import json
import math
import os
import random
import time
from datetime import datetime, timezone

from dotenv import load_dotenv
import paho.mqtt.client as mqtt

load_dotenv()

host = os.getenv("MQTT_BROKER_HOST", "").strip()
device_id = os.getenv("MQTT_DEVICE_ID", "").strip()
if not host or not device_id:
    raise SystemExit("Set MQTT_BROKER_HOST and MQTT_DEVICE_ID before running this demo.")

tls = os.getenv("MQTT_TLS", "true").lower() == "true"
port = int(os.getenv("MQTT_BROKER_PORT", "8883" if tls else "1883"))
prefix = os.getenv("MQTT_TOPIC_PREFIX", "voltedge/telemetry").strip("/")
topic = f"{prefix}/{device_id}"
client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"voltedge-demo-{device_id}")
username, password = os.getenv("MQTT_USERNAME"), os.getenv("MQTT_PASSWORD")
if username:
    client.username_pw_set(username, password or None)
if tls:
    client.tls_set()

client.connect(host, port, keepalive=60)
client.loop_start()
print(f"Publishing sample telemetry to {topic}. Press Ctrl+C to stop.")
energy = 0.0
index = 0
try:
    while True:
        power = 2.5 + math.sin(index / 8) * 0.25 + random.uniform(-0.05, 0.05)
        energy += power * (5 / 3600)
        payload = {
            "power_kw": round(max(0, power), 3),
            "power_factor": round(0.93 + random.uniform(-0.015, 0.015), 3),
            "temperature": round(48 + math.sin(index / 10) * 1.5, 1),
            "voltage": round(231 + random.uniform(-2, 2), 1),
            "current": round(power * 1000 / (1.732 * 231 * 0.93), 2),
            "energy_kwh": round(energy, 5),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        result = client.publish(topic, json.dumps(payload), qos=1)
        result.wait_for_publish()
        print(f"{payload['timestamp']} · {payload['power_kw']} kW · {payload['temperature']} °C")
        index += 1
        time.sleep(5)
except KeyboardInterrupt:
    print("Stopping MQTT demo publisher.")
finally:
    client.disconnect()
    client.loop_stop()
