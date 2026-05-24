import {
  parseEnvelope,
  COUNTDOWN_MS,
  type Envelope,
  type RoomState,
  type Settings,
  type WinConditionKey,
} from "./protocol";

const WS_BASE = (import.meta.env.VITE_WS_URL as string | undefined) ?? "ws://localhost:8787";
// HTTP base derived from WS base — same host, http(s) instead of ws(s).
const HTTP_BASE = WS_BASE.replace(/^ws/, "http");

// ─── Token cookie ────────────────────────────────────────────────────────────

function getOrCreateToken(): string {
  const m = document.cookie.match(/(?:^|;\s*)bingo_token=([^;]+)/);
  if (m) return m[1];
  const t = crypto.randomUUID();
  document.cookie = `bingo_token=${t}; path=/; max-age=${365 * 24 * 3600}; SameSite=Lax`;
  return t;
}

const myToken = getOrCreateToken();

// ─── State ───────────────────────────────────────────────────────────────────

let currentState: RoomState | null = null;
let socket: WebSocket | null = null;
let myNickname = "";
let myRoomCode = "";
let retryCount = 0;
const MAX_RETRIES = 5;

// ─── DOM refs ────────────────────────────────────────────────────────────────

const joinSection     = document.getElementById("join")     as HTMLDivElement;
const lobbySection    = document.getElementById("lobby")    as HTMLDivElement;
const startingSection = document.getElementById("starting") as HTMLDivElement;
const boardSection    = document.getElementById("board")    as HTMLDivElement;
const endSection      = document.getElementById("end")      as HTMLDivElement;
const logSection     = document.getElementById("log")     as HTMLDivElement;

const landingDiv     = document.getElementById("landing")   as HTMLDivElement;
const hostFormDiv    = document.getElementById("host-form") as HTMLDivElement;
const joinFormDiv    = document.getElementById("join-form") as HTMLDivElement;
const hostNicknameInput = document.getElementById("host-nickname") as HTMLInputElement;
const joinNicknameInput = document.getElementById("join-nickname") as HTMLInputElement;
const joinRoomCodeInput = document.getElementById("join-room-code") as HTMLInputElement;
const hostCreateBtn  = document.getElementById("host-create-btn") as HTMLButtonElement;
const joinGoBtn      = document.getElementById("join-go-btn") as HTMLButtonElement;
const btnShowHost    = document.getElementById("btn-show-host") as HTMLButtonElement;
const btnShowJoin    = document.getElementById("btn-show-join") as HTMLButtonElement;
const hostBackBtn    = document.getElementById("host-back-btn") as HTMLButtonElement;
const joinBackBtn    = document.getElementById("join-back-btn") as HTMLButtonElement;
const hostErrorEl    = document.getElementById("host-error") as HTMLDivElement;
const joinErrorEl    = document.getElementById("join-error") as HTMLDivElement;
const statusEl       = document.getElementById("status")    as HTMLDivElement;

function showPreConnect(mode: "landing" | "host" | "join"): void {
  landingDiv.style.display  = mode === "landing" ? "block" : "none";
  hostFormDiv.style.display = mode === "host"    ? "block" : "none";
  joinFormDiv.style.display = mode === "join"    ? "block" : "none";
  hostErrorEl.textContent = "";
  joinErrorEl.textContent = "";
}
btnShowHost.addEventListener("click", () => showPreConnect("host"));
btnShowJoin.addEventListener("click", () => showPreConnect("join"));
hostBackBtn.addEventListener("click", () => showPreConnect("landing"));
joinBackBtn.addEventListener("click", () => showPreConnect("landing"));
const logContent     = document.getElementById("log-content") as HTMLDivElement;
const logToggle      = document.getElementById("log-toggle") as HTMLButtonElement;

// ─── Sections ────────────────────────────────────────────────────────────────

function showSection(phase: "join" | "lobby" | "starting" | "playing" | "ended"): void {
  joinSection.style.display     = phase === "join"     ? "block" : "none";
  lobbySection.style.display    = phase === "lobby"    ? "block" : "none";
  startingSection.style.display = phase === "starting" ? "block" : "none";
  boardSection.style.display    = phase === "playing"  ? "block" : "none";
  endSection.style.display      = phase === "ended"    ? "block" : "none";
}

