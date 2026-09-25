// Dashboard JavaScript for VLV Cricket Hub

let currentTeamsData = [];
let activeTeamIndex = 0;
let eventSource = null;
let appState = {};

// Initialize on DOM ready - Fast Mobile Load
document.addEventListener("DOMContentLoaded", () => {
  if (window.lucide) {
    lucide.createIcons();
  }
  loadFullState();
  initLiveStream();
  // Heartbeat polling every 3s to guarantee zero-lag live updates on mobile/tunnels
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

  // Lazy load tab contents only when accessed
  if (tabId === "tab-matches") {
    loadUpcomingMatches();
  } else if (tabId === "tab-teams") {
    loadTeamsAndSquads();
  } else if (tabId === "tab-history") {
    loadPosterHistory();
  } else if (tabId === "tab-ticker") {
    loadNetworkAndTunnelInfo();
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
    payload = { match_id: 27016163, source: "tournament_2169387" };
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
    alert("Please enter a valid numeric CricHeroes Match ID (e.g. 27109491)");
    return;
  }

  // Add option to select if not present
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
  const waCheckbox = document.getElementById("wa-enabled");
  const waCadence = document.getElementById("wa-cadence");
  const waGroup = document.getElementById("wa-group");
  const autoStepLabel = document.getElementById("auto-step-label");
  const sourceSelect = document.getElementById("match-source-select");
  const sourceTag = document.getElementById("source-tag");

  if (state.live_source === "simulator" || state.simulation_mode) {
    modeBadge.className = "px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 bg-purple-500/20 text-purple-300 border border-purple-500/40";
    modeLabel.textContent = "Simulation Mode Active";
    if (simBanner) simBanner.classList.remove("hidden");
    if (sourceTag) {
      sourceTag.textContent = "🎮 SIMULATION DEMO";
      sourceTag.className = "px-2.5 py-1 rounded text-[11px] font-bold bg-purple-500/20 text-purple-300 border border-purple-500/30";
    }
    if (sourceSelect) sourceSelect.value = "simulator";
  } else {
    modeBadge.className = "px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 bg-emerald-500/20 text-emerald-300 border border-emerald-500/40";
    modeLabel.textContent = "Live CricHeroes Feed Active";
    if (simBanner) simBanner.classList.add("hidden");
    if (sourceTag) {
      sourceTag.textContent = "● REAL CRICHEROES LIVE";
      sourceTag.className = "px-2.5 py-1 rounded text-[11px] font-bold bg-red-500/20 text-red-400 border border-red-500/30";
    }
    if (sourceSelect && state.active_match_id) {
      sourceSelect.value = String(state.active_match_id);
    }
  }

  if (simCheckbox) simCheckbox.checked = state.live_source === "simulator";
  if (waCheckbox) waCheckbox.checked = state.whatsapp_enabled;
  if (waCadence) waCadence.value = state.whatsapp_cadence;
  if (waGroup) waGroup.value = state.whatsapp_group;

  if (autoStepLabel) {
    autoStepLabel.textContent = state.sim_auto_step ? `Auto: ON (${state.sim_speed_seconds}s)` : "Auto: OFF";
  }
}

// Live Scorecard UI Updater
function updateLiveScorecardUI(match) {
  if (!match) return;

  try {
    const teamA = match.team_a || "Team A";
    const teamB = match.team_b || "Team B";
    const batting = match.batting_team || teamA;

    const matchupEl = document.getElementById("team-matchup");
    if (matchupEl) matchupEl.innerHTML = `${teamA} <span class="text-slate-500 text-lg font-normal">vs</span> ${teamB}`;

    const badgeEl = document.getElementById("batting-badge");
    if (badgeEl) badgeEl.textContent = `BATTING: ${batting}`;

    const scoreEl = document.getElementById("score-display");
    if (scoreEl) scoreEl.textContent = `${match.runs !== undefined ? match.runs : 0}/${match.wickets !== undefined ? match.wickets : 0}`;

    const oversEl = document.getElementById("overs-display");
    if (oversEl) oversEl.textContent = `(${match.overs || "0.0"} / ${match.overs_limit || 20} ov)`;
    
    const crrEl = document.getElementById("crr-display");
    if (crrEl) crrEl.textContent = match.crr || "0.00";

    const targetEl = document.getElementById("target-display");
    if (targetEl) targetEl.textContent = (match.target && match.target !== "-") ? match.target : "-";

    const rrrEl = document.getElementById("rrr-display");
    if (rrrEl) rrrEl.textContent = match.rrr || "-";

    // Match Venue / Round
    const roundEl = document.getElementById("match-round");
    if (roundEl && match.round_name) roundEl.textContent = `${match.round_name} (${match.overs_limit || 20} Overs)`;

    const groundEl = document.getElementById("match-ground");
    if (groundEl && match.ground_name) {
      const span = groundEl.querySelector("span");
      if (span) span.textContent = match.ground_name;
    }

    // Equation Banner
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
    if (match.bowler) {
      const bwNameEl = document.getElementById("bowler-name");
      if (bwNameEl) bwNameEl.textContent = match.bowler.name || "Bowler";

      const bwFigEl = document.getElementById("bowler-figures");
      const bw = match.bowler;
      if (bwFigEl) bwFigEl.textContent = `${bw.overs || "0.0"} - ${bw.maidens || 0} - ${bw.runs || 0} - ${bw.wickets || 0}`;

      const bwEconEl = document.getElementById("bowler-econ");
      if (bwEconEl) bwEconEl.textContent = bw.econ || "0.0";
    }

    // WhatsApp Pre-filled Link
    const waDirectLink = document.getElementById("wa-direct-link");
    if (waDirectLink) {
      const text = encodeURIComponent(
        `🏆 *${match.tournament_name || "CricHeroes Live Match"}*\n` +
        `⚔️ *${teamA} vs ${teamB}*\n` +
        `🏏 *${batting}: ${match.runs || 0}/${match.wickets || 0}* (${match.overs || "0.0"}/${match.overs_limit || 20} ov)\n` +
        `⚡ CRR: ${match.crr || "0.00"} | Target: ${match.target || "-"}\n` +
        `🔥 *${match.equation || ""}*`
      );
      waDirectLink.href = `https://api.whatsapp.com/send?text=${text}`;
    }

    // Update Poster Preview and Commentary only when score or overs change
    const posterKey = `${match.match_id}_${match.overs}_${match.runs}_${match.wickets}`;
    if (window._lastPosterKey !== posterKey) {
      window._lastPosterKey = posterKey;
      refreshPosterImage();
      loadLatestCommentary(true);
    }
  } catch (err) {
    console.error("Error in updateLiveScorecardUI:", err);
  }
}

function refreshPosterImage() {
  const posterImg = document.getElementById("poster-preview");
  if (posterImg) {
    posterImg.src = `/posters/latest_poster.png?t=${Date.now()}`;
  }
  const timestamp = document.getElementById("poster-timestamp");
  if (timestamp) {
    timestamp.textContent = "Updated " + new Date().toLocaleTimeString();
  }
}

// SSE Live Stream Connection
function initLiveStream() {
  if (eventSource) eventSource.close();

  eventSource = new EventSource("/api/live/stream");
  eventSource.onmessage = (e) => {
    try {
      const data = JSON.parse(e.data);
      if (data && data.status !== "idle") {
        updateLiveScorecardUI(data);
      }
    } catch (err) {
      console.error("SSE parse error:", err);
    }
  };

  eventSource.onerror = () => {
    console.warn("SSE stream disconnected. Retrying in 5s...");
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
      matchesGrid.innerHTML = `<div class="col-span-3 text-center py-8 text-slate-500">No upcoming matches found. Click 'Sync CricHeroes' above.</div>`;
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
  alert(`Now tracking Match #${matchId} on PRISM Live ticker!`);
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
      btn.className = `px-4 py-2 rounded-xl text-xs font-bold border transition flex items-center gap-2 ${
        idx === activeTeamIndex 
          ? "bg-blue-600 border-blue-500 text-white shadow-md shadow-blue-600/30" 
          : "bg-slate-950 border-slate-800 text-slate-300 hover:bg-slate-800"
      }`;
      btn.innerHTML = `
        <img src="${team.team_logo || 'https://media.cricheroes.in/default/teamintital/AW.png'}" class="w-4 h-4 rounded-full" onerror="this.src='/static/images/team_default.png'">
        <span>${team.team_name}</span>
        <span class="text-[10px] opacity-75 font-normal">(${team.players ? team.players.length : 0})</span>
      `;
      btn.onclick = () => {
        activeTeamIndex = idx;
        renderActiveTeamSquad();
        loadTeamsAndSquads(); // re-render chip styles
      };
      chipsContainer.appendChild(btn);
    });

    renderActiveTeamSquad();
  } catch (err) {
    console.error("Error loading teams:", err);
  }
}

