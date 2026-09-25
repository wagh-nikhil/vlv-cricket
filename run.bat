@echo off
title VLV CricHeroes Scoreboard & Poster Hub
echo =======================================================
echo  VLV Ganapati Men's Cricket Tournament 2026
echo  Local Scoreboard, Poster Generator & WhatsApp Hub
echo =======================================================
echo Starting server on http://localhost:8000 ...
python -m uvicorn app:app --host 0.0.0.0 --port 8000 --reload
pause
