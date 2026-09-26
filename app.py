import asyncio
import json
import logging
import socket
from pathlib import Path
from typing import Dict, Any

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.gzip import GZipMiddleware
from pydantic import BaseModel

import config
from services.cricheroes_client import CricHeroesClient
from services.match_simulator import simulator_instance

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("app")

def get_lan_ip() -> str:
    """Discovers host LAN IPv4 address."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

# Initialize FastAPI App
app = FastAPI(title="VLV CricHeroes Live Scoreboard")
app.add_middleware(GZipMiddleware, minimum_size=500)

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

# Core CricHeroes Client
client = CricHeroesClient()

# In-Memory App State
app_state = {
    "live_source": "real_cricheroes", # "real_cricheroes", "tournament_2169387", "simulator"
    "active_match_id": 27016163,      # Default to Match 1 (F Wing vs A wing)
    "current_match": None,
    "simulation_mode": False,
    "sim_auto_step": False,
    "sim_speed_seconds": 15,
    "poll_interval": config.LIVE_POLL_INTERVAL,
    "cached_tournament": client.load_cached_state()
}

# Request Models
class MatchSelectRequest(BaseModel):
    match_id: int
    source: str = "real_cricheroes"

class SimSettingsUpdate(BaseModel):
    enabled: bool
    auto_step: bool
    speed_seconds: int = 15

# Lightweight background poller: polls live score into memory every 12s
async def background_poller():
    """Periodic task that checks live match state and keeps in-memory score up to date."""
    logger.info("Starting lightweight score poller loop...")
    while True:
        try:
            current_match = None

            if app_state["live_source"] == "real_cricheroes":
                current_match = await asyncio.to_thread(client.fetch_live_mini_scorecard, app_state["active_match_id"])
                if not current_match:
                    current_match = client.get_match_by_id(app_state["active_match_id"])
            elif app_state["live_source"] == "simulator" or app_state["simulation_mode"]:
                if app_state["sim_auto_step"]:
                    current_match = simulator_instance.bowl_next_ball()
                else:
                    current_match = simulator_instance.get_state()
            else:
                # Tournament auto-monitor
                live_matches = await asyncio.to_thread(client.fetch_live_matches_tab)
                if live_matches:
                    current_match = live_matches[0]
                else:
                    cached = await asyncio.to_thread(client.load_cached_state)
                    app_state["cached_tournament"] = cached

            if current_match:
                app_state["current_match"] = current_match

            sleep_duration = app_state["sim_speed_seconds"] if app_state["live_source"] == "simulator" else config.LIVE_POLL_INTERVAL
            await asyncio.sleep(sleep_duration)

        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Error in score poller: {e}")
            await asyncio.sleep(10)

@app.on_event("startup")
async def startup_event():
    # Sync tournament state if not cached
    if not app_state["cached_tournament"]:
        try:
            app_state["cached_tournament"] = await asyncio.to_thread(client.sync_all)
        except Exception as e:
            logger.warning(f"Initial sync warning: {e}")
    
    # Launch lightweight background poller task
    asyncio.create_task(background_poller())

# HTML Route: Main Dashboard
@app.get("/", response_class=HTMLResponse)
async def index_page(request: Request):
    current_match = app_state.get("current_match")
    if not current_match:
        if app_state["live_source"] == "real_cricheroes":
            current_match = await asyncio.to_thread(client.fetch_live_mini_scorecard, app_state["active_match_id"])
            if not current_match:
                current_match = client.get_match_by_id(app_state["active_match_id"])
        elif app_state["live_source"] == "simulator":
            current_match = simulator_instance.get_state()
        app_state["current_match"] = current_match

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "tournament": app_state["cached_tournament"].get("tournament", {}),
            "current_match": current_match or {},
            "live_source": app_state["live_source"],
            "active_match_id": app_state["active_match_id"],
            "config": config
        }
    )

# HTML Route: PRISM Live Transparent Camera Ticker Overlay
@app.get("/ticker", response_class=HTMLResponse)
@app.get("/overlay", response_class=HTMLResponse)
async def ticker_overlay_page(request: Request):
    """Broadcast-quality transparent cricket ticker lower-third for PRISM Live Studio & streaming."""
    current_match = app_state.get("current_match")
    if not current_match:
        current_match = client.get_match_by_id(app_state["active_match_id"]) or {}
    tournament = app_state["cached_tournament"].get("tournament", {})
    return templates.TemplateResponse(
        request=request,
        name="ticker.html",
        context={
            "tournament_name": tournament.get("name") or config.TOURNAMENT_NAME,
            "current_match": current_match
        }
    )

# API Routes
@app.get("/api/state")
async def get_full_state():
    """Returns overall server and tournament state."""
    return {
        "live_source": app_state["live_source"],
        "active_match_id": app_state["active_match_id"],
        "simulation_mode": app_state["live_source"] == "simulator",
        "sim_auto_step": app_state["sim_auto_step"],
        "sim_speed_seconds": app_state["sim_speed_seconds"],
        "current_match": app_state.get("current_match"),
        "last_synced": app_state["cached_tournament"].get("last_synced")
    }

@app.get("/api/live/stream")
async def live_stream(request: Request):
    """Server-Sent Events (SSE) stream for zero-latency live score UI updates from memory."""
    async def event_generator():
        while True:
            if await request.is_disconnected():
                break
            
            data = app_state.get("current_match")
            if not data:
                data = {"status": "idle"}

            # Send ping comment to keep mobile connections alive and defeat proxy buffering
            yield f": ping\n\ndata: {json.dumps(data)}\n\n"
            await asyncio.sleep(2)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Content-Type": "text/event-stream",
            "Access-Control-Allow-Origin": "*"
        }
    )

@app.get("/api/live/real-matches")
async def get_real_live_matches():
    """Returns currently ongoing live matches in Pune from CricHeroes."""
    matches = await asyncio.to_thread(client.fetch_live_pune_matches)
    return matches

@app.post("/api/live/select-match")
async def select_live_match(req: MatchSelectRequest):
    """Selects an active live match to track."""
    app_state["active_match_id"] = req.match_id
    app_state["live_source"] = req.source
    if req.source == "simulator":
        app_state["simulation_mode"] = True
        sim_data = simulator_instance.get_state()
        app_state["current_match"] = sim_data
        return {"status": "success", "match": sim_data}
    else:
        app_state["simulation_mode"] = False
        match_data = await asyncio.to_thread(client.fetch_live_mini_scorecard, req.match_id)
        if not match_data:
            match_data = client.get_match_by_id(req.match_id)
        if match_data:
            app_state["current_match"] = match_data
            return {"status": "success", "match": match_data}
        
    return {"status": "success", "active_match_id": req.match_id}

@app.get("/api/tournament")
async def get_tournament():
    """Returns tournament details and upcoming schedule."""
    cached = client.load_cached_state()
    return {
        "tournament": cached.get("tournament", {}),
        "upcoming_matches": cached.get("upcoming_matches", []),
        "teams_count": len(cached.get("teams", [])),
    }

@app.get("/api/teams")
async def get_teams():
    """Returns teams and full squads."""
    cached = client.load_cached_state()
    return cached.get("teams", [])

@app.get("/api/live")
async def get_live():
    """Returns the current live match."""
    return app_state.get("current_match") or {
        "status": "no_live_match",
        "message": "No live match selected."
    }

@app.post("/api/sync")
async def manual_sync_cricheroes():
    """Forces an immediate sync with CricHeroes."""
    state = await asyncio.to_thread(client.sync_all)
    app_state["cached_tournament"] = state
    return {"status": "success", "matches": len(state.get("upcoming_matches", [])), "teams": len(state.get("teams", []))}

# Simulation Routes
@app.post("/api/simulator/toggle")
async def toggle_simulator(settings: SimSettingsUpdate):
    app_state["simulation_mode"] = settings.enabled
    app_state["sim_auto_step"] = settings.auto_step
    app_state["sim_speed_seconds"] = settings.speed_seconds
    return {"status": "success", "simulation_mode": app_state["simulation_mode"]}

@app.post("/api/simulator/next-ball")
async def sim_next_ball():
    state = simulator_instance.bowl_next_ball()
    return state

@app.post("/api/simulator/next-over")
async def sim_next_over():
    for _ in range(6):
        state = simulator_instance.bowl_next_ball()
    return state

@app.post("/api/simulator/reset")
async def sim_reset():
    simulator_instance.reset()
    state = simulator_instance.get_state()
    return state

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=config.HOST, port=config.PORT)