function renderActiveTeamSquad() {
  const container = document.getElementById("team-squad-container");
  if (!container || currentTeamsData.length === 0) return;

  const team = currentTeamsData[activeTeamIndex];
  if (!team) return;

  const players = team.players || [];
  let html = `
    <div class="mb-4 flex items-center justify-between">
      <h3 class="font-bold text-lg text-white">${team.team_name} Squad (${players.length} Players)</h3>
    </div>
    <div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-3">
  `;

  players.forEach(p => {
    const photo = p.profile_photo || "https://media.cricheroes.in/default/user_profile.png";
    html += `
      <div class="bg-slate-950 p-3 rounded-xl border border-slate-800 text-center flex flex-col items-center hover:border-slate-700 transition">
        <img src="${photo}" class="w-14 h-14 rounded-full object-cover border-2 border-slate-800 mb-2" onerror="this.src='https://media.cricheroes.in/default/user_profile.png'">
        <div class="font-bold text-xs text-white truncate w-full" title="${p.player_name}">${p.player_name}</div>
        <div class="text-[10px] text-slate-500 mt-0.5">Player ID: ${p.player_id}</div>
      </div>
    `;
  });

  html += `</div>`;
  container.innerHTML = html;
}

// Poster History Loader
async function loadPosterHistory() {
  try {
    const res = await fetch("/api/posters/history");
    const history = await res.json();
    const tbody = document.getElementById("history-table-body");
    if (!tbody) return;

    if (!history || history.length === 0) {
      tbody.innerHTML = `<tr><td colspan="5" class="py-4 px-4 text-center text-slate-500">No poster history recorded yet.</td></tr>`;
      return;
    }

    tbody.innerHTML = "";
    history.slice().reverse().forEach(item => {
      const timeStr = item.timestamp ? new Date(item.timestamp).toLocaleTimeString() : "-";
      const tr = document.createElement("tr");
      tr.className = "hover:bg-slate-950/40 transition";
      const isSuccess = item.status === "success";
      tr.innerHTML = `
        <td class="py-3 px-4 text-slate-400">${timeStr}</td>
        <td class="py-3 px-4 font-bold text-amber-400">${item.runs}/${item.wickets} (${item.overs} ov)</td>
        <td class="py-3 px-4">
          <span class="px-2 py-0.5 rounded text-[10px] font-semibold ${isSuccess ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30' : 'bg-slate-800 text-slate-400'}">
            ${item.status.toUpperCase()}
          </span>
        </td>
        <td class="py-3 px-4 text-slate-300">${item.reason || "-"}</td>
        <td class="py-3 px-4 text-right">
          <a href="${item.share_url}" target="_blank" class="text-emerald-400 hover:underline text-xs">Share WA →</a>
        </td>
      `;
      tbody.appendChild(tr);
    });
  } catch (err) {
    console.error("Error loading history:", err);
  }
}