// ─── Log ─────────────────────────────────────────────────────────────────────

function appendLog(text: string): void {
  const div = document.createElement("div");
  const ts = new Date().toLocaleTimeString();
  div.textContent = `[${ts}] ${text}`;
  logContent.appendChild(div);
  logContent.scrollTop = logContent.scrollHeight;
}

logToggle.addEventListener("click", () => {
  const hidden = logContent.style.display === "none";
  logContent.style.display = hidden ? "block" : "none";
  logToggle.textContent = hidden ? "Hide log" : "Show log";
});

// Delegated click handler — survives the lobby's full-DOM rebuild on every state echo.
// Without this, the Start button can be replaced mid-click and the event is lost.
lobbySection.addEventListener("click", (e) => {
  const target = e.target as HTMLElement | null;
  if (target?.id === "start-btn" && !(target as HTMLButtonElement).disabled) {
    send({ t: "start", data: {} });
  }
});

// ─── Send ─────────────────────────────────────────────────────────────────────

function send(envelope: Omit<Envelope, "ts">): void {
  if (!socket || socket.readyState !== WebSocket.OPEN) return;
  const payload = JSON.stringify({ ...envelope, ts: Date.now() });
  socket.send(payload);
}

// ─── Connect ─────────────────────────────────────────────────────────────────

// Tracks host intent on the latest connect attempt so reconnects use the same query.
let connectAsHost = false;
// Distinguishes "WS upgrade was rejected (room missing)" from "WS opened then dropped".
let everOpened = false;

function connect(): void {
  const qs = connectAsHost ? "?host=1" : "";
  const url = `${WS_BASE}/ws/${encodeURIComponent(myRoomCode)}${qs}`;
  console.log(`[${new Date().toISOString()}] [client] Connecting to ${url}`);
  statusEl.textContent = `Connecting to room "${myRoomCode}"…`;
  everOpened = false;

  socket = new WebSocket(url);

  socket.addEventListener("open", () => {
    console.log(`[${new Date().toISOString()}] [client] WebSocket open`);
    retryCount = 0;
    everOpened = true;
    statusEl.textContent = `Connected to room "${myRoomCode}" as "${myNickname}".`;
    send({ t: "hello", data: { token: myToken, nickname: myNickname } });
  });

  socket.addEventListener("message", (event) => {
    const raw = typeof event.data === "string" ? event.data : "[binary]";
    console.log(`[${new Date().toISOString()}] [client] recv: ${raw.slice(0, 120)}`);
    handleMessage(raw);
  });

  socket.addEventListener("close", (event) => {
    console.log(`[${new Date().toISOString()}] [client] WebSocket closed — code=${event.code}`);
    socket = null;

    // Close before open = upgrade rejected (server returned 404 from the join-only gate).
    if (!everOpened && !connectAsHost) {
      myRoomCode = "";
      statusEl.textContent = "Not connected.";
      showSection("join");
      showPreConnect("join");
      joinErrorEl.textContent = "Room not found — check the code with your host.";
      return;
    }

    statusEl.textContent = `Disconnected (code ${event.code}).`;
    if (retryCount < MAX_RETRIES && myRoomCode) {
      retryCount++;
      appendLog(`*** Disconnected. Reconnecting (${retryCount}/${MAX_RETRIES})…`);
      // Reconnects don't need host=1 — once members exist, the join_only gate passes.
      connectAsHost = false;
      setTimeout(connect, 2000);
    } else {
      appendLog("*** Disconnected. Stopped retrying.");
    }
  });

  socket.addEventListener("error", () => {
    console.log(`[${new Date().toISOString()}] [client] WebSocket error`);
    // Don't overwrite the room-not-found message that close handler will set.
    if (everOpened) statusEl.textContent = "Connection error.";
  });
}

hostCreateBtn.addEventListener("click", async () => {
  const nick = hostNicknameInput.value.trim();
  if (!nick) { hostErrorEl.textContent = "Please enter a nickname."; return; }
  hostCreateBtn.disabled = true;
  hostErrorEl.textContent = "";
  try {
    const res = await fetch(`${HTTP_BASE}/create-room`, { method: "POST" });
    if (!res.ok) throw new Error(`create-room failed: ${res.status}`);
    const { code } = await res.json() as { code: string };
    myNickname = nick;
    myRoomCode = code;
    retryCount = 0;
    connectAsHost = true;
    connect();
  } catch (err) {
    hostErrorEl.textContent = `Could not create room: ${(err as Error).message}`;
    hostCreateBtn.disabled = false;
  }
});

