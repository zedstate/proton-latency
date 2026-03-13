import time
from datetime import datetime
import pytz

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
)

logger = setup_logging()
config = Config()
config.validate()

gluetun = GluetunClient(config.GLUETUN_API, config.GLUETUN_API_KEY)
scheduler = Scheduler(config.DATA_DIR)
state = State(config.DATA_DIR)

tz = pytz.timezone(config.TZ)

def wait_for_gluetun():
    logger.info("Waiting for gluetun control API...")
    while True:
        status = gluetun.get_vpn_status()
        if status is not None:
            break
        time.sleep(3)

    logger.info("gluetun API ready, waiting for VPN running...")
    while True:
        status = gluetun.get_vpn_status()
        if status and status.get("status") == "running":
            ip = gluetun.get_public_ip()
            if ip:
                state.data["last_exit_ip"] = ip
                state.save()
                break
        time.sleep(3)

    logger.info("Startup complete", initial_ip=state.data["last_exit_ip"])

def monitor_loop():
    consecutive_bad = state.data["consecutive_bad_latency"]

    while True:
        now_str = datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S %Z")
        mode = scheduler.current_mode()
        logger.info("Poll", time=now_str, mode=mode)

        if mode == "BLOCKED":
            time.sleep(config.POLL_INTERVAL_SECONDS)
            continue

        if state.data["circuit_breaker_tripped"]:
            logger.warning("Circuit breaker active — skipping checks")
            time.sleep(config.POLL_INTERVAL_SECONDS)
            continue

        lat_ms, vpn_down = measure_latency()
        state.data["last_latency_ms"] = lat_ms
        speed_mbps = None

        bad = False
        if vpn_down:
            logger.error("Both pings failed — assuming VPN down")
            bad = True
        elif lat_ms is not None:
            crit = lat_ms >= config.LATENCY_CRIT_MS
            warn = lat_ms >= config.LATENCY_WARN_MS
            if crit:
                logger.warning("Critical latency", ms=lat_ms)
            if warn:
                logger.info("High latency", ms=lat_ms)
                consecutive_bad += 1
                if consecutive_bad >= config.LATENCY_CONSECUTIVE_HITS:
                    bad = True
            else:
                consecutive_bad = 0

        state.data["consecutive_bad_latency"] = consecutive_bad

        if bad:
            if mode == "QUIET":
                logger.info("Congestion detected in QUIET mode — logging only")
                state.save()
                time.sleep(config.POLL_INTERVAL_SECONDS)
                continue

            # MONITOR mode → check preconditions
            can_reset, reason = state.can_reset(config.MIN_RECONNECT_MINUTES, config.MAX_RESETS_PER_HOUR)
            if not can_reset:
                logger.info("Reset skipped", reason=reason)
                notify_reset_deferred(reason)
                time.sleep(config.POLL_INTERVAL_SECONDS)
                continue

            # Trigger reset
            old_ip = state.data["last_exit_ip"] or "unknown"
            notify_reset_triggered(lat_ms or 9999, speed_mbps)

            if lat_ms is not None and lat_ms >= config.LATENCY_WARN_MS:
                # Only run speedtest if latency triggered it
                speed_mbps = measure_speed()
                state.data["last_speed_mbps"] = speed_mbps
                if speed_mbps is not None and speed_mbps >= config.SPEED_MIN_MBPS:
                    logger.info("Speed test passed despite high latency — false positive?")
                    consecutive_bad = 0
                    state.data["consecutive_bad_latency"] = 0
                    state.save()
                    time.sleep(config.POLL_INTERVAL_SECONDS)
                    continue

            logger.info("Executing VPN cycle...")
            gluetun.set_vpn_status("stopped")
            time.sleep(3)
            gluetun.set_vpn_status("running")

            # Wait for reconnect
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
                logger.info("Reset successful", old_ip=old_ip, new_ip=new_ip)
                notify_reset_success(old_ip, new_ip)
            else:
                if new_ip:
                    logger.warning("Reset completed but IP same", ip=new_ip)
                    notify_reset_same_ip(new_ip)
                else:
                    logger.error("VPN failed to reconnect in time")
                if state.data["circuit_breaker_tripped"]:
                    notify_circuit_breaker_tripped()

        else:
            consecutive_bad = 0
            state.data["consecutive_bad_latency"] = 0

        state.save()
        time.sleep(config.POLL_INTERVAL_SECONDS)

if __name__ == "__main__":
    setup_logging()
    logger.info("VPN Monitor starting", config=dict(config.__dict__))
    wait_for_gluetun()
    monitor_loop()