// User Action Handlers
async function generatePosterNow() {
  try {
    const res = await fetch("/api/poster/generate", { method: "POST" });
    const data = await res.json();
    refreshPosterImage();
    alert("Match poster generated successfully!");
  } catch (err) {
    alert("Failed to generate poster: " + err);
  }
}

async function dispatchToWhatsApp() {
  try {
    const res = await fetch("/api/whatsapp/dispatch", { method: "POST" });
    const data = await res.json();
    loadPosterHistory();
    if (data.share_url) {
      window.open(data.share_url, "_blank");
    } else {
      alert("WhatsApp dispatch triggered: " + (data.reason || "Success"));
    }
  } catch (err) {
    alert("Dispatch error: " + err);
  }
}

async function syncCricHeroes() {
  const btn = document.getElementById("btn-sync");
  const statusEl = document.getElementById("sync-status");
  btn.disabled = true;
  statusEl.textContent = "Syncing...";
  statusEl.className = "text-amber-400 animate-pulse";

  try {
    const res = await fetch("/api/sync", { method: "POST" });
    const data = await res.json();
    statusEl.textContent = "Synced (" + data.matches + " matches)";
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
      speed_seconds: appState.sim_speed_seconds || 15
    })
  });
  updateControlsUI(appState);
}

async function saveSettings(e) {
  e.preventDefault();
  const enabled = document.getElementById("wa-enabled").checked;
  const cadence = document.getElementById("wa-cadence").value;
  const group = document.getElementById("wa-group").value;
  const webhook = document.getElementById("wa-webhook").value;
  const simEnabled = document.getElementById("sim-enabled").checked;

  try {
    await fetch("/api/whatsapp/settings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        enabled: enabled,
        cadence: cadence,
        group_name: group,
        webhook_url: webhook
      })
    });

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

