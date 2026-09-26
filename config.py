import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# Tournament Settings
TOURNAMENT_ID = 2169387
TOURNAMENT_NAME = "VLV Ganapti Mens Cricket Tournament 2026"
TOURNAMENT_SLUG = "vlv-ganapti-mens-cricket-tournament-2026"
BASE_URL = f"https://cricheroes.com/tournament/{TOURNAMENT_ID}/{TOURNAMENT_SLUG}"

# Server Settings
HOST = "0.0.0.0"
PORT = int(os.environ.get("PORT", 8008))

# Polling & Ingestion Intervals (in seconds)
LIVE_POLL_INTERVAL = 12         # 12 seconds when match is live for fast ball-by-ball updates
IDLE_POLL_INTERVAL = 120        # 2 minutes when idle/upcoming

# Data Directory
DATA_DIR = BASE_DIR / "data"
STATE_FILE = DATA_DIR / "tournament_state.json"

# Ensure directories exist
DATA_DIR.mkdir(parents=True, exist_ok=True)