joinGoBtn.addEventListener("click", () => {
  const nick = joinNicknameInput.value.trim();
  const room = joinRoomCodeInput.value.trim().toUpperCase();
  if (!nick || !room) { joinErrorEl.textContent = "Please enter a nickname and room code."; return; }
  joinErrorEl.textContent = "";
  myNickname = nick;
  myRoomCode = room;
  retryCount = 0;
  connectAsHost = false;
  connect();
});

// ─── Message dispatch ─────────────────────────────────────────────────────────

function handleMessage(raw: string): void {
  const env = parseEnvelope(raw);
  if (!env) {
    appendLog(`[parse error] ${raw.slice(0, 80)}`);
    return;
  }
  appendLog(`[${env.t}] ${raw.slice(0, 100)}`);

  switch (env.t) {
    case "state": {
      currentState = env.data;
      renderForPhase();
      break;
    }
    case "end": {
      appendLog(`*** Game over! Team ${env.data.teamId + 1} won by ${env.data.condition}`);
      break;
    }
    case "chat": {
      appendLog(env.data.body);
      break;
    }
    case "error": {
      appendLog(`[server error] ${env.data.message}${env.data.reason ? ` (${env.data.reason})` : ""}`);
      break;
    }
  }
}

function renderForPhase(): void {
  if (!currentState) return;
  // Stop any running countdown unless we're (re-)entering the starting phase.
  if (currentState.phase !== "starting") stopCountdown();
  switch (currentState.phase) {
    case "lobby":    showSection("lobby");    renderLobby();    break;
    case "starting": showSection("starting"); renderStarting(); break;
    case "playing":  showSection("playing");  renderBoard();    break;
    case "ended":    showSection("ended");    renderEnd();      break;
  }
}

// ─── Starting countdown ───────────────────────────────────────────────────────

let countdownIntervalId: number | null = null;

function stopCountdown(): void {
  if (countdownIntervalId !== null) {
    clearInterval(countdownIntervalId);
    countdownIntervalId = null;
  }
}

function renderStarting(): void {
  if (!currentState || currentState.startingAt === null) return;
  const startingAt = currentState.startingAt;
  const container = document.getElementById("starting-inner")!;
  container.innerHTML = "";

  const banner = el("div", { style: "font-size:0.9rem;color:#aaa;margin-bottom:24px;" });
  banner.textContent = "Game starting…";
  container.appendChild(banner);

  const number = el("div", { style: "font-size:8rem;font-weight:bold;color:#a78bfa;line-height:1;" });
  container.appendChild(number);

  const update = () => {
    const remainingMs = startingAt + COUNTDOWN_MS - Date.now();
    if (remainingMs <= 0) {
      number.textContent = "GO";
      stopCountdown();
      return;
    }
    // Cap to absorb client/server clock skew — without this, a client whose clock lags briefly shows "4".
    const cap = Math.ceil(COUNTDOWN_MS / 1000);
    number.textContent = String(Math.min(cap, Math.ceil(remainingMs / 1000)));
  };
  update();
  stopCountdown();
  countdownIntervalId = window.setInterval(update, 100);
}

// ─── Lobby render ─────────────────────────────────────────────────────────────