// AI Voice Commentary Functions
let lastCommentaryAudioUrl = "";
let lastCommentaryOver = "";

async function loadLatestCommentary(autoPlay = false) {
  try {
    const res = await fetch("/api/commentary/latest");
    const data = await res.json();
    if (data.text) {
      const transcriptEl = document.getElementById("commentary-transcript");
      if (transcriptEl) transcriptEl.textContent = `"${data.text}"`;
    }
    if (data.audio_url) {
      const audioEl = document.getElementById("commentary-audio");
      if (audioEl) {
        if (lastCommentaryAudioUrl !== data.audio_url) {
          lastCommentaryAudioUrl = data.audio_url;
          audioEl.src = data.audio_url;
          const autoPlayToggle = document.getElementById("auto-play-voice-toggle");
          if (autoPlay && autoPlayToggle && autoPlayToggle.checked) {
            audioEl.play().catch(e => console.log("Auto-play prevented by browser policy:", e));
          }
        }
      }
    }
  } catch (err) {
    console.error("Error loading commentary:", err);
  }
}

async function triggerManualCommentary() {
  const transcriptEl = document.getElementById("commentary-transcript");
  if (transcriptEl) transcriptEl.textContent = "🎙️ Synthesizing AI broadcast commentary...";
  try {
    const res = await fetch("/api/commentary/generate", { method: "POST" });
    const data = await res.json();
    if (data.text && transcriptEl) {
      transcriptEl.textContent = `"${data.text}"`;
    }
    if (data.audio_url) {
      const audioEl = document.getElementById("commentary-audio");
      if (audioEl) {
        audioEl.src = data.audio_url;
        audioEl.play().catch(e => console.log("Audio play error:", e));
      }
    }
  } catch (err) {
    console.error("Error generating commentary:", err);
    if (transcriptEl) transcriptEl.textContent = "Failed to generate commentary.";
  }
}

