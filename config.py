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

# WhatsApp Dispatch Settings
WHATSAPP_ENABLED = False        # Toggle auto-dispatch
WHATSAPP_CADENCE = "1min_delta" # "1min_delta" (only if score changed) or "over_end" (end of overs)
WHATSAPP_GROUP_NAME = "VLV Cricket 2026"
WHATSAPP_WEBHOOK_URL = ""       # Optional: External WhatsApp Webhook / Gateway
WHATSAPP_COOLDOWN_SECONDS = 50  # Prevent spamming within 50 seconds

# Data & Output Directories
DATA_DIR = BASE_DIR / "data"
POSTER_DIR = BASE_DIR / "output" / "posters"
STATE_FILE = DATA_DIR / "tournament_state.json"
POSTER_HISTORY_FILE = DATA_DIR / "poster_history.json"
SETTINGS_FILE = DATA_DIR / "settings.json"

# Ensure directories exist
DATA_DIR.mkdir(parents=True, exist_ok=True)
POSTER_DIR.mkdir(parents=True, exist_ok=True)
