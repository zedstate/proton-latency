import requests
from typing import Optional, Dict, Any

class GluetunClient:
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip("/")
        self.headers = {"X-API-Key": api_key}

    def get_vpn_status(self) -> Optional[Dict[str, Any]]:
        try:
            r = requests.get(f"{self.base_url}/v1/vpn/status", headers=self.headers, timeout=5)
            r.raise_for_status()
            return r.json()
        except requests.exceptions.RequestException:
            return None

    def set_vpn_status(self, status: str) -> bool:
        try:
            r = requests.put(
                f"{self.base_url}/v1/vpn/status",
                json={"status": status},
                headers=self.headers,
                timeout=10,
            )
            return r.status_code in (200, 204)
        except requests.exceptions.RequestException:
            return False

    def get_public_ip(self) -> Optional[str]:
        try:
            r = requests.get(f"{self.base_url}/v1/publicip/ip", headers=self.headers, timeout=5)
            r.raise_for_status()
            return r.json().get("public_ip")
        except requests.exceptions.RequestException:
            return None