// PRISM Live Studio & Tunnel Management
let activeTunnelStatus = null;

async function loadNetworkAndTunnelInfo() {
  try {
    const res = await fetch("/api/network-info");
    const data = await res.json();
    
    // Update Local URL displays
    const quickUrlEl = document.getElementById("quick-ticker-url");
    if (quickUrlEl) quickUrlEl.textContent = data.local_ticker_url;

    const inputLocalEl = document.getElementById("input-local-ticker-url");
    if (inputLocalEl) inputLocalEl.value = data.local_ticker_url;

    const qrLocal = document.getElementById("qr-local-ticker");
    if (qrLocal && data.local_ticker_url) {
      qrLocal.src = `https://api.qrserver.com/v1/create-qr-code/?size=160x160&data=${encodeURIComponent(data.local_ticker_url)}`;
    }

    // Update Tunnel Status
    updateTunnelUI(data.tunnel);
  } catch (err) {
    console.error("Error loading network info:", err);
  }
}

function updateTunnelUI(tunnel) {
  activeTunnelStatus = tunnel;
  const statusBadge = document.getElementById("tunnel-status-badge");
  const inputPublic = document.getElementById("input-public-ticker-url");
  const btnCopyPublic = document.getElementById("btn-copy-public-url");
  const btnTunnelLabel = document.getElementById("btn-tunnel-label");
  const qrPublic = document.getElementById("qr-public-ticker");
  const boxPublicQr = document.getElementById("box-public-qr");

  if (!statusBadge || !inputPublic) return;

  if (tunnel && tunnel.running && tunnel.ticker_url) {
    statusBadge.className = "px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30";
    statusBadge.textContent = "ONLINE (PUBLIC 4G/5G)";
    inputPublic.value = tunnel.ticker_url;
    if (btnCopyPublic) btnCopyPublic.disabled = false;
    if (btnTunnelLabel) btnTunnelLabel.textContent = "Stop Cloudflare Tunnel";
    if (qrPublic) {
      qrPublic.src = `https://api.qrserver.com/v1/create-qr-code/?size=160x160&data=${encodeURIComponent(tunnel.ticker_url)}`;
    }
    if (boxPublicQr) boxPublicQr.classList.remove("hidden");
  } else {
    statusBadge.className = "px-2 py-0.5 rounded text-[10px] font-bold bg-slate-800 text-slate-400 border border-slate-700";
    statusBadge.textContent = "OFFLINE";
    inputPublic.value = "";
    inputPublic.placeholder = "Click 'Launch 4G Tunnel' below";
    if (btnCopyPublic) btnCopyPublic.disabled = true;
    if (btnTunnelLabel) btnTunnelLabel.textContent = "Launch 4G/5G Cloudflare Tunnel";
    if (boxPublicQr) boxPublicQr.classList.add("hidden");
  }
  if (window.lucide) lucide.createIcons();
}

async function toggleCloudflareTunnel() {
  const btnTunnelLabel = document.getElementById("btn-tunnel-label");
  const isRunning = activeTunnelStatus && activeTunnelStatus.running;

  if (btnTunnelLabel) {
    btnTunnelLabel.textContent = isRunning ? "Stopping Tunnel..." : "Starting Cloudflare Tunnel...";
  }

  try {
    const endpoint = isRunning ? "/api/tunnel/stop" : "/api/tunnel/start";
    const res = await fetch(endpoint, { method: "POST" });
    const data = await res.json();
    
    if (data.status === "online" && data.ticker_url) {
      updateTunnelUI({
        available: true,
        running: true,
        public_url: data.public_url,
        ticker_url: data.ticker_url
      });
    } else {
      setTimeout(loadNetworkAndTunnelInfo, 2500);
    }
  } catch (err) {
    console.error("Error toggling tunnel:", err);
    alert("Error controlling tunnel: " + err);
    loadNetworkAndTunnelInfo();
  }
}

