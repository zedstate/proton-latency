import json
import os
from datetime import datetime
import pytz
from typing import Literal

Mode = Literal["MONITOR", "QUIET", "BLOCKED"]

DEFAULT_GRID = [
    # Mon-Sun, each 24 entries (00-23)
    ["MONITOR"] * 24,  # Sunday
    ["MONITOR"] * 17 + ["BLOCKED"] * 1 + ["MONITOR"] * 4 + ["BLOCKED"] * 1 + ["MONITOR"] * 1,  # Monday: BLOCKED 17-18 & 22-23
    ["MONITOR"] * 17 + ["BLOCKED"] * 1 + ["MONITOR"] * 4 + ["BLOCKED"] * 1 + ["MONITOR"] * 1,  # Tuesday
    ["MONITOR"] * 17 + ["BLOCKED"] * 1 + ["MONITOR"] * 4 + ["BLOCKED"] * 1 + ["MONITOR"] * 1,  # Wednesday
    ["MONITOR"] * 17 + ["BLOCKED"] * 1 + ["MONITOR"] * 4 + ["BLOCKED"] * 1 + ["MONITOR"] * 1,  # Thursday
    ["MONITOR"] * 17 + ["BLOCKED"] * 1 + ["MONITOR"] * 4 + ["BLOCKED"] * 1 + ["MONITOR"] * 1,  # Friday
    ["MONITOR"] * 24,  # Saturday
]

class Scheduler:
    def __init__(self, data_dir: str):
        self.path = os.path.join(data_dir, "schedule.json")
        self.grid: list[list[Mode]] = self._load_or_create()

    def _load_or_create(self) -> list[list[Mode]]:
        if os.path.exists(self.path):
            with open(self.path, "r") as f:
                data = json.load(f)
                return data["grid"]
        # Create default
        with open(self.path, "w") as f:
            json.dump({"grid": DEFAULT_GRID}, f, indent=2)
        return DEFAULT_GRID

    def current_mode(self) -> Mode:
        tz = pytz.timezone("America/New_York")
        now = datetime.now(tz)
        weekday = now.weekday()          # 0=Mon ... 6=Sun
        hour = now.hour
        return self.grid[weekday][hour]
