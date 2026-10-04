"""VoltEdge adapter for the trained energy and anomaly models."""
from __future__ import annotations

import importlib
import logging
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

logger = logging.getLogger("voltedge.ml")
MODEL_DIR = Path(__file__).resolve().parent / "ml"
MIN_WINDOWS = 97  # 96 lagged quarter-hour values plus the current value
MAX_WINDOWS = 200
MAX_TELEMETRY_ROWS = 50000
CACHE_SECONDS = 20
_model_lock = threading.Lock()
_model_module = None
_cache_lock = threading.Lock()
_analysis_cache = {}


class MLServiceUnavailable(RuntimeError):
    pass


def _load_model_module():
    global _model_module
    if _model_module is not None:
        return _model_module
    with _model_lock:
        if _model_module is not None:
            return _model_module
        required = [MODEL_DIR / "ml_inference.py", MODEL_DIR / "voltedge_energy_model_full.pkl", MODEL_DIR / "voltedge_anomaly_models.pkl"]
        missing = [path.name for path in required if not path.is_file()]
        if missing:
            raise MLServiceUnavailable("Trained ML files are missing: " + ", ".join(missing))
        try:
            _model_module = importlib.import_module("app.ml.ml_inference")
        except Exception as exc:
            logger.exception("Could not load VoltEdge trained ML models")
            raise MLServiceUnavailable("The trained ML models could not be loaded. Check backend ML dependencies and model files.") from exc
    return _model_module


def available_asset_ids():
    module = _load_model_module()
    return sorted(str(asset_id) for asset_id in module.anomaly_models)


