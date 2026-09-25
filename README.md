---
title: VLV Cricket Scoreboard & PRISM Ticker
emoji: 🏏
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
---

# VLV Ganapati Men's Cricket Tournament 2026
### Local Live Scoreboard, Poster Generator & WhatsApp Broadcast Hub

A high-performance local dashboard and automated broadcast system built for the **VLV Ganapati Men's Cricket Tournament 2026** (CricHeroes Tournament ID: `2169387`).

---

## 🌟 Key Capabilities

1. **Anti-Block & Cloudflare Compliance**:
   - Standard HTTP requests to CricHeroes trigger `HTTP 403 Forbidden` due to Cloudflare Bot Management and TLS fingerprinting.
   - This project uses `curl_cffi` to impersonate authentic Chrome 120 TLS fingerprints and HTTP/2 headers.
   - Operates as a **polite, single-client bridge**: queries CricHeroes once per interval and caches the data locally. 100 viewers on your local network (phones, laptops, TVs) connect to this local server, generating **zero duplicate strain** on CricHeroes.

2. **Real-Time Local Scoreboard (FastAPI + Tailwind CSS)**:
   - Zero-latency Server-Sent Events (SSE) streaming updates scores, overs, run rates, batters at crease, current bowler, and recent ball commentary without manual page refresh.
   - Shows all **9 tournament match fixtures** with ground details and dates.
   - Shows all **6 participating teams** (A wing, B Wing, C Wing, E Wing, F Wing, H Wing) with player rosters and photos.

3. **1080x1080 Broadcast-Grade Poster Generator**:
   - Generates crisp, high-resolution square score posters (`output/posters/latest_poster.png`) with team branding, big score digits, batter/bowler figures, and match equations.
   - Ready for instant posting on WhatsApp groups, Instagram stories, or status updates.

4. **Safe WhatsApp Dispatcher with Anti-Ban Guardrails**:
   - **Delta Check**: Even when running every 1 minute, the dispatcher **skips identical scores** if no balls were bowled (delays, innings breaks, timeouts).
   - **Cooldown Guard**: Enforces a minimum 50-second spacing between dispatches.
   - **Cadence Modes**: Supports "Every 1 Minute with Delta Check" or "End of Every Over".
   - **1-Click WhatsApp Web Share**: Generates a pre-formatted WhatsApp share link for instant sharing from browser or phone, plus optional Webhook integration.

5. **Interactive Match Simulator**:
   - Because tournament matches start on **September 26, 2026**, the system comes with an interactive match simulator using the actual teams and players so you can test score updates, poster creation, and WhatsApp sharing immediately!

6. **AI Voice Commentary Broadcaster**:
   - Generates 2-sentence charismatic live cricket commentary (combining Ravi Shastri and Harsha Bhogle broadcasting styles) via LLMs or an intelligent rule-based engine.
   - Synthesizes realistic Indian English audio commentary (`en-IN-PrabhatNeural`) through Microsoft `edge-tts` with real-time browser playback.

---

## 📖 In-Depth Documentation
For a complete architectural breakdown, API specifications, and operational runbook, please refer to:
👉 **[DOCUMENTATION.md](file:///d:/AI_stuff/CH_Score/DOCUMENTATION.md)**

---

## 🚀 Quick Start Guide

### 1. Launch the Server
Double-click `run.bat` or run:
```bash
python -m uvicorn app:app --host 0.0.0.0 --port 8000
```

### 2. Access the Dashboard
- Open **http://localhost:8000** in your browser.
- Anyone on your Wi-Fi can view it on their phone: `http://<YOUR_COMPUTER_IP>:8000`.

---

## 📁 Project Layout
```
d:\AI_stuff\CH_Score\
├── app.py                      # FastAPI web server, API routes & background poller
├── config.py                   # Central settings (Tournament ID, intervals, paths)
├── run.bat                     # 1-click Windows launcher
├── DOCUMENTATION.md            # Comprehensive project documentation & API guide
├── README.md                   # Quick start summary
├── services/
│   ├── cricheroes_client.py    # Cloudflare-bypassing CricHeroes scraper
│   ├── poster_generator.py     # 1080x1080 Pillow scorecard graphic generator
│   ├── match_simulator.py      # Real-time ball-by-ball cricket simulator
│   ├── whatsapp_dispatcher.py  # WhatsApp dispatcher with delta check & anti-ban guards
│   └── ai_commentator.py       # AI broadcast commentary (LLM + Edge-TTS voice)
├── templates/
│   └── index.html              # Responsive dark-theme dashboard UI
├── static/
│   ├── css/styles.css          # Custom styling & animations
│   └── js/dashboard.js         # SSE live streaming, tab routing & UI updates
├── data/
│   ├── tournament_state.json   # Cached CricHeroes tournament data
│   └── poster_history.json     # Record of generated posters & dispatches
└── output/
    ├── posters/                # Generated scorecard PNG posters
    └── commentary/             # Generated voice commentary MP3 files
```
