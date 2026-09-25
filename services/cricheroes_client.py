import json
import re
import logging
from datetime import datetime
from curl_cffi import requests
from typing import Dict, List, Any, Optional
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config

logger = logging.getLogger("cricheroes_client")
logging.basicConfig(level=logging.INFO)

class CricHeroesClient:
    def __init__(self, tournament_id: int = config.TOURNAMENT_ID, slug: str = config.TOURNAMENT_SLUG):
        self.tournament_id = tournament_id
        self.slug = slug
        self.base_tournament_url = f"https://cricheroes.com/tournament/{tournament_id}/{slug}"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }
        self.api_headers = {
            "api-key": "cr!CkH3r0s",
            "device-type": "Chrome: 120.0.0.0",
            "udid": "web-client-session",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Referer": "https://cricheroes.com/",
            "Origin": "https://cricheroes.com"
        }
        self._scorecard_cache: Dict[int, Dict[str, Any]] = {}
        self._scorecard_cache_time: Dict[int, float] = {}
        self._cache_ttl = 10.0  # seconds - fast ball-by-ball refreshes

    def _extract_json_block(self, text: str, key: str) -> Optional[Dict[str, Any]]:
        """Finds and parses a balanced JSON object containing a given key."""
        pos = text.find(f'"{key}":')
        if pos == -1:
            return None
        start = text.rfind('{', 0, pos)
        if start == -1:
            return None
        
        brace_count = 0
        end = start
        for i in range(start, len(text)):
            if text[i] == '{':
                brace_count += 1
            elif text[i] == '}':
                brace_count -= 1
                if brace_count == 0:
                    end = i + 1
                    break
        
        if end > start:
            try:
                return json.loads(text[start:end])
            except Exception as e:
                logger.debug(f"JSON parsing error for key {key}: {e}")
                return None
        return None

    def _get_page_rsc_chunks(self, url: str) -> List[str]:
        """Fetches page via curl_cffi Chrome impersonation to bypass Cloudflare WAF and extracts RSC chunks."""
        try:
            resp = requests.get(url, headers=self.headers, impersonate="chrome120", timeout=15)
            if resp.status_code != 200:
                logger.warning(f"Failed to fetch {url}, status code: {resp.status_code}")
                return []
            
            raw_chunks = re.findall(r'self\.__next_f\.push\(\[1,"(.*?)"\]\)', resp.text, re.DOTALL)
            chunks = []
            for chunk in raw_chunks:
                try:
                    # Unescape standard Next.js escaped sequences
                    unescaped = chunk.replace('\\"', '"').replace('\\\\', '\\')
                    chunks.append(unescaped)
                except Exception:
                    chunks.append(chunk)
            return chunks
        except Exception as e:
            logger.error(f"Network error fetching {url}: {e}")
            return []

    def fetch_tournament_info_and_matches(self) -> Dict[str, Any]:
        """Fetches tournament details and upcoming/current matches."""
        url = f"{self.base_tournament_url}/matches/upcoming-matches"
        chunks = self._get_page_rsc_chunks(url)
        
        tournament_details = {}
        matches_list = []

        for chunk in chunks:
            # Extract tournament details
            if '"tournamentDetails"' in chunk and not tournament_details:
                parsed = self._extract_json_block(chunk, "tournamentDetails")
                if parsed and "tournamentDetails" in parsed:
                    tournament_details = parsed["tournamentDetails"].get("data", {})

            # Extract matches
            if '"matches":{"status":true' in chunk and not matches_list:
                parsed = self._extract_json_block(chunk, "matches")
                if parsed and "matches" in parsed:
                    matches_list = parsed["matches"].get("data", [])

        return {
            "tournament": tournament_details,
            "matches": matches_list
        }

    def fetch_teams(self) -> List[Dict[str, Any]]:
        """Fetches participating teams and player rosters."""
        url = f"{self.base_tournament_url}/teams"
        chunks = self._get_page_rsc_chunks(url)
        
        teams = []
        for chunk in chunks:
            if '"teamResponse":{"status":true' in chunk:
                parsed = self._extract_json_block(chunk, "teamResponse")
                if parsed and "teamResponse" in parsed:
                    teams = parsed["teamResponse"].get("data", [])
                    break
        return teams

    def fetch_live_matches_tab(self) -> List[Dict[str, Any]]:
        """Checks the live-matches tab for active ongoing matches."""
        url = f"{self.base_tournament_url}/matches/live-matches"
        chunks = self._get_page_rsc_chunks(url)
        live_matches = []
        for chunk in chunks:
            if '"matches":{"status":true' in chunk:
                parsed = self._extract_json_block(chunk, "matches")
                if parsed and "matches" in parsed:
                    live_matches = parsed["matches"].get("data", [])
                    break
        return live_matches

    def fetch_live_pune_matches(self) -> List[Dict[str, Any]]:
        """Fetches active ongoing matches near Pune using CricHeroes API."""
        url = "https://cricheroes.in/api/v1/search/v2/near-by-me-matches/18.5204/73.8567"
        try:
            r = requests.get(url, headers=self.api_headers, impersonate="chrome120", timeout=10)
            if r.status_code == 200:
                data = r.json().get("data", [])
                live = [m for m in data if m.get("status") == "live"]
                return live
            return []
        except Exception as e:
            logger.error(f"Error fetching nearby live matches: {e}")
            return []

    def fetch_live_mini_scorecard(self, match_id: int) -> Optional[Dict[str, Any]]:
        """Fetches detailed real-time live match scorecard for any active CricHeroes match with TTL caching."""
        import time
        now = time.time()
        if match_id in self._scorecard_cache:
            if now - self._scorecard_cache_time.get(match_id, 0) < self._cache_ttl:
                return self._scorecard_cache[match_id]

        url = f"https://cricheroes.in/api/v1/scorecard/get-mini-scorecard/{match_id}"
        try:
            r = requests.get(url, headers=self.api_headers, impersonate="chrome120", timeout=10)
            if r.status_code != 200:
                logger.warning(f"Error fetching mini scorecard {match_id}: status {r.status_code}")
                return self._scorecard_cache.get(match_id)
            raw = r.json().get("data", {})
            if not raw:
                return self._scorecard_cache.get(match_id)

            team_a_data = raw.get("team_a", {}) or {}
            team_b_data = raw.get("team_b", {}) or {}
            team_a_name = team_a_data.get("name", "Team A")
            team_b_name = team_b_data.get("name", "Team B")

            current_inning = raw.get("current_inning", 1)
            
            if current_inning == 2:
                batting_team_name = team_b_name
                current_team_obj = team_b_data
            else:
                batting_team_name = team_a_name
                current_team_obj = team_a_data

            innings_list = current_team_obj.get("innings", [])
            current_inn = innings_list[-1] if innings_list else {}

            runs = current_inn.get("total_run", 0)
            wickets = current_inn.get("total_wicket", 0)
            overs = str(current_inn.get("overs_played", "0.0"))
            
            summary_obj = current_inn.get("summary", {})
            crr = str(summary_obj.get("rr", "0.00"))

            match_sum = raw.get("match_summary", {}) or {}
            target = match_sum.get("target", "-")
            rrr = match_sum.get("rrr", "-")
            equation = match_sum.get("summary") or match_sum.get("ticker_summary") or raw.get("toss_details", "")

            # Batters
            batters_raw = raw.get("batsmen", {}) or {}
            batters = []
            sb = batters_raw.get("sb")
            if sb:
                batters.append({
                    "name": sb.get("name", "Batter") + "*",
                    "runs": sb.get("runs", 0),
                    "balls": sb.get("balls", 0),
                    "fours": sb.get("4s", 0),
                    "sixes": sb.get("6s", 0),
                    "sr": str(sb.get("strike_rate", "0.0"))
                })
            nsb = batters_raw.get("nsb")
            if nsb:
                batters.append({
                    "name": nsb.get("name", "Batter"),
                    "runs": nsb.get("runs", 0),
                    "balls": nsb.get("balls", 0),
                    "fours": nsb.get("4s", 0),
                    "sixes": nsb.get("6s", 0),
                    "sr": str(nsb.get("strike_rate", "0.0"))
                })

            # Bowler
            bowlers_raw = raw.get("bowlers", {}) or {}
            bw_sb = bowlers_raw.get("sb") or {}
            bowler = {
                "name": bw_sb.get("name", "Bowler"),
                "overs": str(bw_sb.get("overs", "0.0")),
                "maidens": bw_sb.get("maidens", 0),
                "runs": bw_sb.get("runs", 0),
                "wickets": bw_sb.get("wickets", 0),
                "econ": str(bw_sb.get("economy_rate", "0.0"))
            }

            recent_over_str = raw.get("recent_over", "")
            balls = [b.strip() for b in recent_over_str.replace("|", " ").split() if b.strip()]
            if not balls:
                balls = ["•"]

            result = {
                "is_simulated": False,
                "is_real_cricheroes": True,
                "status": raw.get("status", "live"),
                "match_id": raw.get("match_id"),
                "tournament_name": raw.get("tournament_name") or "CricHeroes Live Match",
                "round_name": raw.get("tournament_round_name") or raw.get("match_type") or "Match",
                "overs_limit": raw.get("overs", 20),
                "ground_name": raw.get("ground_name") or "Cricket Ground",
                "team_a": team_a_name,
                "team_b": team_b_name,
                "batting_team": batting_team_name,
                "runs": runs,
                "wickets": wickets,
                "overs": overs,
                "crr": crr,
                "rrr": rrr,
                "target": target,
                "recent_balls": balls[-6:],
                "batters": batters,
                "bowler": bowler,
                "equation": equation,
            }
            self._scorecard_cache[match_id] = result
            self._scorecard_cache_time[match_id] = now
            return result
        except Exception as e:
            logger.error(f"Error parsing mini scorecard for {match_id}: {e}")
            return self._scorecard_cache.get(match_id)

    def fetch_match_scorecard(self, match_id: int, team_a: str = "", team_b: str = "", status: str = "live") -> Optional[Dict[str, Any]]:
        """Fetches detailed live scorecard for a given match."""
        slug_a = re.sub(r'[^a-zA-Z0-9]+', '-', team_a.strip().lower()).strip('-') if team_a else "team-a"
        slug_b = re.sub(r'[^a-zA-Z0-9]+', '-', team_b.strip().lower()).strip('-') if team_b else "team-b"
        url = f"https://cricheroes.com/scorecard/{match_id}/{self.slug}/{slug_a}-vs-{slug_b}/{status}"
        
        chunks = self._get_page_rsc_chunks(url)
        # Scan chunks for scorecard payload
        scorecard_data = {}
        for chunk in chunks:
            if '"matchDetails"' in chunk or '"squad"' in chunk or f'"match_id":{match_id}' in chunk:
                # Attempt extracting root json
                parsed = self._extract_json_block(chunk, "matchDetails")
                if parsed:
                    scorecard_data.update(parsed)
        return scorecard_data

    def sync_all(self) -> Dict[str, Any]:
        """Fetches full state (tournament, matches, teams) and caches locally."""
        info = self.fetch_tournament_info_and_matches()
        teams = self.fetch_teams()
        live_matches = self.fetch_live_matches_tab()

        state = {
            "last_synced": datetime.now().isoformat(),
            "tournament": info.get("tournament", {}),
            "upcoming_matches": info.get("matches", []),
            "live_matches": live_matches,
            "teams": teams,
        }

        # Cache to disk
        try:
            with open(config.STATE_FILE, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2, ensure_ascii=False)
            logger.info(f"Successfully synced state to {config.STATE_FILE}")
        except Exception as e:
            logger.error(f"Failed to write state file: {e}")

        return state

    @staticmethod
    def load_cached_state() -> Dict[str, Any]:
        """Loads locally cached tournament state if available."""
        if config.STATE_FILE.exists():
            try:
                with open(config.STATE_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error reading cache: {e}")
        return {}

if __name__ == "__main__":
    client = CricHeroesClient()
    print("Testing CricHeroesClient sync...")
    state = client.sync_all()
    print("Tournament:", state["tournament"].get("name"))
    print("Matches Count:", len(state["upcoming_matches"]))
    print("Teams Count:", len(state["teams"]))
