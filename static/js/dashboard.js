// Minimal & Ultra-Fast Dashboard JavaScript for VLV Cricket Hub

let currentTeamsData = [];
let activeTeamIndex = 0;
let eventSource = null;
let appState = {};

// Initialize on DOM ready
document.addEventListener("DOMContentLoaded", () => {
  if (window.lucide) {
    lucide.createIcons();
  }
  loadFullState();
  initLiveStream();
  // 3-second heartbeat polling ensures zero-lag updates on mobile/tunnels
  setInterval(pollDashboardState, 3000);
});

// Dual-channel live polling fallback
async function pollDashboardState() {
  try {
    const res = await fetch("/api/state");
    const data = await res.json();
    if (data.current_match) {
      updateLiveScorecardUI(data.current_match);
    }
  } catch (e) {}
}

// Switch Tabs with On-Demand Lazy Loading
function switchTab(tabId) {
  document.querySelectorAll(".tab-content").forEach(el => el.classList.add("hidden"));
  document.querySelectorAll(".tab-btn").forEach(el => {
    el.classList.remove("active-tab", "text-blue-400", "border-blue-500");
    el.classList.add("text-slate-400", "border-transparent");
  });

  const activeBtn = document.getElementById("nav-" + tabId);
  const activeContent = document.getElementById(tabId);
  if (activeContent) activeContent.classList.remove("hidden");
  if (activeBtn) {
    activeBtn.classList.add("active-tab", "text-blue-400", "border-blue-500");
    activeBtn.classList.remove("text-slate-400", "border-transparent");
  }

  // Lazy load tab data on-demand only when opened
  if (tabId === "tab-matches") {
    loadUpcomingMatches();
  } else if (tabId === "tab-teams") {
    loadTeamsAndSquads();
  }

  if (window.lucide) lucide.createIcons();
}

// Full State Loader
async function loadFullState() {
  try {
    const res = await fetch("/api/state");
    appState = await res.json();
    updateControlsUI(appState);
    if (appState.current_match) {
      updateLiveScorecardUI(appState.current_match);
    }
  } catch (err) {
    console.error("Failed to load full state:", err);
  }
}

