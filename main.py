import time
from datetime import datetime
import pytz
import requests  # ← added for IP geolocation lookup

from config import Config
from logger import setup_logging
from gluetun import GluetunClient
from measurements import measure_latency, measure_speed
from scheduler import Scheduler
from state import State
from pushover import (
    notify_reset_triggered,
    notify_reset_success,
    notify_reset_same_ip,
    notify_circuit_breaker_tripped,
    notify_reset_deferred,
    send_pushover,
)

logger = setup_logging()
config = Config()
config.validate()

gluetun = GluetunClient(config.GLUETUN_API, config.GLUETUN_API_KEY)
scheduler = Scheduler(config.DATA_DIR)
state = State(config.DATA_DIR)

tz = pytz.timezone(config.TZ)


def get_ip_location(ip: str | None) -> str:
    """Fetch real-time geolocation from free ipapi.co API"""
    if not ip:
        return "unknown"
    try:
        r = requests.get(f"https://ipapi.co/{ip}/json/", timeout=5)
        r.raise_for_status()
        data = r.json()
        city = data.get("city", "Unknown")
        region = data.get("region", "")
        country = data.get("country_name", "Unknown")
        if city != "Unknown" and region:
            return f"{city}, {region}, {country}"
        elif city != "Unknown":
            return f"{city}, {country}"
        else:
            return country
    except Exception as e:
        logger.warning("IP geolocation lookup failed", ip=ip, error=str(e))
        return "lookup failed"


def get_exit_location_fallback(ip: str | None) -> str:
    """Fallback heuristic for Proton free/common ranges"""
    if not ip:
        return "unknown"
    mapping = {
        "37.19.": "Poland / Romania",
        "37.120.": "Netherlands",
        "185.220.": "United States / Tor mix",
        "185.": "Netherlands / various",
        "146.70.": "Switzerland / Romania",
        "209.127.": "United States",
        "45.": "Various (US/CA/JP/SG)",
        # Add more prefixes as you observe reconnects
    }
    for prefix, loc in mapping.items():
        if ip.startswith(prefix):
            return loc
    return f"{ip} (ProtonVPN exit - country unknown)"


def get_exit_location(ip: str | None) -> str:
    """Preferred: API lookup → fallback heuristic"""
    api_loc = get_ip_location(ip)
    if api_loc != "lookup failed":
        return api_loc
    return get_exit_location_fallback(ip)


def log_poll_summary(
    mode: str,
    lat_ms: int | None,
    speed_mbps: float | None,
    consecutive_bad: int,
    cb_count: int,
    cb_tripped: bool,
    resets_hour: int,
    ip: str | None,
):
    lat_str = f"{lat_ms} ms" if lat_ms is not None else "N/A"
    speed_str = f"{speed_mbps:.1f} Mbps" if speed_mbps is not None else "N/A"

    if lat_ms is None or lat_ms >= config.LATENCY_WARN_MS:
        status_icon = "⚠️" if consecutive_bad > 0 else "❌"
    else:
        status_icon = "✅"

    cb_status = "🔒 TRIPPED" if cb_tripped else f"{cb_count}/{config.CIRCUIT_BREAKER_THRESHOLD}"

    logger.info(
        f"Poll  {mode:<9}  {status_icon}  "
        f"lat={lat_str:<9}  speed={speed_str:<11}  "
        f"bad={consecutive_bad}/{config.LATENCY_CONSECUTIVE_HITS}  "
        f"CB={cb_status}  resets/hr={resets_hour}  "
        f"IP={ip or 'unknown'}"
    )


def wait_for_gluetun():
    logger.info("Waiting for gluetun control API... 🔌")

    attempts = 0
    while True:
        attempts += 1
        status = gluetun.get_vpn_status()
        if status is not None:
            logger.info("Gluetun API ready ✓")
            break
        if attempts % 10 == 0:
            logger.info(f"API still not responding... ({attempts} attempts)")
        time.sleep(3)

    logger.info("Waiting for VPN tunnel to become active... ⏳")

    attempts = 0
    while True:
        attempts += 1
        status = gluetun.get_vpn_status()
        if status and status.get("status") == "running":
            ip = gluetun.get_public_ip()
            if ip:
                state.data["last_exit_ip"] = ip
                state.save()
                location = get_exit_location(ip)
                now_str = datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S %Z")

                logger.info(
                    "VPN tunnel UP ✓",
                    status="running",
                    public_ip=ip,
                    exit_location=location,
                    time=now_str
                )

                # Send Pushover notification on successful startup
                startup_msg = (
                    "VPN Monitor started successfully\n"
                    f"Exit IP: {ip}\n"
                    f"Location: {location}\n"
                    f"Time: {now_str}"
                )
                send_pushover(
                    config.PUSHOVER_USER,
                    config.PUSHOVER_TOKEN,
                    startup_msg,
                    priority=-1,   # low priority (no sound/alert by default)
                    sound="none"   # silent; change to "pushover" or "magic" if desired
                )

                break

        if attempts % 5 == 0:
            logger.info(f"VPN still connecting... ({attempts} checks)")
        time.sleep(3)

    logger.info("Startup sequence complete 🚀")


