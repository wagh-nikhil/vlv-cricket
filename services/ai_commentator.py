import asyncio
import logging
import os
import json
import shutil
from pathlib import Path
from typing import Dict, Any, Optional
import requests
import edge_tts

import config

logger = logging.getLogger("ai_commentator")

COMMENTARY_DIR = config.BASE_DIR / "output" / "commentary"
COMMENTARY_DIR.mkdir(parents=True, exist_ok=True)

CANDIDATE_MODELS = [
    "gemini/gemini-3.7-flash",
    "gemini/gemini-3-flash-preview",
    "kimchi/deepseek-v4-flash-0731",
    "nvidia/deepseek-ai/deepseek-v4-flash",
    "gc/gemini-2.5-flash",
    "kc/google/gemini-2.5-flash",
    "ds/deepseek-v4-flash"
]

ROUTER_URL = "http://localhost:20128/v1/chat/completions"
ROUTER_KEY = "sk-966b6095fb9f1512-so865f-073b9c5c"

class AICommentator:
    def __init__(self, voice: str = "en-IN-PrabhatNeural"):
        self.voice = voice
        self.last_commentary_key = ""
        self.last_text = ""

    def generate_commentary_text_rule_based(self, match: Dict[str, Any]) -> str:
        """Dynamic rule-based fallback commentator in Harsha/Ravi style."""
        batting = match.get("batting_team") or match.get("team_a") or "The batting side"
        runs = match.get("runs", 0)
        wickets = match.get("wickets", 0)
        overs = match.get("overs", "0.0")
        target = match.get("target", "-")
        equation = match.get("equation", "")
        crr = match.get("crr", "0.00")
        rrr = match.get("rrr", "-")
        recent = match.get("recent_balls", [])

        recent_str = " ".join(str(b) for b in recent[-4:]) if recent else "steady deliveries"
        
        if target and target != "-":
            return (
                f"{batting} are currently {runs} for {wickets} after {overs} overs, chasing a target of {target}. "
                f"They are scoring at {crr} runs an over. {equation}. "
                f"Pressure is mounting with every ball!"
            )
        else:
            return (
                f"{batting} have reached {runs} for {wickets} in {overs} overs with a run rate of {crr}. "
                f"Recent deliveries went {recent_str}. "
                f"An exciting phase of play unfolding right here!"
            )

    def generate_llm_commentary(self, match: Dict[str, Any]) -> str:
        """Calls local 9router LLM gateway for broadcast-style commentary."""
        prompt = (
            f"You are a charismatic, high-energy Indian cricket commentator like Ravi Shastri and Harsha Bhogle. "
            f"Give a punchy 2-sentence commentary update for this exact live game state:\n"
            f"- Match: {match.get('team_a')} vs {match.get('team_b')}\n"
            f"- Batting Team: {match.get('batting_team')}\n"
            f"- Score: {match.get('runs')}/{match.get('wickets')} in {match.get('overs')} overs (Limit: {match.get('overs_limit', 20)} ov)\n"
            f"- Target: {match.get('target', '-')}, CRR: {match.get('crr')}, RRR: {match.get('rrr', '-')}\n"
            f"- Equation: {match.get('equation')}\n"
            f"- Recent Balls: {match.get('recent_balls', [])}\n"
            f"Requirements: Strictly 2 sentences. Vibrant, thrilling cricket broadcasting tone. Do NOT include markdown or quotes."
        )

        headers = {
            "Authorization": f"Bearer {ROUTER_KEY}",
            "Content-Type": "application/json"
        }

        for model in ["gemini/gemini-3.7-flash", "kimchi/deepseek-v4-flash-0731"]:
            try:
                payload = {
                    "model": model,
                    "messages": [
                        {"role": "system", "content": "You are a professional live cricket commentator. Be lively, concise, and authentic."},
                        {"role": "user", "content": prompt}
                    ],
                    "max_tokens": 90,
                    "temperature": 0.7
                }
                resp = requests.post(ROUTER_URL, headers=headers, json=payload, timeout=1.5)
                if resp.status_code == 200:
                    data = resp.json()
                    choices = data.get("choices", [])
                    if choices:
                        text = choices[0].get("message", {}).get("content", "").strip()
                        if text:
                            logger.info(f"Generated commentary via 9router model {model}")
                            return text.replace('"', '').replace('*', '')
            except Exception as e:
                logger.debug(f"Model {model} skipped: {e}")
                continue

        logger.info("Using dynamic cricket broadcast commentary engine.")
        return self.generate_commentary_text_rule_based(match)

    async def generate_speech_audio(self, text: str, output_filename: str = "latest_commentary.mp3") -> Path:
        """Converts commentary text to crystal-clear speech using edge-tts."""
        dest_path = COMMENTARY_DIR / output_filename
        communicate = edge_tts.Communicate(text, voice=self.voice)
        await communicate.save(str(dest_path))

        # Copy to latest_commentary.mp3 if different
        latest_path = COMMENTARY_DIR / "latest_commentary.mp3"
        if dest_path != latest_path:
            shutil.copyfile(str(dest_path), str(latest_path))

        return latest_path

    async def generate_live_commentary(self, match: Dict[str, Any], force: bool = False) -> Optional[Dict[str, Any]]:
        """Generates commentary text and voice mp3 for a match."""
        if not match:
            return None

        match_id = match.get("match_id", "live")
        overs = str(match.get("overs", "0.0")).replace(".", "_")
        runs = match.get("runs", 0)
        wickets = match.get("wickets", 0)
        current_key = f"{match_id}_{overs}_{runs}_{wickets}"

        if not force and current_key == self.last_commentary_key:
            return {
                "status": "cached",
                "text": self.last_text,
                "audio_url": "/commentary/latest_commentary.mp3"
            }

        # 1. Generate text
        text = self.generate_llm_commentary(match)
        self.last_text = text
        self.last_commentary_key = current_key

        # 2. Generate audio
        filename = f"commentary_{match_id}_{overs}.mp3"
        try:
            await self.generate_speech_audio(text, filename)
            mtime = os.path.getmtime(COMMENTARY_DIR / "latest_commentary.mp3")
            return {
                "status": "success",
                "text": text,
                "audio_url": f"/commentary/latest_commentary.mp3?t={mtime}"
            }
        except Exception as e:
            logger.error(f"Error generating voice audio: {e}")
            return {
                "status": "text_only",
                "text": text,
                "audio_url": None
            }

commentator_instance = AICommentator()
