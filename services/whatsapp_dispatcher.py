import json
import time
import urllib.parse
import logging
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Tuple, Optional
from curl_cffi import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config

logger = logging.getLogger("whatsapp_dispatcher")
logging.basicConfig(level=logging.INFO)

class WhatsAppDispatcher:
    def __init__(self, history_file: Path = config.POSTER_HISTORY_FILE):
        self.history_file = Path(history_file)
        self.last_dispatched_state: Optional[Tuple[int, int, str, str]] = None
        self.last_dispatch_time: float = 0.0
        self.history: list = self._load_history()

    def _load_history(self) -> list:
        if self.history_file.exists():
            try:
                with open(self.history_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return []
        return []

    def _save_history(self):
        try:
            with open(self.history_file, "w", encoding="utf-8") as f:
                json.dump(self.history[-50:], f, indent=2) # keep last 50
        except Exception as e:
            logger.error(f"Error saving history: {e}")

    def format_caption(self, match: Dict[str, Any]) -> str:
        """Creates a clean WhatsApp markdown scorecard summary."""
        team_a = match.get("team_a", "Team A")
        team_b = match.get("team_b", "Team B")
        batting_team = match.get("batting_team", team_a)
        runs = match.get("runs", 0)
        wickets = match.get("wickets", 0)
        overs = match.get("overs", "0.0")
        overs_limit = match.get("overs_limit", 8)
        crr = match.get("crr", "0.00")
        target = match.get("target", "-")
        rrr = match.get("rrr", "-")
        equation = match.get("equation", "")

        batters = match.get("batters", [])
        batters_str = ", ".join([f"{b.get('name')}: {b.get('runs')}({b.get('balls')})" for b in batters[:2]])

        bowler = match.get("bowler", {})
        bowler_str = f"{bowler.get('name')}: {bowler.get('overs')}-{bowler.get('maidens', 0)}-{bowler.get('runs')}-{bowler.get('wickets')}"

        recent_balls = " ".join(match.get("recent_balls", []))

        text = (
            f"🏆 *{match.get('tournament_name', config.TOURNAMENT_NAME)}*\n"
            f"⚔️ *{team_a} vs {team_b}*\n"
            f"🏏 *{batting_team}: {runs}/{wickets}* ({overs}/{overs_limit} ov)\n"
            f"⚡ CRR: {crr}"
        )
        if target and target != "-":
            text += f" | Target: {target} (Req: {rrr})"
        text += (
            f"\n\n🏏 *Batters:* {batters_str}\n"
            f"🎯 *Bowler:* {bowler_str}\n"
            f"⚪ *Recent:* [{recent_balls}]\n"
            f"🔥 *{equation}*\n\n"
            f"📊 _Updated: {datetime.now().strftime('%I:%M %p')}_"
        )
        return text

    def should_dispatch(self, match: Dict[str, Any], force: bool = False) -> Tuple[bool, str]:
        """
        Applies anti-spam and compliance guardrails:
        1. Delta check: skips if score hasn't changed.
        2. Cooldown check: ensures minimum 50s spacing.
        3. Cadence check: obeys over-end vs 1min mode.
        """
        if force:
            return True, "Manual trigger override"

        current_state = (
            match.get("runs", 0),
            match.get("wickets", 0),
            str(match.get("overs", "0.0")),
            str(match.get("status", "live"))
        )

        # 1. Delta Check
        if self.last_dispatched_state == current_state:
            return False, "Score unchanged since last dispatch (delta check passed)"

        # 2. Cooldown Check
        now = time.time()
        elapsed = now - self.last_dispatch_time
        if elapsed < config.WHATSAPP_COOLDOWN_SECONDS:
            remaining = int(config.WHATSAPP_COOLDOWN_SECONDS - elapsed)
            return False, f"Throttled by cooldown ({remaining}s remaining)"

        # 3. Cadence Check
        if config.WHATSAPP_CADENCE == "over_end":
            overs_str = str(match.get("overs", ""))
            if not (overs_str.endswith(".0") and overs_str != "0.0"):
                return False, f"Waiting for end of over (current over: {overs_str})"

        return True, "Ready for dispatch"

    def dispatch(self, match: Dict[str, Any], poster_path: str, force: bool = False) -> Dict[str, Any]:
        """Dispatches scorecard poster and text to configured WhatsApp endpoint or records share link."""
        allowed, reason = self.should_dispatch(match, force=force)
        
        caption = self.format_caption(match)
        encoded_caption = urllib.parse.quote(caption)
        share_url = f"https://api.whatsapp.com/send?text={encoded_caption}"

        record = {
            "timestamp": datetime.now().isoformat(),
            "runs": match.get("runs", 0),
            "wickets": match.get("wickets", 0),
            "overs": match.get("overs", "0.0"),
            "poster_path": poster_path,
            "status": "skipped",
            "reason": reason,
            "caption": caption,
            "share_url": share_url
        }

        if not allowed:
            logger.info(f"WhatsApp Dispatch skipped: {reason}")
            return record

        # Proceed with dispatch
        delivery_success = False
        delivery_note = ""

        if config.WHATSAPP_WEBHOOK_URL:
            try:
                payload = {
                    "group": config.WHATSAPP_GROUP_NAME,
                    "caption": caption,
                    "image_path": poster_path,
                    "match_id": match.get("match_id")
                }
                resp = requests.post(config.WHATSAPP_WEBHOOK_URL, json=payload, timeout=10)
                if resp.status_code in [200, 201]:
                    delivery_success = True
                    delivery_note = f"Sent to Webhook HTTP {resp.status_code}"
                else:
                    delivery_note = f"Webhook error HTTP {resp.status_code}"
            except Exception as e:
                delivery_note = f"Webhook connection error: {e}"
        else:
            delivery_success = True
            delivery_note = "Generated 1-Click WhatsApp Share Link & Poster Ready"

        # Update tracking state
        self.last_dispatched_state = (
            match.get("runs", 0),
            match.get("wickets", 0),
            str(match.get("overs", "0.0")),
            str(match.get("status", "live"))
        )
        self.last_dispatch_time = time.time()

        record["status"] = "success" if delivery_success else "failed"
        record["reason"] = delivery_note

        self.history.append(record)
        self._save_history()

        logger.info(f"WhatsApp Dispatch executed: {delivery_note}")
        return record

# Global dispatcher instance
dispatcher_instance = WhatsAppDispatcher()

if __name__ == "__main__":
    from services.poster_generator import PosterGenerator
    from services.match_simulator import MatchSimulator

    sim = MatchSimulator()
    state = sim.bowl_next_ball()
    gen = PosterGenerator()
    poster = gen.generate_poster(state, "test_dispatch_poster.png")
    disp = WhatsAppDispatcher()
    
    res = disp.dispatch(state, poster, force=True)
    print("Dispatch result:", res["status"], "|", res["reason"])
    print("WhatsApp Caption Preview (Ascii safe):\n", res["caption"].encode('ascii', errors='ignore').decode())
