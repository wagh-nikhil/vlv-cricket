import asyncio
import logging
import os
import re
import subprocess
import threading
from pathlib import Path
from typing import Optional, Dict, Any

logger = logging.getLogger("tunnel_manager")

CLOUDFLARED_BIN = Path(os.environ.get("APPDATA", "")) / "9router" / "bin" / "cloudflared.exe"

class TunnelManager:
    def __init__(self, target_port: int = 8000):
        self.target_port = target_port
        self.process: Optional[subprocess.Popen] = None
        self.public_url: Optional[str] = None
        self.is_running = False
        self._lock = threading.Lock()

    def is_available(self) -> bool:
        """Checks if cloudflared binary exists on the system."""
        return CLOUDFLARED_BIN.exists()

    def start(self) -> Dict[str, Any]:
        """Starts a Cloudflare quick tunnel in a background thread."""
        with self._lock:
            if self.is_running and self.public_url:
                return {
                    "status": "already_running",
                    "public_url": self.public_url,
                    "ticker_url": f"{self.public_url}/ticker"
                }

            if not self.is_available():
                logger.error(f"cloudflared binary not found at {CLOUDFLARED_BIN}")
                return {
                    "status": "error",
                    "message": f"cloudflared binary not found at {CLOUDFLARED_BIN}"
                }

            cmd = [
                str(CLOUDFLARED_BIN),
                "tunnel",
                "--url",
                f"http://127.0.0.1:{self.target_port}",
                "--no-autoupdate"
            ]

            try:
                self.process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
                )
                self.is_running = True

                # Parse output in background thread to extract trycloudflare.com URL
                monitor_thread = threading.Thread(target=self._monitor_output, daemon=True)
                monitor_thread.start()

                # Wait up to 10 seconds for URL extraction
                for _ in range(20):
                    if self.public_url:
                        break
                    import time
                    time.sleep(0.5)

                if self.public_url:
                    logger.info(f"Cloudflare tunnel online: {self.public_url}")
                    return {
                        "status": "online",
                        "public_url": self.public_url,
                        "ticker_url": f"{self.public_url}/ticker"
                    }
                else:
                    return {
                        "status": "starting",
                        "message": "Tunnel is starting, URL will be available in a few seconds."
                    }
            except Exception as e:
                self.is_running = False
                logger.error(f"Failed to launch cloudflared: {e}")
                return {"status": "error", "message": str(e)}

    def _monitor_output(self):
        """Reads stdout/stderr from cloudflared to extract the generated trycloudflare URL."""
        if not self.process or not self.process.stdout:
            return

        pattern = re.compile(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com")
        try:
            for line in iter(self.process.stdout.readline, ''):
                if not line:
                    break
                match = pattern.search(line)
                if match:
                    self.public_url = match.group(0)
                    logger.info(f"Captured Cloudflare tunnel URL: {self.public_url}")
                    break
        except Exception as e:
            logger.debug(f"Tunnel monitor read error: {e}")

    def stop(self) -> Dict[str, Any]:
        """Stops the active Cloudflare tunnel."""
        with self._lock:
            if self.process:
                try:
                    self.process.terminate()
                    self.process.wait(timeout=3)
                except Exception:
                    try:
                        self.process.kill()
                    except Exception:
                        pass
                self.process = None

            self.public_url = None
            self.is_running = False
            logger.info("Cloudflare tunnel stopped.")
            return {"status": "stopped"}

    def get_status(self) -> Dict[str, Any]:
        """Returns the current tunnel state."""
        return {
            "available": self.is_available(),
            "running": self.is_running and (self.process.poll() is None if self.process else False),
            "public_url": self.public_url,
            "ticker_url": f"{self.public_url}/ticker" if self.public_url else None
        }

import config
tunnel_manager = TunnelManager(target_port=config.PORT)