function shareUrlViaWhatsApp(inputId) {
  const input = document.getElementById(inputId);
  const url = input ? input.value : "";
  if (!url) {
    alert("No URL available to share yet.");
    return;
  }
  const message = `🏏 PRISM Live Cricket Ticker Overlay Link:\n\n${url}\n\n(Paste this in PRISM Live Studio -> My Studio -> Widget -> Web)`;
  const waUrl = `https://api.whatsapp.com/send?text=${encodeURIComponent(message)}`;
  window.open(waUrl, "_blank");
}

function copyTickerUrl() {
  const input = document.getElementById("input-local-ticker-url");
  const text = input ? input.value : `http://${window.location.hostname}:8000/ticker`;
  navigator.clipboard.writeText(text).then(() => {
    alert("Copied PRISM Live Ticker URL:\n" + text + "\n\nPaste this in PRISM Live Studio Web Widget!");
  }).catch(() => {
    prompt("Copy this PRISM Live Ticker URL:", text);
  });
}

function copyToClipboard(elementId) {
  const el = document.getElementById(elementId);
  if (!el) return;
  el.select();
  el.setSelectionRange(0, 99999);
  navigator.clipboard.writeText(el.value).then(() => {
    alert("Copied to clipboard:\n" + el.value);
  }).catch(() => {
    prompt("Copy this URL:", el.value);
  });
}

function setPreviewPosition(pos) {
  const iframe = document.getElementById("preview-ticker-iframe");
  const btnBottom = document.getElementById("btn-pos-bottom");
  const btnTop = document.getElementById("btn-pos-top");
  const localInput = document.getElementById("input-local-ticker-url");
  const publicInput = document.getElementById("input-public-ticker-url");
  const qrLocal = document.getElementById("qr-local-ticker");
  const qrPublic = document.getElementById("qr-public-ticker");

  if (pos === 'top') {
    if (iframe) iframe.src = "/ticker?pos=top";
    if (btnTop) btnTop.className = "px-3 py-1.5 rounded-lg font-bold text-xs text-blue-400 bg-slate-800 shadow-sm transition";
    if (btnBottom) btnBottom.className = "px-3 py-1.5 rounded-lg font-bold text-xs text-slate-400 hover:text-slate-200 transition";
    
    if (localInput && !localInput.value.includes("?pos=top")) {
      localInput.value = localInput.value.split("?")[0] + "?pos=top";
      if (qrLocal) qrLocal.src = `https://api.qrserver.com/v1/create-qr-code/?size=160x160&data=${encodeURIComponent(localInput.value)}`;
    }
    if (publicInput && publicInput.value && !publicInput.value.includes("?pos=top")) {
      publicInput.value = publicInput.value.split("?")[0] + "?pos=top";
      if (qrPublic) qrPublic.src = `https://api.qrserver.com/v1/create-qr-code/?size=160x160&data=${encodeURIComponent(publicInput.value)}`;
    }
  } else {
    if (iframe) iframe.src = "/ticker";
    if (btnBottom) btnBottom.className = "px-3 py-1.5 rounded-lg font-bold text-xs text-blue-400 bg-slate-800 shadow-sm transition";
    if (btnTop) btnTop.className = "px-3 py-1.5 rounded-lg font-bold text-xs text-slate-400 hover:text-slate-200 transition";
    
    if (localInput) {
      localInput.value = localInput.value.replace("?pos=top", "");
      if (qrLocal) qrLocal.src = `https://api.qrserver.com/v1/create-qr-code/?size=160x160&data=${encodeURIComponent(localInput.value)}`;
    }
    if (publicInput && publicInput.value) {
      publicInput.value = publicInput.value.replace("?pos=top", "");
      if (qrPublic) qrPublic.src = `https://api.qrserver.com/v1/create-qr-code/?size=160x160&data=${encodeURIComponent(publicInput.value)}`;
    }
  }
}