function renderLobby(): void {
  if (!currentState) return;
  const state = currentState;
  const amHost = state.hostToken === myToken;
  const myTeamId = state.members[myToken]?.teamId ?? null;

  const container = document.getElementById("lobby-inner")!;
  container.innerHTML = "";

  // Room code display + Copy button
  const codeDiv = el("div", { style: "margin-bottom:16px;font-size:1.2rem;display:flex;align-items:center;gap:8px;" });
  const codeLabel = document.createElement("span");
  codeLabel.textContent = "Room: ";
  const codeValue = document.createElement("span");
  codeValue.textContent = myRoomCode;
  codeValue.style.cssText = "font-weight:bold;letter-spacing:2px;background:#222;padding:2px 8px;border-radius:3px;";
  const copyBtn = document.createElement("button") as HTMLButtonElement;
  copyBtn.textContent = "📋 Copy";
  copyBtn.style.cssText = "font-size:0.8rem;padding:4px 8px;";
  copyBtn.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(myRoomCode);
      copyBtn.textContent = "✓ Copied";
      setTimeout(() => { copyBtn.textContent = "📋 Copy"; }, 1500);
    } catch {
      copyBtn.textContent = "Copy failed";
    }
  });
  codeDiv.appendChild(codeLabel);
  codeDiv.appendChild(codeValue);
  codeDiv.appendChild(copyBtn);
  container.appendChild(codeDiv);

  // Members list grouped by team
  const membersDiv = el("div", { style: "margin-bottom:16px;" });
  const membersTitle = el("h3", {});
  membersTitle.textContent = "Members";
  membersDiv.appendChild(membersTitle);

  // Unassigned
  const unassigned = Object.entries(state.members).filter(([, m]) => m.teamId === null);
  if (unassigned.length > 0) {
    const ul = el("ul", {});
    for (const [tok, m] of unassigned) {
      const li = el("li", { style: `color:${m.online ? "#eee" : "#666"}` });
      li.textContent = `${m.nickname}${tok === myToken ? " (you)" : ""}${tok === state.hostToken ? " 👑" : ""}${!m.online ? " [offline]" : ""}`;
      ul.appendChild(li);
    }
    const label = el("div", { style: "color:#aaa;font-size:0.85rem;" });
    label.textContent = "No team:";
    membersDiv.appendChild(label);
    membersDiv.appendChild(ul);
  }

  // Per-team
  for (const team of state.teams) {
    if (team.memberTokens.length === 0) continue;
    const teamDiv = el("div", { style: `border-left:4px solid ${team.color};padding-left:8px;margin-bottom:8px;` });
    const teamLabel = el("div", { style: "font-weight:bold;" });
    teamLabel.textContent = team.name;
    teamDiv.appendChild(teamLabel);
    const ul = el("ul", {});
    for (const tok of team.memberTokens) {
      const m = state.members[tok];
      if (!m) continue;
      const li = el("li", { style: `color:${m.online ? "#eee" : "#666"}` });
      li.textContent = `${m.nickname}${tok === myToken ? " (you)" : ""}${tok === state.hostToken ? " 👑" : ""}${tok === team.leaderToken ? " ★" : ""}${!m.online ? " [offline]" : ""}`;
      ul.appendChild(li);
    }
    teamDiv.appendChild(ul);
    membersDiv.appendChild(teamDiv);
  }
  container.appendChild(membersDiv);

  // Team picker
  const pickerDiv = el("div", { style: "margin-bottom:16px;" });
  const pickerTitle = el("h3", {});
  pickerTitle.textContent = "Pick a team";
  pickerDiv.appendChild(pickerTitle);

  const btnRow = el("div", { style: "display:flex;flex-wrap:wrap;gap:8px;" });
  for (const team of state.teams) {
    const btn = el("button", {
      style: `background:${team.color};border:none;padding:8px 12px;border-radius:4px;cursor:pointer;font-family:monospace;color:#000;font-weight:bold;${myTeamId === team.id ? "outline:3px solid #fff;" : ""}`,
    }) as HTMLButtonElement;
    btn.textContent = team.name;
    btn.addEventListener("click", () => {
      send({ t: "team_join", data: { teamId: team.id } });
    });
    btnRow.appendChild(btn);
  }
  if (myTeamId !== null) {
    const leaveBtn = el("button", { style: "padding:8px 12px;border-radius:4px;cursor:pointer;font-family:monospace;" }) as HTMLButtonElement;
    leaveBtn.textContent = "Leave team";
    leaveBtn.addEventListener("click", () => {
      send({ t: "team_join", data: { teamId: null } });
    });
    btnRow.appendChild(leaveBtn);
  }
  pickerDiv.appendChild(btnRow);
  container.appendChild(pickerDiv);

  // Settings (host only)
  if (amHost) {
    const settingsDiv = renderSettingsForm(state.settings);
    container.appendChild(settingsDiv);
  }

  // Start button (host only)
  if (amHost) {
    const teamsWithMembers = state.teams.filter((t) => t.memberTokens.length > 0);
    const allHaveLeaders = teamsWithMembers.every((t) => t.leaderToken !== null);
    const canStart = teamsWithMembers.length >= 1 && allHaveLeaders;

    const startBtn = el("button", {
      id: "start-btn",
      style: "padding:10px 24px;background:#2563eb;color:#fff;border:none;border-radius:4px;cursor:pointer;font-family:monospace;font-size:1rem;margin-top:12px;",
    }) as HTMLButtonElement;
    startBtn.textContent = "Start Game";
    startBtn.disabled = !canStart;
    startBtn.title = canStart ? "" : "Need at least one team with a leader";
    // Click handled via delegation on lobbySection (see init).
    container.appendChild(startBtn);
  } else {
    const waiting = el("div", { style: "margin-top:12px;color:#aaa;" });
    waiting.textContent = "Waiting for host to start the game…";
    container.appendChild(waiting);
  }
}

