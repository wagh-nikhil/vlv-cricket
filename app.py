import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

import config
import socket
from services.cricheroes_client import CricHeroesClient
from services.poster_generator import PosterGenerator
from services.whatsapp_dispatcher import WhatsAppDispatcher
from services.match_simulator import simulator_instance
from services.ai_commentator import commentator_instance
from services.tunnel_manager import tunnel_manager

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
app = FastAPI(title="VLV CricHeroes Local Scoreboard & WhatsApp Poster Hub")

from fastapi.middleware.gzip import GZipMiddleware
app.add_middleware(GZipMiddleware, minimum_size=500)

# Mount static and output directories
BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
app.mount("/posters", StaticFiles(directory=str(config.POSTER_DIR)), name="posters")

COMMENTARY_DIR = BASE_DIR / "output" / "commentary"
COMMENTARY_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/commentary", StaticFiles(directory=str(COMMENTARY_DIR)), name="commentary")

# Core services
client = CricHeroesClient()
generator = PosterGenerator()
dispatcher = WhatsAppDispatcher()

# App State
app_state = {
    "live_source": "real_cricheroes", # "real_cricheroes", "tournament_2169387", "simulator"
    "active_match_id": 27123027,      # Real live match in Pune: PUNE MEMON UNITED vs KACHHI ROYALS
    "current_match": None,
    "simulation_mode": False,
    "sim_auto_step": False,
    "sim_speed_seconds": 15,
    "poll_interval": config.LIVE_POLL_INTERVAL,
    "last_poster_path": str(config.POSTER_DIR / "latest_poster.png"),
    "cached_tournament": client.load_cached_state()
}

# Ensure initial poster exists using real live match or simulator
initial_real_match = client.fetch_live_mini_scorecard(app_state["active_match_id"])
app_state["current_match"] = initial_real_match
if initial_real_match:
    generator.generate_poster(initial_real_match, "latest_poster.png")
elif not (config.POSTER_DIR / "latest_poster.png").exists():
    sim_state = simulator_instance.get_state()
    app_state["current_match"] = sim_state
    generator.generate_poster(sim_state, "latest_poster.png")

# Request Models
class WhatsAppSettingsUpdate(BaseModel):
    enabled: bool
    group_name: str
    cadence: str # "1min_delta" or "over_end"
    webhook_url: str = ""

class MatchSelectRequest(BaseModel):
    match_id: int
    source: str = "real_cricheroes"

class SimSettingsUpdate(BaseModel):
    enabled: bool
    auto_step: bool
    speed_seconds: int = 15

# Background worker for 1-minute automated polling & poster generation
async def background_poller():
    """Periodic task that checks live match state, generates posters, and dispatches to WhatsApp."""
    logger.info("Starting background poller loop...")
    while True:
        try:
            current_match = None

            if app_state["live_source"] == "real_cricheroes":
                # Real live match from CricHeroes
                current_match = await asyncio.to_thread(client.fetch_live_mini_scorecard, app_state["active_match_id"])
            elif app_state["live_source"] == "simulator" or app_state["simulation_mode"]:
                if app_state["sim_auto_step"]:
                    current_match = simulator_instance.bowl_next_ball()
                else:
                    current_match = simulator_instance.get_state()
            else:
                # Poll tournament 2169387
                live_matches = await asyncio.to_thread(client.fetch_live_matches_tab)
                if live_matches:
                    current_match = live_matches[0]
                else:
                    cached = await asyncio.to_thread(client.load_cached_state)
                    app_state["cached_tournament"] = cached

            if current_match:
                app_state["current_match"] = current_match
                # Check delta & should dispatch
                allowed, reason = dispatcher.should_dispatch(current_match)
                if allowed:
                    over_str = str(current_match.get("overs", "0.0")).replace(".", "_")
                    filename = f"poster_{current_match.get('match_id', 'live')}_{over_str}.png"
                    poster_path = await asyncio.to_thread(generator.generate_poster, current_match, filename)
                    app_state["last_poster_path"] = poster_path

                    if config.WHATSAPP_ENABLED:
                        await asyncio.to_thread(dispatcher.dispatch, current_match, poster_path)
                    else:
                        logger.info(f"Live CricHeroes poster updated: {filename}")

            sleep_duration = app_state["sim_speed_seconds"] if app_state["live_source"] == "simulator" else config.LIVE_POLL_INTERVAL
            await asyncio.sleep(sleep_duration)

        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Error in background poller: {e}")
            await asyncio.sleep(10)

