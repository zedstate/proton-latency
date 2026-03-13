import json
import os
from datetime import datetime, timedelta
from typing import Optional
from dateutil.parser import isoparse, parse

class State:
    def __init__(self, data_dir: str):
        self.path = os.path.join(data_dir, "state.json")
        self.data = self._load_or_create()

    def _load_or_create(self) -> dict:
        defaults = {
            "last_reset_ts": None,
            "consecutive_bad_latency": 0,
            "circuit_breaker_count": 0,
            "circuit_breaker_tripped": False,
            "circuit_breaker_last_failed_ts": None,
            "resets_this_hour": 0,
            "resets_hour_bucket": None,
            "last_exit_ip": None,
            "last_latency_ms": None,
            "last_speed_mbps": None,
        }
        if os.path.exists(self.path):
            with open(self.path, "r") as f:
                loaded = json.load(f)
                loaded = {**defaults, **loaded}  # merge with defaults
                return loaded
        with open(self.path, "w") as f:
            json.dump(defaults, f, indent=2)
        return defaults

    def save(self):
        with open(self.path, "w") as f:
            json.dump(self.data, f, indent=2)

    def can_reset(self, min_reconnect_min: int, max_per_hour: int) -> tuple[bool, str]:
        now = datetime.utcnow()

        # Circuit breaker cooldown
        if self.data["circuit_breaker_tripped"]:
            last_failed = self.data["circuit_breaker_last_failed_ts"]
            if last_failed:
                last_failed_dt = isoparse(last_failed)
                if now - last_failed_dt >= timedelta(minutes=min_reconnect_min):
                    self.data["circuit_breaker_tripped"] = False
                    self.data["circuit_breaker_count"] = 0
                    self.save()
                else:
                    return False, "circuit breaker cooldown active"

        # Cooldown from last reset
        if self.data["last_reset_ts"]:
            last_reset = isoparse(self.data["last_reset_ts"])
            if now - last_reset < timedelta(minutes=min_reconnect_min):
                return False, "min reconnect cooldown active"

        # Hourly cap
        current_hour = now.strftime("%Y-%m-%dT%H")
        if self.data["resets_hour_bucket"] == current_hour:
            if self.data["resets_this_hour"] >= max_per_hour:
                return False, "hourly reset cap reached"
        else:
            self.data["resets_this_hour"] = 0
            self.data["resets_hour_bucket"] = current_hour

        return True, ""

    def record_reset_attempt(self, success: bool, new_ip: Optional[str]):
        now_iso = datetime.utcnow().isoformat()
        self.data["last_reset_ts"] = now_iso
        self.data["last_exit_ip"] = new_ip

        if success:
            self.data["circuit_breaker_count"] = 0
            self.data["circuit_breaker_tripped"] = False
            self.data["circuit_breaker_last_failed_ts"] = None
        else:
            self.data["circuit_breaker_count"] += 1
            self.data["circuit_breaker_last_failed_ts"] = now_iso
            if self.data["circuit_breaker_count"] >= 3:  # threshold hardcoded here per spec
                self.data["circuit_breaker_tripped"] = True

        current_hour = datetime.utcnow().strftime("%Y-%m-%dT%H")
        if self.data["resets_hour_bucket"] == current_hour:
            self.data["resets_this_hour"] += 1
        else:
            self.data["resets_this_hour"] = 1
            self.data["resets_hour_bucket"] = current_hour

        self.save()