function renderSettingsForm(settings: Settings): HTMLElement {
  const wrapper = el("div", { style: "border:1px solid #444;padding:16px;border-radius:4px;margin-bottom:16px;" });
  const title = el("h3", {});
  title.textContent = "Settings (host)";
  wrapper.appendChild(title);

  // Board size
  wrapper.appendChild(labelText("Board size:"));
  const sizeRow = el("div", { style: "display:flex;gap:12px;margin-bottom:12px;" });
  for (const s of [5, 7, 9] as (5 | 7 | 9)[]) {
    const radio = el("label", {});
    const inp = document.createElement("input");
    inp.type = "radio";
    inp.name = "boardSize";
    inp.value = String(s);
    inp.checked = settings.boardSize === s;
    inp.addEventListener("change", () => {
      sendUpdatedSettings({ ...settings, boardSize: s });
    });
    radio.appendChild(inp);
    radio.append(` ${s}×${s}`);
    sizeRow.appendChild(radio);
  }
  wrapper.appendChild(sizeRow);

  // Sections
  wrapper.appendChild(labelText("Sections:"));
  const sectionsRow = el("div", { style: "display:flex;gap:12px;margin-bottom:12px;flex-wrap:wrap;" });
  for (const sec of ["standard", "level_completion", "modded"] as Settings["sections"][number][]) {
    const lbl = el("label", {});
    const inp = document.createElement("input");
    inp.type = "checkbox";
    inp.checked = settings.sections.includes(sec);
    inp.addEventListener("change", () => {
      const newSections = inp.checked
        ? ([...settings.sections, sec] as Settings["sections"])
        : (settings.sections.filter((s) => s !== sec) as Settings["sections"]);
      if (newSections.length === 0) { inp.checked = true; return; }
      sendUpdatedSettings({ ...settings, sections: newSections });
    });
    lbl.appendChild(inp);
    lbl.append(` ${sec}`);
    sectionsRow.appendChild(lbl);
  }
  wrapper.appendChild(sectionsRow);

  // Allow modded
  wrapper.appendChild(makeCheckbox("Allow modded squares", settings.allowModded, (v) => {
    sendUpdatedSettings({ ...settings, allowModded: v });
  }));

  // Center free
  wrapper.appendChild(makeCheckbox("Center free square", settings.centerFree, (v) => {
    sendUpdatedSettings({ ...settings, centerFree: v });
  }));

  // Lockout — ON = first team to claim owns it. OFF = multiple teams may claim
  // the same cell (rendered as horizontal stripes).
  wrapper.appendChild(makeCheckbox("Lockout (one team per square)", settings.lockout, (v) => {
    sendUpdatedSettings({ ...settings, lockout: v });
  }));

  // Time limit
  wrapper.appendChild(labelText("Time limit (minutes):"));
  const timeInput = document.createElement("input");
  timeInput.type = "number";
  timeInput.value = String(settings.timeLimitMin);
  timeInput.style.cssText = "width:100px;padding:4px;background:#222;border:1px solid #444;color:#eee;font-family:monospace;border-radius:3px;margin-bottom:12px;";
  timeInput.addEventListener("change", () => {
    const v = parseInt(timeInput.value, 10);
    if (!isNaN(v) && v > 0) sendUpdatedSettings({ ...settings, timeLimitMin: v });
  });
  wrapper.appendChild(timeInput);
  wrapper.appendChild(document.createElement("br"));

  // Win conditions
  wrapper.appendChild(labelText("Win conditions:"));
  const winRow = el("div", { style: "display:flex;gap:12px;margin-bottom:12px;flex-wrap:wrap;" });
  const allWins: WinConditionKey[] = ["line", "four_corners", "full_house", "first_to_n", "time_limit"];
  for (const wc of allWins) {
    const lbl = el("label", {});
    const inp = document.createElement("input");
    inp.type = "checkbox";
    inp.checked = settings.winConditions.includes(wc);
    inp.addEventListener("change", () => {
      const newWins = inp.checked
        ? ([...settings.winConditions, wc] as WinConditionKey[])
        : settings.winConditions.filter((w) => w !== wc);
      sendUpdatedSettings({ ...settings, winConditions: newWins });
    });
    lbl.appendChild(inp);
    lbl.append(` ${wc}`);
    winRow.appendChild(lbl);
  }
  wrapper.appendChild(winRow);

  // first_to_n value (only show if first_to_n selected)
  if (settings.winConditions.includes("first_to_n")) {
    wrapper.appendChild(labelText("First to N (count):"));
    const nInput = document.createElement("input");
    nInput.type = "number";
    nInput.value = String(settings.firstToN ?? 5);
    nInput.style.cssText = "width:80px;padding:4px;background:#222;border:1px solid #444;color:#eee;font-family:monospace;border-radius:3px;margin-bottom:12px;";
    nInput.addEventListener("change", () => {
      const v = parseInt(nInput.value, 10);
      if (!isNaN(v) && v > 0) sendUpdatedSettings({ ...settings, firstToN: v });
    });
    wrapper.appendChild(nInput);
  }

  return wrapper;
}