@app.on_event("startup")
async def startup_event():
    # Sync tournament state if not cached
    if not app_state["cached_tournament"]:
        try:
            app_state["cached_tournament"] = await asyncio.to_thread(client.sync_all)
        except Exception as e:
            logger.warning(f"Initial sync warning: {e}")
    
    # Launch background poller task
    asyncio.create_task(background_poller())

# HTML Route
@app.get("/", response_class=HTMLResponse)
async def index_page(request: Request):
    current_match = app_state.get("current_match")
    if not current_match:
        if app_state["live_source"] == "real_cricheroes":
            current_match = await asyncio.to_thread(client.fetch_live_mini_scorecard, app_state["active_match_id"])
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

# Ticker Overlay Routes for PRISM Live Studio & Broadcast Streaming
@app.get("/ticker", response_class=HTMLResponse)
@app.get("/overlay", response_class=HTMLResponse)
async def ticker_overlay_page(request: Request):
    """Broadcast-quality transparent cricket ticker lower-third for PRISM Live Studio & streaming tools."""
    current_match = app_state.get("current_match") or {}
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
@app.get("/api/network-info")
async def get_network_info():
    """Returns local LAN IP, local ticker URL, and active Cloudflare tunnel URL."""
    lan_ip = get_lan_ip()
    tunnel_status = tunnel_manager.get_status()
    local_url = f"http://{lan_ip}:{config.PORT}/ticker"
    
    return {
        "lan_ip": lan_ip,
        "port": config.PORT,
        "local_ticker_url": local_url,
        "local_dashboard_url": f"http://{lan_ip}:{config.PORT}",
        "tunnel": tunnel_status
    }

@app.post("/api/tunnel/start")
async def start_tunnel():
    """Starts a Cloudflare quick tunnel for 4G/5G mobile outdoor streaming."""
    res = await asyncio.to_thread(tunnel_manager.start)
    return res

@app.post("/api/tunnel/stop")
async def stop_tunnel():
    """Stops the active Cloudflare tunnel."""
    res = await asyncio.to_thread(tunnel_manager.stop)
    return res

@app.get("/api/tunnel/status")
async def get_tunnel_status():
    """Checks the status of the Cloudflare tunnel."""
    return tunnel_manager.get_status()

@app.get("/api/state")
async def get_full_state():
    """Returns overall server and tournament state."""
    current_match = app_state.get("current_match")
    
    return {
        "live_source": app_state["live_source"],
        "active_match_id": app_state["active_match_id"],
        "simulation_mode": app_state["live_source"] == "simulator",
        "sim_auto_step": app_state["sim_auto_step"],
        "sim_speed_seconds": app_state["sim_speed_seconds"],
        "whatsapp_enabled": config.WHATSAPP_ENABLED,
        "whatsapp_cadence": config.WHATSAPP_CADENCE,
        "whatsapp_group": config.WHATSAPP_GROUP_NAME,
        "current_match": current_match,
        "latest_poster_url": "/posters/latest_poster.png",
        "last_synced": app_state["cached_tournament"].get("last_synced")
    }

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
    else:
        app_state["simulation_mode"] = False
    
    # Generate immediate poster for newly selected match
    if req.source == "real_cricheroes":
        match_data = await asyncio.to_thread(client.fetch_live_mini_scorecard, req.match_id)
        if match_data:
            app_state["current_match"] = match_data
            await asyncio.to_thread(generator.generate_poster, match_data, "latest_poster.png")
            return {"status": "success", "match": match_data}
    elif req.source == "simulator":
        sim_data = simulator_instance.get_state()
        app_state["current_match"] = sim_data
        await asyncio.to_thread(generator.generate_poster, sim_data, "latest_poster.png")
        return {"status": "success", "match": sim_data}
        
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

