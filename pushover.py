import requests
from typing import Optional

def send_pushover(
    user: Optional[str],
    token: Optional[str],
    message: str,
    priority: int = 0,
    sound: str = "none",
) -> bool:
    if not user or not token:
        return False
    try:
        requests.post(
            "https://api.pushover.net/1/messages.json",
            data={
                "token": token,
                "user": user,
                "message": message,
                "priority": priority,
                "sound": sound,
            },
            timeout=10,
        ).raise_for_status()
        return True
    except Exception:
        return False

# Pre-built helpers
def notify_reset_triggered(lat_ms: int, speed_mbps: Optional[float]):
    speed_part = f" & speed {speed_mbps:.1f} Mbps" if speed_mbps is not None else ""
    msg = f"VPN reset triggered: latency {lat_ms} ms{speed_part}"
    send_pushover(config.PUSHOVER_USER, config.PUSHOVER_TOKEN, msg, 0, "climb")

def notify_reset_success(old_ip: str, new_ip: str):
    msg = f"VPN reset successful: {old_ip} → {new_ip}"
    send_pushover(config.PUSHOVER_USER, config.PUSHOVER_TOKEN, msg, 0, "magic")

def notify_reset_same_ip(ip: str):
    msg = f"VPN reset completed but IP unchanged: {ip}"
    send_pushover(config.PUSHOVER_USER, config.PUSHOVER_TOKEN, msg, 0, "default")

def notify_circuit_breaker_tripped():
    msg = "CRITICAL: Circuit breaker tripped — auto-reset suspended"
    send_pushover(config.PUSHOVER_USER, config.PUSHOVER_TOKEN, msg, 1, "siren")

def notify_reset_deferred(reason: str):
    msg = f"Reset deferred: {reason}"
    send_pushover(config.PUSHOVER_USER, config.PUSHOVER_TOKEN, msg, -1, "none")