function sendUpdatedSettings(s: Settings): void {
  send({ t: "settings", data: s });
}

// ─── Board render ─────────────────────────────────────────────────────────────

function renderBoard(): void {
  if (!currentState?.board) return;
  const state = currentState;
  const { boardSize } = state.settings;
  const myTeamId = state.members[myToken]?.teamId ?? null;
  const myTeam = myTeamId !== null ? state.teams[myTeamId] : null;
  const amLeader = myTeam?.leaderToken === myToken;

  const container = document.getElementById("board-inner")!;
  container.innerHTML = "";

  // Claim counts per team — FREE sentinel counts for every team.
  const countsDiv = el("div", { style: "margin-bottom:12px;display:flex;gap:12px;flex-wrap:wrap;" });
  for (const team of state.teams) {
    const count = state.claims.filter((c) => cellCountsFor(c, team.id)).length;
    if (team.memberTokens.length === 0 && count === 0) continue;
    const badge = el("span", { style: `background:${team.color};color:#000;padding:4px 8px;border-radius:4px;font-weight:bold;` });
    badge.textContent = `${team.name}: ${count}`;
    countsDiv.appendChild(badge);
  }
  container.appendChild(countsDiv);

  if (!amLeader && myTeamId !== null) {
    const note = el("div", { style: "color:#aaa;margin-bottom:8px;font-size:0.85rem;" });
    note.textContent = "Only your team leader can claim squares.";
    container.appendChild(note);
  }
  if (myTeamId === null) {
    const note = el("div", { style: "color:#aaa;margin-bottom:8px;font-size:0.85rem;" });
    note.textContent = "You are not on a team — spectating.";
    container.appendChild(note);
  }

  // Grid
  const cellSize = Math.max(70, Math.floor(560 / boardSize));
  const grid = el("div", {
    style: `display:grid;grid-template-columns:repeat(${boardSize},${cellSize}px);grid-auto-rows:minmax(${cellSize}px,auto);gap:4px;`,
  });

  const winShape = state.winner?.shape ?? null;

  for (let i = 0; i < boardSize ** 2; i++) {
    const square = state.board!.squares[i];
    const claim = state.claims[i];
    const isFree = cellIsFree(claim);
    const inWinShape = winShape?.includes(i);
    const clickable = amLeader && !isFree;

    const bg = cellBackground(claim, state.teams);
    const textColor = claim ? "#000" : "#eee";
    const border = inWinShape ? "3px solid #fff" : "1px solid #444";

    const cell = el("div", {
      style: `background:${bg};color:${textColor};border:${border};width:${cellSize}px;min-height:${cellSize}px;box-sizing:border-box;padding:4px;font-size:0.7rem;display:flex;align-items:center;justify-content:center;text-align:center;cursor:${clickable ? "pointer" : "default"};border-radius:3px;word-break:break-word;`,
      title: square + cellTitle(claim),
    });

    const nameSpan = document.createElement("span");
    nameSpan.style.cssText = "background:rgba(255,255,255,0.6);padding:0 3px;border-radius:2px;";
    nameSpan.textContent = isFree ? "FREE" : square;
    cell.appendChild(nameSpan);

    if (clickable) {
      cell.addEventListener("click", () => handleCellClick(i));
    }

    grid.appendChild(cell);
  }

  container.appendChild(grid);
}

