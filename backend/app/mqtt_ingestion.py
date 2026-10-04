"""MQTT subscriber that validates devices and stores readings in MongoDB."""
import json
import logging
import os
from datetime import datetime, timezone

from pymongo import ASCENDING, DESCENDING

from app.core.database import database
from app.models import TelemetryCreate

logger = logging.getLogger("voltedge.mqtt")
_client = None
_dependency_available = None
_indexes_ready = False


def mqtt_status():
    host = os.getenv("MQTT_BROKER_HOST", "").strip()
    return {"configured": bool(host), "connected": bool(_client and _client.is_connected()), "dependency_available": _dependency_available is not False, "topic": os.getenv("MQTT_TOPIC_PREFIX", "voltedge/telemetry").strip("/") + "/+" if host else None}


def _handle_message(topic, payload):
    global _indexes_ready
    if database is None:
        logger.error("Discarding MQTT telemetry: MongoDB is not configured")
        return
    prefix = os.getenv("MQTT_TOPIC_PREFIX", "voltedge/telemetry").strip("/")
    topic_prefix = prefix + "/"
    if not topic.startswith(topic_prefix):
        return
    device_id = topic[len(topic_prefix):].strip()
    if not device_id or "/" in device_id:
        logger.warning("Discarding MQTT message with invalid device topic: %s", topic)
        return
    try:
        message = json.loads(payload.decode("utf-8"))
        if not isinstance(message, dict):
            raise ValueError("Payload must be a JSON object")
        if message.get("device_id") and message["device_id"] != device_id:
            raise ValueError("Payload device_id does not match the MQTT topic")
        device = database["devices"].find_one({"device_id": device_id})
        if not device:
            logger.warning("Discarding MQTT message: device %s is not registered", device_id)
            return
        # Match the Devices API, which treats legacy records without an enabled
        # field as enabled; only an explicit false value disables the device.
        if device.get("enabled", True) is False:
            logger.warning("Discarding MQTT message: device %s is disabled", device_id)
            return
        if device.get("protocol", "").strip().lower() != "mqtt":
            logger.warning("Discarding MQTT message: device %s uses protocol %r, not MQTT", device_id, device.get("protocol"))
            return
        supplied_machine = message.get("machine_id", device["machine_id"])
        if supplied_machine != device["machine_id"]:
            raise ValueError("Payload machine_id does not match the registered device")
        machine = database["machines"].find_one({"machine_id": device["machine_id"], "status": {"$ne": "inactive"}})
        if not machine:
            logger.warning("Discarding MQTT message: linked machine is inactive for device %s", device_id)
            return
        message.update({"device_id": device_id, "machine_id": device["machine_id"], "source": "mqtt"})
        reading = TelemetryCreate(**message)
        timestamp = reading.timestamp or datetime.now(timezone.utc)
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        document = reading.dict(exclude_none=True)
        document.update({"timestamp": timestamp, "source": "mqtt"})
        telemetry = database["telemetry"]
        if not _indexes_ready:
            telemetry.create_index([("machine_id", ASCENDING), ("timestamp", DESCENDING)])
            telemetry.create_index([("device_id", ASCENDING), ("timestamp", DESCENDING)])
            _indexes_ready = True
        telemetry.insert_one(document)
        database["devices"].update_one({"device_id": device_id}, {"$set": {"last_seen": timestamp}})
        logger.info("Stored MQTT telemetry for %s (%s)", device_id, device["machine_id"])
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError, TypeError) as exc:
        logger.warning("Discarding invalid MQTT telemetry on %s: %s", topic, exc)
    except Exception:
        logger.exception("Could not store MQTT telemetry from %s", topic)


def start_mqtt_subscriber():
    global _client, _dependency_available
    host = os.getenv("MQTT_BROKER_HOST", "").strip()
    if not host:
        logger.info("MQTT subscriber is disabled; configure MQTT_BROKER_HOST to enable it")
        return None
    try:
        import paho.mqtt.client as mqtt
        _dependency_available = True
    except ImportError:
        _dependency_available = False
        logger.error("MQTT subscriber is configured but paho-mqtt is missing; install backend requirements")
        return None
    tls = os.getenv("MQTT_TLS", "true").lower() == "true"
    port = int(os.getenv("MQTT_BROKER_PORT", "8883" if tls else "1883"))
    prefix = os.getenv("MQTT_TOPIC_PREFIX", "voltedge/telemetry").strip("/")
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=os.getenv("MQTT_CLIENT_ID", "voltedge-backend"))
    username, password = os.getenv("MQTT_USERNAME"), os.getenv("MQTT_PASSWORD")
    if username:
        client.username_pw_set(username, password or None)
    if tls:
        client.tls_set()

    def connected(mqtt_client, _userdata, _flags, reason_code, _properties):
        if reason_code.is_failure:
            logger.error("MQTT broker rejected the connection: %s", reason_code)
            return
        mqtt_client.subscribe(prefix + "/+", qos=1)
        logger.info("Connected to MQTT broker; subscribed to %s/+", prefix)

    client.on_connect = connected
    client.on_message = lambda _client, _userdata, message: _handle_message(message.topic, message.payload)
    client.connect_async(host, port, keepalive=60)
    client.loop_start()
    _client = client
    return client


def stop_mqtt_subscriber():
    global _client
    if _client:
        _client.disconnect()
        _client.loop_stop()
        _client = None
