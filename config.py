import os
from dataclasses import dataclass
from typing import Optional

@dataclass
class Config:
    GLUETUN_API: str = os.getenv("GLUETUN_API", "http://127.0.0.1:8000")
    GLUETUN_API_KEY: str = os.getenv("GLUETUN_API_KEY", "")
    
    PUSHOVER_TOKEN: Optional[str] = os.getenv("PUSHOVER_TOKEN") or None
    PUSHOVER_USER: Optional[str] = os.getenv("PUSHOVER_USER") or None
    
    LATENCY_WARN_MS: int = int(os.getenv("LATENCY_WARN_MS", "150"))
    LATENCY_CRIT_MS: int = int(os.getenv("LATENCY_CRIT_MS", "200"))
    LATENCY_CONSECUTIVE_HITS: int = int(os.getenv("LATENCY_CONSECUTIVE_HITS", "2"))
    
    SPEED_MIN_MBPS: float = float(os.getenv("SPEED_MIN_MBPS", "15.0"))
    
    MIN_RECONNECT_MINUTES: int = int(os.getenv("MIN_RECONNECT_MINUTES", "60"))
    MAX_RESETS_PER_HOUR: int = int(os.getenv("MAX_RESETS_PER_HOUR", "1"))
    CIRCUIT_BREAKER_THRESHOLD: int = int(os.getenv("CIRCUIT_BREAKER_THRESHOLD", "3"))
    
    POLL_INTERVAL_SECONDS: int = int(os.getenv("POLL_INTERVAL_SECONDS", "60"))
    RECONNECT_TIMEOUT_SECONDS: int = int(os.getenv("RECONNECT_TIMEOUT_SECONDS", "60"))
    
    TZ: str = os.getenv("TZ", "America/New_York")
    DATA_DIR: str = "/data"

    def validate(self):
        if not self.GLUETUN_API_KEY:
            raise ValueError("GLUETUN_API_KEY is required")