function handleCellClick(squareIndex: number): void {
  if (!currentState) return;
  const member = currentState.members[myToken];
  if (!member || member.teamId === null) return;
  const existing = currentState.claims[squareIndex];

  if (existing === null) {
    send({ t: "claim", data: { squareIndex, timeMs: null } });
    return;
  }
  if (existing.some((c) => c.teamId === -1)) return; // FREE — no-op
  if (existing.some((c) => c.teamId === member.teamId)) {
    send({ t: "unclaim", data: { squareIndex } });
    return;
  }
  // Cell owned by other team(s) but not me. Multi-claim only allowed when lockout is OFF.
  if (!currentState.settings.lockout) {
    send({ t: "claim", data: { squareIndex, timeMs: null } });
  }
}

// ─── End screen ───────────────────────────────────────────────────────────────

function renderEnd(): void {
  if (!currentState) return;
  const state = currentState;

  const container = document.getElementById("end-inner")!;
  container.innerHTML = "";

  const winner = state.winner;
  if (winner) {
    const team = state.teams[winner.teamId];
    const banner = el("h2", { style: `color:${team.color};margin-bottom:16px;` });
    banner.textContent = `${team.name} won by ${winner.condition}!`;
    container.appendChild(banner);
  } else {
    const banner = el("h2", {});
    banner.textContent = "Game over — no winner.";
    container.appendChild(banner);
  }

  // Final board (read-only, winning shape highlighted)
  if (state.board) {
    const { boardSize } = state.settings;
    const winShape = state.winner?.shape ?? null;
    const cellSize = Math.max(60, Math.floor(480 / boardSize));

    const grid = el("div", {
      style: `display:grid;grid-template-columns:repeat(${boardSize},${cellSize}px);grid-auto-rows:minmax(${cellSize}px,auto);gap:4px;margin-bottom:16px;`,
    });

    for (let i = 0; i < boardSize ** 2; i++) {
      const square = state.board.squares[i];
      const claim = state.claims[i];
      const isFree = cellIsFree(claim);
      const inWinShape = winShape?.includes(i);

      const bg = cellBackground(claim, state.teams);
      const textColor = claim ? "#000" : "#eee";
      const border = inWinShape ? "3px solid #fff" : "1px solid #444";

      const cell = el("div", {
        style: `background:${bg};color:${textColor};border:${border};width:${cellSize}px;min-height:${cellSize}px;box-sizing:border-box;padding:4px;font-size:0.65rem;display:flex;align-items:center;justify-content:center;text-align:center;border-radius:3px;word-break:break-word;`,
        title: square + cellTitle(claim),
      });
      const nameSpan = document.createElement("span");
      nameSpan.style.cssText = "background:rgba(255,255,255,0.6);padding:0 3px;border-radius:2px;";
      nameSpan.textContent = isFree ? "FREE" : square;
      cell.appendChild(nameSpan);
      grid.appendChild(cell);
    }

    container.appendChild(grid);
  }

  // Host action row: Replay (same board) / New board / Back to lobby. Disabled
  // for non-host members; they wait for the host to pick.
  const amHost = state.hostToken === myToken;
  const actionRow = el("div", { style: "display:flex;gap:8px;flex-wrap:wrap;margin-bottom:16px;" });

  const mkActionBtn = (label: string, mode: "same" | "new" | "lobby", bg: string): HTMLButtonElement => {
    const b = el("button", {
      style: `padding:10px 18px;background:${bg};color:#fff;border:none;border-radius:4px;cursor:${amHost ? "pointer" : "default"};font-family:monospace;font-size:0.95rem;${amHost ? "" : "opacity:0.4;"}`,
    }) as HTMLButtonElement;
    b.textContent = label;
    b.disabled = !amHost;
    if (amHost) b.addEventListener("click", () => send({ t: "restart", data: { mode } }));
    return b;
  };

  actionRow.appendChild(mkActionBtn("Replay (same board)", "same", "#2563eb"));
  actionRow.appendChild(mkActionBtn("New board",           "new",  "#16a34a"));
  actionRow.appendChild(mkActionBtn("Back to lobby",       "lobby", "#6b7280"));
  container.appendChild(actionRow);

  if (!amHost) {
    const note = el("div", { style: "color:#aaa;font-size:0.85rem;margin-bottom:16px;" });
    note.textContent = "Waiting for host to pick a next step…";
    container.appendChild(note);
  }

  // Always-available: leave the room entirely.
  const leaveBtn = el("button", {
    style: "padding:8px 18px;background:#374151;color:#eee;border:1px solid #555;border-radius:4px;cursor:pointer;font-family:monospace;font-size:0.85rem;",
  }) as HTMLButtonElement;
  leaveBtn.textContent = "Leave room";
  leaveBtn.addEventListener("click", () => {
    currentState = null;
    socket?.close();
    socket = null;
    myRoomCode = "";
    retryCount = MAX_RETRIES; // prevent auto-reconnect
    showSection("join");
  });
  container.appendChild(leaveBtn);
}