def _utc(value):
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _interval_energy(records):
    """Integrate cumulative meter deltas or power over 15-minute UTC windows."""
    energy_by_window = {}
    previous_by_stream = {}
    for current in records:
        current_time = _utc(current.get("timestamp"))
        if current_time is None:
            continue
        stream_id = str(current.get("device_id") or "__machine__")
        previous = previous_by_stream.get(stream_id)
        previous_by_stream[stream_id] = current
        if previous is None:
            continue
        previous_time = _utc(previous.get("timestamp"))
        seconds = (current_time - previous_time).total_seconds()
        # Ignore clock reversals and long gaps instead of inventing their energy.
        if seconds <= 0 or seconds > 1800:
            continue
        old_energy, new_energy = previous.get("energy_kwh"), current.get("energy_kwh")
        try:
            old_energy, new_energy = float(old_energy), float(new_energy)
            delta = new_energy - old_energy if new_energy >= old_energy else -1
        except (TypeError, ValueError):
            delta = -1
        if delta < 0:
            try:
                old_power = float(previous.get("power_kw", 0) or 0)
                new_power = float(current.get("power_kw", 0) or 0)
                delta = max(0.0, (old_power + new_power) * 0.5 * seconds / 3600)
            except (TypeError, ValueError):
                continue
        # Split an interval across boundaries so the model receives true quarter-hour buckets.
        cursor = previous_time.timestamp()
        end = current_time.timestamp()
        duration = end - cursor
        while cursor < end:
            window = int(cursor // 900) * 900
            boundary = min(end, window + 900)
            energy_by_window[window] = energy_by_window.get(window, 0.0) + delta * ((boundary - cursor) / duration)
            cursor = boundary
    return energy_by_window


def _forecast_next_hour(module, history, asset_id, last_window):
    """Recursive four-step forecast using the handoff's trained one-step model."""
    import pandas as pd

    forecast_history = history.copy()
    forecasts = []
    for step in range(1, 5):
        next_window = last_window + step * 900
        future = pd.DataFrame([{
            "AssetId": asset_id,
            "window_start_utc": datetime.fromtimestamp(next_window, tz=timezone.utc),
            "Energy_kWh_15m": float("nan"),
        }])
        candidate = pd.concat([forecast_history, future], ignore_index=True)
        predicted = module.predict_energy(candidate)
        value = predicted.iloc[-1].get("expected_energy_kwh")
        if pd.isna(value):
            break
        value = max(0.0, float(value))
        forecasts.append({
            "window_start_utc": datetime.fromtimestamp(next_window, tz=timezone.utc).isoformat(),
            "expected_energy_kwh": value,
        })
        future.loc[0, "Energy_kWh_15m"] = value
        forecast_history = pd.concat([forecast_history, future], ignore_index=True)
    return forecasts


def analyze_machine(db, machine, tariff_rupees_per_kwh=8.0):
    module = _load_model_module()
    machine_id = str(machine.get("machine_id", ""))
    asset_id = str(machine.get("ml_asset_id") or "").strip()
    assets = sorted(str(key) for key in module.anomaly_models)
    if not asset_id:
        return {
            "status": "mapping_required", "machine_id": machine_id,
            "machine_name": machine.get("name", machine_id), "ml_asset_id": None,
            "available_asset_ids": assets,
            "message": "Choose the matching trained asset ID for this machine.",
        }
    if asset_id not in assets:
        return {
            "status": "unsupported_asset", "machine_id": machine_id,
            "machine_name": machine.get("name", machine_id), "ml_asset_id": asset_id,
            "available_asset_ids": assets,
            "message": "This asset ID is not present in the trained models.",
        }

    latest = db["telemetry"].find_one({"machine_id": machine_id}, {"timestamp": 1}, sort=[("timestamp", -1)])
    latest_stamp = latest.get("timestamp") if latest else None
    cache_key = (machine_id, asset_id, latest_stamp, float(tariff_rupees_per_kwh))
    now_mono = time.monotonic()
    with _cache_lock:
        cached = _analysis_cache.get(cache_key)
        if cached and now_mono - cached[0] < CACHE_SECONDS:
            return cached[1]

    records = list(db["telemetry"].find(
        {"machine_id": machine_id},
        {"timestamp": 1, "device_id": 1, "energy_kwh": 1, "power_kw": 1},
    ).sort("timestamp", -1).limit(MAX_TELEMETRY_ROWS))
    records.reverse()
    energy = _interval_energy(records)
    now_utc = datetime.now(timezone.utc)
    latest_completed = int(now_utc.timestamp() // 900) * 900 - 900
    populated = sorted(window for window in energy if window <= latest_completed)
    if not populated:
        result = {
            "status": "no_data", "machine_id": machine_id,
            "machine_name": machine.get("name", machine_id), "ml_asset_id": asset_id,
            "sample_windows": 0, "required_windows": MIN_WINDOWS,
            "message": "No completed 15-minute telemetry windows are available yet.",
        }
    else:
        # Only use an uninterrupted tail: lag_96 means each model row must be 15 minutes apart.
        end_window = populated[-1]
        contiguous = []
        cursor = end_window
        while cursor in energy and len(contiguous) < MAX_WINDOWS:
            contiguous.append(cursor)
            cursor -= 900
        contiguous.reverse()
        if len(contiguous) < MIN_WINDOWS:
            last_time = _utc(records[-1].get("timestamp")) if records else None
            result = {
                "status": "warming_up", "machine_id": machine_id,
                "machine_name": machine.get("name", machine_id), "ml_asset_id": asset_id,
                "sample_windows": len(contiguous), "required_windows": MIN_WINDOWS,
                "history_hours_required": 24.25,
                "last_reading_at": last_time.isoformat() if last_time else None,
                "message": "The model needs at least 97 consecutive completed 15-minute windows (about 24 hours) before it can predict.",
            }
        else:
            try:
                import pandas as pd
                rows = [{
                    "AssetId": asset_id,
                    "window_start_utc": datetime.fromtimestamp(window, tz=timezone.utc),
                    "Energy_kWh_15m": max(0.0, float(energy[window])),
                } for window in contiguous]
                frame = pd.DataFrame(rows)
                predicted = module.run_ml_pipeline(frame, tariff_rupees_per_kwh=float(tariff_rupees_per_kwh))
                latest_row = predicted.iloc[-1]
                expected = latest_row.get("expected_energy_kwh")
                anomaly_flag = latest_row.get("anomaly_flag")
                if pd.isna(expected) or pd.isna(anomaly_flag):
                    result = {
                        "status": "warming_up", "machine_id": machine_id,
                        "machine_name": machine.get("name", machine_id), "ml_asset_id": asset_id,
                        "sample_windows": len(contiguous), "required_windows": MIN_WINDOWS,
                        "message": "The model needs more complete history to calculate this prediction.",
                    }
                else:
                    def number(name):
                        value = latest_row.get(name)
                        return None if pd.isna(value) else float(value)
                    latest_window = datetime.fromtimestamp(contiguous[-1], tz=timezone.utc)
                    last_reading = _utc(records[-1].get("timestamp")) if records else None
                    age_seconds = max(0.0, (now_utc - last_reading).total_seconds()) if last_reading else None
                    try:
                        forecast = _forecast_next_hour(module, frame, asset_id, contiguous[-1])
                    except Exception:
                        logger.exception("VoltEdge forward forecast failed for machine %s", machine_id)
                        forecast = []
                    previous_day = float(frame.iloc[-97]["Energy_kWh_15m"]) if len(frame) >= MIN_WINDOWS else None
                    actual = number("Energy_kWh_15m")
                    expected = number("expected_energy_kwh")
                    deviation_pct = ((actual - expected) / expected * 100.0) if actual is not None and expected not in (None, 0) else None
                    result = {
                        "status": "ready", "machine_id": machine_id,
                        "machine_name": machine.get("name", machine_id), "ml_asset_id": asset_id,
                        "sample_windows": len(contiguous), "required_windows": MIN_WINDOWS,
                        "last_reading_at": last_reading.isoformat() if last_reading else None,
                        "telemetry_age_seconds": age_seconds,
                        "telemetry_fresh": age_seconds is not None and age_seconds <= 1800,
                        "window_start_utc": latest_window.isoformat(),
                        "actual_energy_kwh": actual,
                        "expected_energy_kwh": expected,
                        "deviation_percent": deviation_pct,
                        "same_time_previous_day_kwh": previous_day,
                        "forecast_next_hour": forecast,
                        "forecast_next_hour_total_kwh": sum(item["expected_energy_kwh"] for item in forecast) if len(forecast) == 4 else None,
                        "forecast_steps_available": len(forecast),
                        "forecast_method": "Recursive 15-minute point forecasts from the trained energy model; later steps use earlier predictions.",
                        "anomaly": bool(int(anomaly_flag) == 1),
                        "anomaly_score": number("anomaly_score"),
                        "severity": str(latest_row.get("severity", "NORMAL")),
                        "excess_energy_kwh": number("excess_energy_kwh"),
                        "potential_waste_kwh": number("potential_waste_kwh"),
                        "potential_cost_impact_rupees": number("potential_cost_impact"),
                        "tariff_rupees_per_kwh": float(tariff_rupees_per_kwh),
                    }
            except Exception as exc:
                logger.exception("VoltEdge ML inference failed for machine %s", machine_id)
                raise MLServiceUnavailable("The trained model could not analyze this machine's telemetry.") from exc
    with _cache_lock:
        _analysis_cache[cache_key] = (now_mono, result)
        # Prevent unbounded growth as the app is used across many machine mappings.
        if len(_analysis_cache) > 500:
            _analysis_cache.clear()
    return result


def recommendation_from_analysis(analysis):
    if analysis.get("status") != "ready" or not analysis.get("anomaly"):
        return []
    severity = str(analysis.get("severity", "MEDIUM")).upper()
    level = "bad" if severity in {"HIGH", "CRITICAL"} else "warn"
    actual = analysis.get("actual_energy_kwh")
    expected = analysis.get("expected_energy_kwh")
    excess = analysis.get("potential_waste_kwh") or 0.0
    cost = analysis.get("potential_cost_impact_rupees") or 0.0
    score = analysis.get("anomaly_score")
    return [{
        "rid": f"ML-{analysis['machine_id']}-{analysis['window_start_utc']}",
        "rule": "ENERGY_ML_ANOMALY", "lvl": level,
        "obs": f"Trained model flagged {actual:.3f} kWh in this 15-minute window; its expected value was {expected:.3f} kWh.",
        "why": f"Asset-specific Isolation Forest detected an unusual energy pattern (severity {severity}, score {score if score is not None else 'unavailable'}).",
        "acts": ["Review the machine's telemetry and operating conditions", "Check for idle load, leakage, or an unplanned process change"],
        "obj": f"Potential excess: {excess:.3f} kWh · estimated impact ₹{cost:.2f} at ₹{analysis.get('tariff_rupees_per_kwh', 8.0):.2f}/kWh",
        "esc": "", "stop": False, "source": "ml-service",
        "severity": severity, "anomaly_score": score, "asset_id": analysis["ml_asset_id"],
    }]