@app.post("/api/poster/generate")
async def manual_generate_poster():
    """Generates a poster on demand and returns the image URL."""
    match = None
    if app_state["live_source"] == "real_cricheroes":
        match = await asyncio.to_thread(client.fetch_live_mini_scorecard, app_state["active_match_id"])
    elif app_state["live_source"] == "simulator":
        match = simulator_instance.get_state()
    
    if not match:
        live = await asyncio.to_thread(client.fetch_live_matches_tab)
        match = live[0] if live else simulator_instance.get_state()

    path = await asyncio.to_thread(generator.generate_poster, match, "latest_poster.png")
    app_state["last_poster_path"] = path
    return {"status": "success", "url": "/posters/latest_poster.png", "timestamp": datetime.now().isoformat()}

@app.get("/api/poster/latest")
async def get_latest_poster():
    latest = config.POSTER_DIR / "latest_poster.png"
    if latest.exists():
        return FileResponse(str(latest), media_type="image/png")
    return JSONResponse({"error": "No poster generated yet"}, status_code=404)

@app.get("/api/posters/history")
async def get_poster_history():
    return dispatcher.history

@app.post("/api/whatsapp/dispatch")
async def manual_dispatch_whatsapp(force: bool = True):
    """Dispatches current live score poster and caption to WhatsApp."""
    match = None
    if app_state["live_source"] == "real_cricheroes":
        match = await asyncio.to_thread(client.fetch_live_mini_scorecard, app_state["active_match_id"])
    elif app_state["live_source"] == "simulator":
        match = simulator_instance.get_state()

    if not match:
        live = await asyncio.to_thread(client.fetch_live_matches_tab)
        match = live[0] if live else simulator_instance.get_state()

    poster_path = await asyncio.to_thread(generator.generate_poster, match, "latest_poster.png")
    res = await asyncio.to_thread(dispatcher.dispatch, match, poster_path, force=force)
    return res

@app.post("/api/whatsapp/settings")
async def update_whatsapp_settings(settings: WhatsAppSettingsUpdate):
    config.WHATSAPP_ENABLED = settings.enabled
    config.WHATSAPP_GROUP_NAME = settings.group_name
    config.WHATSAPP_CADENCE = settings.cadence
    config.WHATSAPP_WEBHOOK_URL = settings.webhook_url
    return {"status": "success", "settings": settings.dict()}

@app.post("/api/simulator/toggle")
async def toggle_simulator(settings: SimSettingsUpdate):
    app_state["simulation_mode"] = settings.enabled
    app_state["sim_auto_step"] = settings.auto_step
    app_state["sim_speed_seconds"] = settings.speed_seconds
    return {"status": "success", "simulation_mode": app_state["simulation_mode"]}

@app.post("/api/simulator/next-ball")
async def sim_next_ball():
    state = simulator_instance.bowl_next_ball()
    generator.generate_poster(state, "latest_poster.png")
    return state

@app.post("/api/simulator/next-over")
async def sim_next_over():
    for _ in range(6):
        state = simulator_instance.bowl_next_ball()
    generator.generate_poster(state, "latest_poster.png")
    return state

@app.post("/api/simulator/reset")
async def sim_reset():
    simulator_instance.reset()
    state = simulator_instance.get_state()
    generator.generate_poster(state, "latest_poster.png")
    return state

@app.post("/api/sync")
async def manual_sync_cricheroes():
    """Forces an immediate sync with CricHeroes."""
    state = await asyncio.to_thread(client.sync_all)
    app_state["cached_tournament"] = state
    return {"status": "success", "matches": len(state.get("upcoming_matches", [])), "teams": len(state.get("teams", []))}

@app.get("/api/commentary/latest")
async def get_latest_commentary():
    """Returns latest commentary text and audio URL."""
    audio_path = COMMENTARY_DIR / "latest_commentary.mp3"
    audio_url = f"/commentary/latest_commentary.mp3?t={audio_path.stat().st_mtime}" if audio_path.exists() else None
    return {
        "text": commentator_instance.last_text or "Live commentary ready.",
        "audio_url": audio_url
    }

@app.post("/api/commentary/generate")
async def manual_generate_commentary():
    """Forces generation of new commentary for current match."""
    match = app_state.get("current_match")
    if match:
        res = await commentator_instance.generate_live_commentary(match, force=True)
        return res
    return {"status": "error", "message": "No active match"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=config.HOST, port=config.PORT)
