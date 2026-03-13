import subprocess
import json
from typing import Tuple, Optional
import time

def run_ping(host: str, count: int = 5, timeout: int = 2) -> Tuple[Optional[float], bool]:
    """Returns (max_rtt_ms, has_packet_loss)"""
    cmd = ["ping", "-c", str(count), "-W", str(timeout), host]
    try:
        output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True, timeout=15)
        lines = output.splitlines()
        rtts = []
        received = 0
        for line in lines:
            if "time=" in line:
                rtt_str = line.split("time=")[1].split(" ms")[0]
                rtts.append(float(rtt_str))
            if "received" in line:
                received = int(line.split("received,")[0].split()[-1])
        
        if not rtts:
            return None, True
        
        max_rtt = max(rtts)
        packet_loss = received < count
        return max_rtt, packet_loss
    
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return None, True

def measure_latency() -> Tuple[Optional[int], bool]:  # latency_ms or None, is_vpn_down
    hosts = ["1.1.1.1", "8.8.8.8"]
    max_rtts = []
    any_loss = False
    all_failed = True

    for host in hosts:
        max_rtt, loss = run_ping(host)
        if max_rtt is not None:
            all_failed = False
            max_rtts.append(max_rtt)
        if loss:
            any_loss = True

    if all_failed:
        return None, True  # both completely failed → assume VPN down

    if not max_rtts:
        return None, False

    final_latency = int(max(max_rtts))  # worst-case spike matters for streaming
    return final_latency, any_loss

def measure_speed() -> Optional[float]:
    """Returns Mbps download or None on failure"""
    try:
        output = subprocess.check_output(
            ["speedtest", "--accept-license", "--format=json", "--progress=no"],
            stderr=subprocess.STDOUT,
            text=True,
            timeout=90,
        )
        data = json.loads(output)
        return float(data["download"]["bandwidth"]) / 1_000_000  # bytes/s → Mbps
    except Exception:
        return None