def monitor_loop():
    consecutive_bad = state.data["consecutive_bad_latency"]

    while True:
        now_str = datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S %Z")
        mode = scheduler.current_mode()

        if mode == "BLOCKED":
            logger.info(f"[{now_str}] Schedule BLOCKED — skipping checks")
            time.sleep(config.POLL_INTERVAL_SECONDS)
            continue

        if state.data["circuit_breaker_tripped"]:
            logger.warning(f"[{now_str}] Circuit breaker active — monitoring only")
            time.sleep(config.POLL_INTERVAL_SECONDS)
            continue

        lat_ms, vpn_down = measure_latency()
        state.data["last_latency_ms"] = lat_ms
        speed_mbps = None

        bad = False
        if vpn_down:
            logger.error("Both pings failed — assuming VPN down ❌")
            bad = True
        elif lat_ms is not None:
            if lat_ms >= config.LATENCY_CRIT_MS:
                logger.warning("Critical latency", ms=lat_ms)
            if lat_ms >= config.LATENCY_WARN_MS:
                consecutive_bad += 1
                if consecutive_bad >= config.LATENCY_CONSECUTIVE_HITS:
                    bad = True
            else:
                consecutive_bad = 0

        state.data["consecutive_bad_latency"] = consecutive_bad

        # Always show clean poll summary
        log_poll_summary(
            mode=mode,
            lat_ms=lat_ms,
            speed_mbps=speed_mbps,
            consecutive_bad=consecutive_bad,
            cb_count=state.data["circuit_breaker_count"],
            cb_tripped=state.data["circuit_breaker_tripped"],
            resets_hour=state.data["resets_this_hour"],
            ip=state.data["last_exit_ip"],
        )

        if bad:
            if mode == "QUIET":
                logger.info("Congestion in QUIET mode — logging only")
                state.save()
                time.sleep(config.POLL_INTERVAL_SECONDS)
                continue

            can_reset, reason = state.can_reset(config.MIN_RECONNECT_MINUTES, config.MAX_RESETS_PER_HOUR)
            if not can_reset:
                logger.info(f"Reset skipped: {reason}")
                notify_reset_deferred(reason)
                time.sleep(config.POLL_INTERVAL_SECONDS)
                continue

            old_ip = state.data["last_exit_ip"] or "unknown"
            notify_reset_triggered(lat_ms or 9999, speed_mbps)

            if lat_ms is not None and lat_ms >= config.LATENCY_WARN_MS:
                speed_mbps = measure_speed()
                state.data["last_speed_mbps"] = speed_mbps
                if speed_mbps is not None and speed_mbps >= config.SPEED_MIN_MBPS:
                    logger.info("Speed test passed — likely false positive ✓", mbps=speed_mbps)
                    consecutive_bad = 0
                    state.data["consecutive_bad_latency"] = 0
                    state.save()
                    time.sleep(config.POLL_INTERVAL_SECONDS)
                    continue

            logger.info("Executing VPN cycle... 🔄")
            gluetun.set_vpn_status("stopped")
            time.sleep(3)
            gluetun.set_vpn_status("running")

            start = time.monotonic()
            new_ip = None
            while time.monotonic() - start < config.RECONNECT_TIMEOUT_SECONDS:
                status = gluetun.get_vpn_status()
                if status and status.get("status") == "running":
                    new_ip = gluetun.get_public_ip()
                    if new_ip and new_ip != old_ip:
                        break
                time.sleep(5)

            success = bool(new_ip and new_ip != old_ip)

            state.record_reset_attempt(success, new_ip)

            if success:
                location_new = get_exit_location(new_ip)
                logger.info(
                    "Reset successful ✓",
                    old_ip=old_ip,
                    new_ip=new_ip,
                    new_location=location_new
                )
                notify_reset_success(old_ip, new_ip)
            else:
                if new_ip:
                    logger.warning("Reset completed — IP unchanged", ip=new_ip)
                    notify_reset_same_ip(new_ip)
                else:
                    logger.error("VPN failed to reconnect in time ❌")
                if state.data["circuit_breaker_tripped"]:
                    logger.critical("Circuit breaker TRIPPED — auto-reset suspended")
                    notify_circuit_breaker_tripped()

        else:
            consecutive_bad = 0
            state.data["consecutive_bad_latency"] = 0

        state.save()
        time.sleep(config.POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    logger.info("VPN Monitor starting", config=dict(config.__dict__))
    wait_for_gluetun()
    monitor_loop()