// ─── Cell helpers (claim is ClaimInfo[] | null) ───────────────────────────────

function cellIsFree(claim: import("./protocol").ClaimInfo[] | null): boolean {
  return claim?.some((c) => c.teamId === -1) ?? false;
}

function cellCountsFor(claim: import("./protocol").ClaimInfo[] | null, teamId: number): boolean {
  if (!claim) return false;
  return claim.some((c) => c.teamId === teamId || c.teamId === -1);
}

function cellBackground(claim: import("./protocol").ClaimInfo[] | null, teams: import("./protocol").TeamInfo[]): string {
  if (!claim || claim.length === 0) return "#222";
  if (cellIsFree(claim)) return "#888";
  if (claim.length === 1) return teams[claim[0].teamId].color;
  // Multiple teams — horizontal stripes, equal bands top-to-bottom.
  const colors = claim.map((c) => teams[c.teamId].color);
  const n = colors.length;
  const stops = colors
    .flatMap((color, i) => [
      `${color} ${((i * 100) / n).toFixed(2)}%`,
      `${color} ${(((i + 1) * 100) / n).toFixed(2)}%`,
    ])
    .join(", ");
  return `linear-gradient(to bottom, ${stops})`;
}

function cellTitle(claim: import("./protocol").ClaimInfo[] | null): string {
  if (!claim || claim.length === 0) return "";
  return "\n" + claim.map((c) => {
    if (c.teamId === -1) return "FREE";
    const t = c.timeMs != null ? ` (${(c.timeMs / 1000).toFixed(2)}s)` : "";
    return `${c.player}${t}`;
  }).join(", ");
}

// ─── DOM helpers ──────────────────────────────────────────────────────────────

function el(tag: string, attrs: Record<string, string>): HTMLElement {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    e.setAttribute(k, v);
  }
  return e;
}

function labelText(text: string): HTMLElement {
  const lbl = el("div", { style: "font-size:0.85rem;color:#aaa;margin-bottom:4px;" });
  lbl.textContent = text;
  return lbl;
}

function makeCheckbox(label: string, checked: boolean, onChange: (v: boolean) => void): HTMLElement {
  const wrapper = el("div", { style: "margin-bottom:12px;" });
  const lbl = el("label", {});
  const inp = document.createElement("input");
  inp.type = "checkbox";
  inp.checked = checked;
  inp.addEventListener("change", () => onChange(inp.checked));
  lbl.appendChild(inp);
  lbl.append(` ${label}`);
  wrapper.appendChild(lbl);
  return wrapper;
}

// ─── Init ────────────────────────────────────────────────────────────────────

showSection("join");