// Switch Active Live Match Source
async function onMatchSourceChange(value) {
  let payload = {};
  if (value === "simulator") {
    payload = { match_id: 27016163, source: "simulator" };
  } else if (value === "tournament_2169387") {
    payload = { match_id: 2169387, source: "tournament_2169387" };
  } else {
    payload = { match_id: parseInt(value), source: "real_cricheroes" };
  }

  try {
    const res = await fetch("/api/live/select-match", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (data.match) {
      updateLiveScorecardUI(data.match);
    }
    loadFullState();
  } catch (err) {
    console.error("Error switching live match source:", err);
  }
}

// Track Custom Match by ID
async function trackCustomMatch() {
  const input = document.getElementById("custom-match-id");
  const matchId = parseInt(input.value);
  if (!matchId || isNaN(matchId)) {
    alert("Please enter a valid numeric CricHeroes Match ID (e.g. 27303530)");
    return;
  }

  const select = document.getElementById("match-source-select");
  let exists = false;
  for (let opt of select.options) {
    if (opt.value == matchId) {
      exists = true;
      break;
    }
  }
  if (!exists) {
    const newOpt = document.createElement("option");
    newOpt.value = matchId;
    newOpt.textContent = `🔴 Custom Match #${matchId} (CricHeroes Live)`;
    select.prepend(newOpt);
  }
  select.value = matchId;
  await onMatchSourceChange(matchId);
  input.value = "";
}

// Updates Settings & Mode Badges
function updateControlsUI(state) {
  const modeBadge = document.getElementById("mode-badge");
  const modeLabel = document.getElementById("mode-label");
  const simBanner = document.getElementById("sim-banner");
  const simCheckbox = document.getElementById("sim-enabled");
  const autoStepLabel = document.getElementById("auto-step-label");
  const sourceSelect = document.getElementById("match-source-select");
  const sourceTag = document.getElementById("source-tag");

  if (state.live_source === "simulator" || state.simulation_mode) {
    if (modeBadge) {
      modeBadge.className = "px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 bg-purple-500/20 text-purple-300 border border-purple-500/40";
      modeLabel.textContent = "Simulation Mode Active";
    }
    if (simBanner) simBanner.classList.remove("hidden");
    if (sourceTag) {
      sourceTag.textContent = "🎮 SIMULATION DEMO";
      sourceTag.className = "px-2 py-0.5 rounded text-[11px] font-bold bg-purple-500/20 text-purple-300 border border-purple-500/30";
    }
    if (sourceSelect) sourceSelect.value = "simulator";
  } else {
    if (modeBadge) {
      modeBadge.className = "px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 bg-emerald-500/20 text-emerald-300 border border-emerald-500/40";
      modeLabel.textContent = "Live CricHeroes Active";
    }
    if (simBanner) simBanner.classList.add("hidden");
    if (sourceTag) {
      sourceTag.textContent = "● REAL CRICHEROES LIVE";
      sourceTag.className = "px-2 py-0.5 rounded text-[11px] font-bold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30";
    }
  }

  if (simCheckbox) simCheckbox.checked = state.simulation_mode || false;
  if (autoStepLabel) autoStepLabel.textContent = state.sim_auto_step ? "Auto: ON (15s)" : "Auto: OFF";
}

// Live Scorecard UI Updates
function updateLiveScorecardUI(match) {
  if (!match || match.status === "idle") return;

  try {
    const matchupEl = document.getElementById("team-matchup");
    if (matchupEl) {
      const a = match.team_a || "Team A";
      const b = match.team_b || "Team B";
      matchupEl.innerHTML = `${a} <span class="text-slate-500 text-lg font-normal">vs</span> ${b}`;
    }

    const batting = match.batting_team || match.team_a || "Batting";
    const badgeEl = document.getElementById("batting-badge");
    if (badgeEl) badgeEl.textContent = `BATTING: ${batting}`;

    const scoreEl = document.getElementById("score-display");
    if (scoreEl) scoreEl.textContent = `${match.runs !== undefined ? match.runs : 0}/${match.wickets !== undefined ? match.wickets : 0}`;

    const oversEl = document.getElementById("overs-display");
    if (oversEl) oversEl.textContent = `(${match.overs || "0.0"} / ${match.overs_limit || 8} ov)`;
    
    const crrEl = document.getElementById("crr-display");
    if (crrEl) crrEl.textContent = match.crr || "0.00";

    const targetEl = document.getElementById("target-display");
    if (targetEl) targetEl.textContent = (match.target && match.target !== "-") ? match.target : "-";

    const rrrEl = document.getElementById("rrr-display");
    if (rrrEl) rrrEl.textContent = match.rrr || "-";

    const roundEl = document.getElementById("match-round");
    if (roundEl && match.round_name) roundEl.textContent = `${match.round_name} (${match.overs_limit || 8} Overs)`;

    const groundEl = document.getElementById("match-ground");
    if (groundEl && match.ground_name) {
      const span = groundEl.querySelector("span");
      if (span) span.textContent = match.ground_name;
    }

    const eqBanner = document.getElementById("equation-banner");
    if (eqBanner && match.equation) {
      eqBanner.textContent = "⚡ " + match.equation.toUpperCase();
    }

    // Recent Balls Strip
    const ballsContainer = document.getElementById("over-balls-container");
    if (ballsContainer && match.recent_balls) {
      ballsContainer.innerHTML = "";
      match.recent_balls.forEach(b => {
        const span = document.createElement("span");
        span.className = "w-8 h-8 rounded-full text-xs font-bold flex items-center justify-center transition";
        const bStr = String(b);
        if (bStr === "W") {
          span.className += " bg-red-600 text-white";
        } else if (bStr === "4") {
          span.className += " bg-emerald-600 text-white";
        } else if (bStr === "6") {
          span.className += " bg-purple-600 text-white";
        } else if (bStr.includes("wd") || bStr.includes("nb")) {
          span.className += " bg-amber-600 text-white";
        } else {
          span.className += " bg-slate-800 text-slate-200 border border-slate-700";
        }
        span.textContent = bStr;
        ballsContainer.appendChild(span);
      });
    }

    // Batters Card
    const battersList = document.getElementById("batters-list");
    if (battersList && match.batters && match.batters.length > 0) {
      battersList.innerHTML = "";
      match.batters.slice(0, 2).forEach((b, idx) => {
        const div = document.createElement("div");
        div.className = `flex items-center justify-between ${idx === 0 ? "pb-2 border-b border-slate-800/60" : ""}`;
        div.innerHTML = `
          <div>
            <div class="font-bold text-sm text-slate-100 flex items-center gap-1">
              <span>${b.name}</span>
            </div>
            <div class="text-xs text-slate-400">4s: ${b.fours || 0} | 6s: ${b.sixes || 0} | SR: ${b.sr || "0.0"}</div>
          </div>
          <div class="text-right">
            <div class="text-base font-bold text-amber-400">${b.runs || 0} <span class="text-xs text-slate-400 font-normal">(${b.balls || 0})</span></div>
          </div>
        `;
        battersList.appendChild(div);
      });
    }

    // Bowler Card
    const bwName = document.getElementById("bowler-name");
    const bwFigures = document.getElementById("bowler-figures");
    const bwEcon = document.getElementById("bowler-econ");
    if (match.bowler) {
      if (bwName) bwName.textContent = match.bowler.name || "Bowler";
      if (bwFigures) bwFigures.textContent = `${match.bowler.overs || "0.0"} - ${match.bowler.maidens || 0} - ${match.bowler.runs || 0} - ${match.bowler.wickets || 0}`;
      if (bwEcon) bwEcon.textContent = match.bowler.econ || "0.0";
    }

  } catch (err) {
    console.error("Error updating scorecard UI:", err);
  }
}

// Server-Sent Events (SSE) Listener
function initLiveStream() {
  if (eventSource) eventSource.close();
  eventSource = new EventSource("/api/live/stream");

  eventSource.onmessage = (e) => {
    try {
      const data = JSON.parse(e.data);
      updateLiveScorecardUI(data);
    } catch (err) {}
  };

  eventSource.onerror = () => {
    eventSource.close();
    setTimeout(initLiveStream, 5000);
  };
}

// Upcoming Matches Loader
async function loadUpcomingMatches() {
  try {
    const res = await fetch("/api/tournament");
    const data = await res.json();
    const matchesGrid = document.getElementById("matches-grid");
    if (!matchesGrid) return;

    matchesGrid.innerHTML = "";
    const matches = data.upcoming_matches || [];

    if (matches.length === 0) {
      matchesGrid.innerHTML = `<div class="col-span-3 text-center py-8 text-slate-500">No upcoming matches found. Click 'Sync' above.</div>`;
      return;
    }

    matches.forEach((m, idx) => {
      const dateStr = m.match_start_time ? new Date(m.match_start_time).toLocaleString("en-IN", {
        weekday: 'short', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'
      }) : "TBD";

      const card = document.createElement("div");
      card.className = "bg-slate-950 p-5 rounded-xl border border-slate-800 hover:border-slate-700 transition space-y-3 relative";
      card.innerHTML = `
        <div class="flex items-center justify-between text-xs text-slate-400 border-b border-slate-800/80 pb-2">
          <span class="font-bold text-blue-400">Match #${idx + 1}</span>
          <span>📅 ${dateStr}</span>
        </div>

        <div class="flex items-center justify-between py-1">
          <div class="space-y-1">
            <div class="font-bold text-base text-white">${m.team_a}</div>
            <div class="text-xs text-slate-500 font-medium">vs</div>
            <div class="font-bold text-base text-white">${m.team_b}</div>
          </div>
          <div class="text-right text-xs text-slate-400">
            <span class="px-2 py-1 rounded bg-slate-900 border border-slate-800 font-mono">${m.overs} Overs</span>
          </div>
        </div>

        <div class="text-[11px] text-slate-400 pt-2 border-t border-slate-800/60 flex items-center justify-between">
          <span>📍 ${m.ground_name || "Pune"}</span>
          <span class="capitalize text-amber-400">${m.status || "Upcoming"}</span>
        </div>

        <button onclick="trackCustomMatchId(${m.match_id || 0})" class="w-full mt-2 py-1.5 bg-blue-600 hover:bg-blue-500 active:scale-95 text-white font-semibold rounded-lg text-xs transition flex items-center justify-center gap-1.5 shadow">
          <i data-lucide="crosshair" class="w-3.5 h-3.5"></i> Set as Live Ticker Match
        </button>
      `;
      matchesGrid.appendChild(card);
    });
    if (window.lucide) lucide.createIcons();
  } catch (err) {
    console.error("Error loading upcoming matches:", err);
  }
}

async function trackCustomMatchId(matchId) {
  if (!matchId || matchId === 0) {
    alert("Match ID is not active yet on CricHeroes.");
    return;
  }
  const select = document.getElementById("match-source-select");
  let exists = false;
  for (let opt of select.options) {
    if (opt.value == matchId) {
      exists = true;
      break;
    }
  }
  if (!exists) {
    const newOpt = document.createElement("option");
    newOpt.value = matchId;
    newOpt.textContent = `🔴 Match #${matchId} (CricHeroes)`;
    select.prepend(newOpt);
  }
  select.value = matchId;
  await onMatchSourceChange(matchId);
  switchTab('tab-live');
  alert(`Now tracking Match #${matchId} on live scoreboard & PRISM ticker!`);
}

// Teams & Squads Loader
async function loadTeamsAndSquads() {
  try {
    const res = await fetch("/api/teams");
    currentTeamsData = await res.json();
    const chipsContainer = document.getElementById("team-chips");
    if (!chipsContainer || currentTeamsData.length === 0) return;

    chipsContainer.innerHTML = "";
    currentTeamsData.forEach((team, idx) => {
      const btn = document.createElement("button");
      btn.className = `px-3.5 py-1.5 rounded-lg text-xs font-semibold border transition ${
        idx === activeTeamIndex 
          ? "bg-blue-600 text-white border-blue-500 shadow-md" 
          : "bg-slate-950 text-slate-300 border-slate-800 hover:border-slate-700"
      }`;
      btn.textContent = team.team_name;
      btn.onclick = () => selectTeam(idx);
      chipsContainer.appendChild(btn);
    });

    renderActiveTeamSquad();
  } catch (err) {
    console.error("Error loading teams:", err);
  }
}

function selectTeam(idx) {
  activeTeamIndex = idx;
  const chips = document.getElementById("team-chips").children;
  for (let i = 0; i < chips.length; i++) {
    if (i === idx) {
      chips[i].className = "px-3.5 py-1.5 rounded-lg text-xs font-semibold border bg-blue-600 text-white border-blue-500 shadow-md transition";
    } else {
      chips[i].className = "px-3.5 py-1.5 rounded-lg text-xs font-semibold border bg-slate-950 text-slate-300 border-slate-800 hover:border-slate-700 transition";
    }
  }
  renderActiveTeamSquad();
}

function renderActiveTeamSquad() {
  const container = document.getElementById("team-squad-container");
  if (!container || currentTeamsData.length === 0) return;

  const team = currentTeamsData[activeTeamIndex];
  if (!team) return;

  const players = team.players || [];
  let html = `
    <div class="mb-4 flex items-center justify-between">
      <h3 class="font-bold text-base text-white">${team.team_name} Squad (${players.length} Players)</h3>
    </div>
    <div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-3">
  `;

  players.forEach(p => {
    const photo = p.profile_photo || "https://media.cricheroes.in/default/user_profile.png";
    html += `
      <div class="bg-slate-950 p-3 rounded-xl border border-slate-800 text-center flex flex-col items-center hover:border-slate-700 transition">
        <img src="${photo}" class="w-12 h-12 rounded-full object-cover border-2 border-slate-800 mb-2" onerror="this.src='https://media.cricheroes.in/default/user_profile.png'">
        <div class="font-bold text-xs text-white truncate w-full" title="${p.player_name}">${p.player_name}</div>
        <div class="text-[10px] text-slate-500 mt-0.5">ID: ${p.player_id}</div>
      </div>
    `;
  });

  html += `</div>`;
  container.innerHTML = html;
}

// CricHeroes Sync
async function syncCricHeroes() {
  const btn = document.getElementById("btn-sync");
  const statusEl = document.getElementById("sync-status");
  btn.disabled = true;
  statusEl.textContent = "Syncing...";
  statusEl.className = "text-amber-400 animate-pulse";

  try {
    const res = await fetch("/api/sync", { method: "POST" });
    const data = await res.json();
    statusEl.textContent = "Synced";
    statusEl.className = "text-emerald-400";
    loadUpcomingMatches();
    loadTeamsAndSquads();
    alert(`Successfully synced with CricHeroes!\nLoaded ${data.matches} matches and ${data.teams} teams.`);
  } catch (err) {
    statusEl.textContent = "Sync Error";
    statusEl.className = "text-red-400";
    alert("Error syncing with CricHeroes: " + err);
  } finally {
    btn.disabled = false;
  }
}

// Simulation Controls
async function simNextBall() {
  const res = await fetch("/api/simulator/next-ball", { method: "POST" });
  const data = await res.json();
  updateLiveScorecardUI(data);
}

async function simNextOver() {
  const res = await fetch("/api/simulator/next-over", { method: "POST" });
  const data = await res.json();
  updateLiveScorecardUI(data);
}

async function simReset() {
  const res = await fetch("/api/simulator/reset", { method: "POST" });
  const data = await res.json();
  updateLiveScorecardUI(data);
}

async function toggleSimAuto() {
  appState.sim_auto_step = !appState.sim_auto_step;
  await fetch("/api/simulator/toggle", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      enabled: appState.simulation_mode,
      auto_step: appState.sim_auto_step,
      speed_seconds: 15
    })
  });
  updateControlsUI(appState);
}

async function saveSettings(e) {
  e.preventDefault();
  const simEnabled = document.getElementById("sim-enabled").checked;

  try {
    await fetch("/api/simulator/toggle", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        enabled: simEnabled,
        auto_step: appState.sim_auto_step,
        speed_seconds: 15
      })
    });
    alert("Settings saved successfully!");
    loadFullState();
  } catch (err) {
    alert("Failed to save settings: " + err);
  }
}
