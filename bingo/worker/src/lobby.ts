import { DurableObject } from "cloudflare:workers";
import {
  parseEnvelope,
  makeInitialState,
  COUNTDOWN_MS,
  type RoomState,
  type MemberInfo,
  type ClaimInfo,
  type Envelope,
  type EndMsg,
  type ErrorMsg,
  type State,
  type Chat,
} from "./protocol";
import { generateBoard, evaluateWin, evalTimeLimit } from "./board";

const CHAT_HISTORY_CAP = 50;

function coord(squareIndex: number, boardSize: number): string {
  const r = Math.floor(squareIndex / boardSize);
  const c = squareIndex % boardSize;
  return `${String.fromCharCode(65 + c)}${r + 1}`;
}

export class LobbyDO extends DurableObject {
  private room: RoomState = makeInitialState();
  // Standard (non-hibernating) accept: DO instance stays alive while any socket
  // is connected, so in-memory state (room, wsTokens) persists naturally.
  // Plan explicitly accepts the trade-off: "DO state is in-memory only during
  // a room's lifetime; once the last player disconnects, the room dies."
  private sockets = new Set<WebSocket>();
  private wsTokens = new Map<WebSocket, string>();
  private chatHistory: Chat[] = [];

  async fetch(request: Request): Promise<Response> {
    const upgradeHeader = request.headers.get("Upgrade");
    if (!upgradeHeader || upgradeHeader.toLowerCase() !== "websocket") {
      return new Response("Expected WebSocket upgrade", { status: 426 });
    }

    // Join-only gate: reject WS upgrades that didn't declare host intent (?host=1)
    // when this room has no members. Prevents "typo creates ghost lobby" — the
    // joiner gets a clean 404 instead of silently landing in an empty room.
    // A returning member always passes because their token is already in members.
    const url = new URL(request.url);
    const isHost = url.searchParams.get("host") === "1";
    const memberCount = Object.keys(this.room.members).length;
    if (!isHost && memberCount === 0) {
      return new Response("Room not found", { status: 404 });
    }

    const pair = new WebSocketPair();
    const [client, server] = Object.values(pair);
    server.accept();
    this.sockets.add(server);

    server.addEventListener("message", (event: MessageEvent) => {
      const raw = typeof event.data === "string" ? event.data : new TextDecoder().decode(event.data as ArrayBuffer);
      this.handleMessage(server, raw);
    });
    server.addEventListener("close", (event: CloseEvent) => {
      console.log(`[${new Date().toISOString()}] [worker] WebSocket closed — code=${event.code} reason=${event.reason}`);
      this.sockets.delete(server);
      this.handleDisconnect(server);
    });
    server.addEventListener("error", (event: Event) => {
      console.log(`[${new Date().toISOString()}] [worker] WebSocket error — ${String(event)}`);
      this.sockets.delete(server);
      this.handleDisconnect(server);
    });

    console.log(`[${new Date().toISOString()}] [worker] WebSocket accepted; total sockets: ${this.sockets.size}`);

    return new Response(null, { status: 101, webSocket: client });
  }

  private handleMessage(ws: WebSocket, raw: string): void {
    const envelope = parseEnvelope(raw);

    if (!envelope) {
      this.sendError(ws, "Invalid envelope", "parse_error");
      return;
    }

    const senderToken = this.wsTokens.get(ws);

    if (!senderToken && envelope.t !== "hello") {
      this.sendError(ws, "Send hello first", "not_identified");
      return;
    }

    switch (envelope.t) {
      case "hello":    this.handleHello(ws, envelope.data.token, envelope.data.nickname); break;
      case "team_join": this.handleTeamJoin(ws, senderToken!, envelope.data.teamId); break;
      case "team_rename": this.handleTeamRename(ws, senderToken!, envelope.data.teamId, envelope.data.name); break;
      case "settings": this.handleSettings(ws, senderToken!, envelope.data); break;
      case "start":    this.handleStart(ws, senderToken!, envelope.data.seed); break;
      case "claim":    this.handleClaim(ws, senderToken!, envelope.data.squareIndex, envelope.data.timeMs); break;
      case "unclaim":  this.handleUnclaim(ws, senderToken!, envelope.data.squareIndex); break;
      case "restart":  this.handleRestart(ws, senderToken!, envelope.data.mode); break;
      case "chat":     this.handleChat(senderToken!, envelope.data.body); break;
    }
  }

  async alarm(): Promise<void> {
    // Countdown alarm: transition starting → playing, then chain the time-limit alarm if needed.
    if (this.room.phase === "starting") {
      this.room.phase = "playing";
      this.room.startedAt = Date.now();
      this.room.startingAt = null;
      if (this.room.settings.winConditions.includes("time_limit")) {
        this.ctx.storage.setAlarm(this.room.startedAt + this.room.settings.timeLimitMin * 60 * 1000);
      }
      console.log(`[${new Date().toISOString()}] [worker] Countdown done — phase=playing`);
      this.broadcastState();
      return;
    }

    if (this.room.phase !== "playing") return;
    if (!this.room.settings.winConditions.includes("time_limit")) return;

    console.log(`[${new Date().toISOString()}] [worker] Alarm fired — evaluating time_limit win`);
    const result = evalTimeLimit(this.room.claims);
    if (result) {
      this.room.winner = { teamId: result.teamId, condition: "time_limit", shape: result.shape };
      this.room.phase = "ended";
      this.broadcastState();
      this.broadcastEnd(result.teamId, "time_limit", result.shape);
    } else {
      // No claims at all — no winner; leave ended anyway
      this.room.phase = "ended";
      this.pushChat("Time limit reached — no winner", { system: true });
      this.broadcastState();
    }
  }

  // Shared startup: install a board, reset per-game state, enter the "starting"
  // countdown phase, and schedule the countdown alarm. Used by handleStart and
  // handleRestart (same/new modes).
  private beginStartingPhase(board: { seed: number; squares: string[] }): void {
    const total = this.room.settings.boardSize ** 2;
    this.room.board = board;
    this.room.claims = Array(total).fill(null) as (ClaimInfo[] | null)[];
    if (this.room.settings.centerFree) {
      const centerIdx = Math.floor(total / 2);
      this.room.claims[centerIdx] = [{ teamId: -1, timeMs: null, player: "FREE", ts: Date.now() }];
    }
    this.room.winner = null;
    this.room.phase = "starting";
    this.room.startingAt = Date.now();
    this.room.startedAt = null;
    this.ctx.storage.deleteAlarm();
    this.ctx.storage.setAlarm(this.room.startingAt + COUNTDOWN_MS);
    this.broadcastState();
  }

  // ─── Handlers ─────────────────────────────────────────────────────────────

  private handleHello(ws: WebSocket, token: string, nickname: string): void {
    this.wsTokens.set(ws, token);

    const existing = this.room.members[token];
    const isFirstJoin = !existing;
    if (existing) {
      existing.online = true;
      existing.nickname = nickname;
    } else {
      const member: MemberInfo = { nickname, teamId: null, online: true, joinedAt: Date.now() };
      this.room.members[token] = member;
    }

    // (Chat replay + first-join announce happen after broadcastState — see end of method.)

    if (this.room.hostToken === null) {
      this.room.hostToken = token;
    }

    // Reconnect repair: if this member was previously on a team that lost its
    // leader to disconnect (sole-member case), reclaim leadership on rejoin.
    const reconnectingMember = this.room.members[token];
    if (reconnectingMember?.teamId !== null && reconnectingMember?.teamId !== undefined) {
      const team = this.room.teams[reconnectingMember.teamId];
      if (team && team.leaderToken === null && team.memberTokens.includes(token)) {
        team.leaderToken = token;
      }
    }

    console.log(`[${new Date().toISOString()}] [worker] hello from ${nickname} (${token.slice(0, 8)})`);
    this.broadcastState();
    // Order matters: state first (so client can resolve team colors), then chat replay
    // (to the new socket only), then synthetic "joined" announce (broadcast to all).
    this.replayChatTo(ws);
    if (isFirstJoin) {
      const joinLabel = this.room.phase === "lobby" ? "joined" : "joined as spectator";
      this.pushChat(joinLabel, { system: true, nickname });
    }
  }

  private handleTeamJoin(ws: WebSocket, token: string, teamId: number | null): void {
    const member = this.room.members[token];
    if (!member) return;

    const oldTeamId = member.teamId;

    // Mid-game rule: spectators can join a team and team members can drop to
    // spectator, but team-to-team swaps are blocked outside the lobby phase —
    // otherwise a losing team could dissolve into the leading team in the
    // final minute.
    if (this.room.phase !== "lobby") {
      const isTeamToTeamSwap = oldTeamId !== null && teamId !== null && oldTeamId !== teamId;
      if (isTeamToTeamSwap) {
        this.sendError(ws, "Cannot switch teams after the game has started", "wrong_phase");
        return;
      }
    }

    // Remove from old team
    if (oldTeamId !== null) {
      const oldTeam = this.room.teams[oldTeamId];
      oldTeam.memberTokens = oldTeam.memberTokens.filter((t) => t !== token);
      if (oldTeam.leaderToken === token) {
        oldTeam.leaderToken = this.pickNewLeader(oldTeam.memberTokens);
      }
    }

    member.teamId = teamId;

    if (teamId !== null) {
      const team = this.room.teams[teamId];
      if (!team.memberTokens.includes(token)) {
        team.memberTokens.push(token);
      }
      if (team.leaderToken === null) {
        team.leaderToken = token;
      }
      this.pushChat(`joined ${team.name}`, { system: true, teamId, nickname: member.nickname });
    } else if (oldTeamId !== null) {
      this.pushChat(`left ${this.room.teams[oldTeamId].name}`, { system: true, teamId: oldTeamId, nickname: member.nickname });
    }

    this.broadcastState();
  }

  private handleTeamRename(ws: WebSocket, token: string, teamId: number, name: string): void {
    if (this.room.phase !== "lobby") {
      this.sendError(ws, "Cannot rename teams after game started", "wrong_phase");
      return;
    }
    const team = this.room.teams[teamId];
    if (!team) {
      this.sendError(ws, "Unknown team", "bad_team");
      return;
    }
    if (!team.memberTokens.includes(token)) {
      this.sendError(ws, "You must be on the team to rename it", "not_member");
      return;
    }
    const oldName = team.name;
    team.name = name.trim().slice(0, 24);
    this.pushChat(`${oldName} → ${team.name}`, { system: true, teamId });
    this.broadcastState();
  }

  private handleSettings(ws: WebSocket, token: string, data: unknown): void {
    if (token !== this.room.hostToken) {
      this.sendError(ws, "Only the host can change settings", "not_host");
      return;
    }
    if (this.room.phase !== "lobby") {
      this.sendError(ws, "Cannot change settings after game started", "wrong_phase");
      return;
    }

    // data already validated by parseEnvelope / isSettingsMsg
    const s = data as import("./protocol").Settings;
    this.room.settings = s;
    this.broadcastState();
  }

  private handleStart(ws: WebSocket, token: string, seedInput: number | undefined): void {
    if (token !== this.room.hostToken) {
      this.sendError(ws, "Only the host can start the game", "not_host");
      return;
    }
    if (this.room.phase !== "lobby") {
      this.sendError(ws, "Game already started", "wrong_phase");
      return;
    }

    const seed = seedInput ?? Math.floor(Math.random() * 2 ** 32);
    const result = generateBoard(this.room.settings, seed);

    if ("error" in result) {
      this.sendError(ws, result.error, "board_gen_error");
      return;
    }

    console.log(`[${new Date().toISOString()}] [worker] Game start requested — seed=${seed} boardSize=${this.room.settings.boardSize}`);
    this.pushChat(`Game starting (${this.room.settings.boardSize}x${this.room.settings.boardSize}, win: ${this.room.settings.winConditions.join(", ")})`, { system: true });
    this.beginStartingPhase({ seed, squares: result.squares });
  }

  private handleRestart(ws: WebSocket, token: string, mode: "same" | "new" | "lobby"): void {
    if (token !== this.room.hostToken) {
      this.sendError(ws, "Only the host can restart the game", "not_host");
      return;
    }
    // "lobby" mode is allowed from any non-lobby phase — it's the host's
    // escape hatch for a stuck game (no winner reachable, bad board, etc.).
    // "same"/"new" still require an ended game.
    if (mode === "lobby") {
      if (this.room.phase === "lobby") {
        this.sendError(ws, "Already in lobby", "wrong_phase");
        return;
      }
      const wasPlaying = this.room.phase === "playing" || this.room.phase === "starting";
      this.room.phase = "lobby";
      this.room.board = null;
      this.room.claims = [];
      this.room.winner = null;
      this.room.startingAt = null;
      this.room.startedAt = null;
      this.ctx.storage.deleteAlarm();
      console.log(`[${new Date().toISOString()}] [worker] Restart → lobby (from ${wasPlaying ? "playing" : "ended"})`);
      this.pushChat(wasPlaying ? "Host ended the game and returned to lobby" : "Back to lobby", { system: true });
      this.broadcastState();
      return;
    }

    if (this.room.phase !== "ended") {
      this.sendError(ws, "Can only restart from the end screen", "wrong_phase");
      return;
    }

    // "same" or "new" — both run a fresh countdown.
    let board = this.room.board;
    if (mode === "new" || !board) {
      const seed = Math.floor(Math.random() * 2 ** 32);
      const result = generateBoard(this.room.settings, seed);
      if ("error" in result) {
        this.sendError(ws, result.error, "board_gen_error");
        return;
      }
      board = { seed, squares: result.squares };
    }
    console.log(`[${new Date().toISOString()}] [worker] Restart → ${mode} (seed=${board.seed})`);
    this.pushChat(mode === "same" ? "Replaying same board" : "New board", { system: true });
    this.beginStartingPhase(board);
  }

  private handleClaim(ws: WebSocket, token: string, squareIndex: number, timeMs: number | null): void {
    if (this.room.phase !== "playing") {
      this.sendError(ws, "Game is not in progress", "wrong_phase");
      return;
    }

    const member = this.room.members[token];
    if (!member || member.teamId === null) {
      this.sendError(ws, "You are not on a team", "no_team");
      return;
    }

    const team = this.room.teams[member.teamId];
    if (!this.room.settings.anyoneCanClaim && team.leaderToken !== token) {
      this.sendError(ws, "Only the team leader can claim squares", "not_leader");
      return;
    }

    const total = this.room.settings.boardSize ** 2;
    if (squareIndex < 0 || squareIndex >= total) {
      this.sendError(ws, "Square index out of range", "bad_index");
      return;
    }

    const existing = this.room.claims[squareIndex];
    const newClaim: ClaimInfo = { teamId: member.teamId, timeMs, player: member.nickname, ts: Date.now() };

    if (existing === null) {
      // Empty — always accept (single-element array).
      this.room.claims[squareIndex] = [newClaim];
    } else {
      // Never override FREE sentinel.
      if (existing.some((c) => c.teamId === -1)) return;
      // Already claimed by my team — no-op (unclaim is a separate envelope).
      if (existing.some((c) => c.teamId === member.teamId)) return;
      // Lockout ON — first team owns the cell; nothing else can claim.
      if (this.room.settings.lockout) return;
      // Multi-claim allowed — add alongside existing claims.
      existing.push(newClaim);
    }

    const square = this.room.board?.squares[squareIndex] ?? "?";
    const coordStr = coord(squareIndex, this.room.settings.boardSize);
    this.pushChat(`claimed ${coordStr} — ${square}`, { system: true, teamId: member.teamId, nickname: member.nickname });

    const win = evaluateWin(this.room);
    if (win) {
      this.room.winner = win;
      this.room.phase = "ended";
      this.broadcastState();
      this.broadcastEnd(win.teamId, win.condition, win.shape);
    } else {
      this.broadcastState();
    }
  }

  private handleUnclaim(ws: WebSocket, token: string, squareIndex: number): void {
    if (this.room.phase !== "playing") {
      this.sendError(ws, "Game is not in progress", "wrong_phase");
      return;
    }
    const member = this.room.members[token];
    if (!member || member.teamId === null) {
      this.sendError(ws, "You are not on a team", "no_team");
      return;
    }
    const team = this.room.teams[member.teamId];
    if (!this.room.settings.anyoneCanClaim && team.leaderToken !== token) {
      this.sendError(ws, "Only the team leader can unclaim squares", "not_leader");
      return;
    }
    const total = this.room.settings.boardSize ** 2;
    if (squareIndex < 0 || squareIndex >= total) {
      this.sendError(ws, "Square index out of range", "bad_index");
      return;
    }
    const existing = this.room.claims[squareIndex];
    if (existing === null) return;
    if (existing.some((c) => c.teamId === -1)) return;       // FREE sentinel — never clear
    const filtered = existing.filter((c) => c.teamId !== member.teamId);
    if (filtered.length === existing.length) return;         // my team wasn't on this cell
    this.room.claims[squareIndex] = filtered.length === 0 ? null : filtered;
    const square = this.room.board?.squares[squareIndex] ?? "?";
    const coordStr = coord(squareIndex, this.room.settings.boardSize);
    this.pushChat(`unclaimed ${coordStr} — ${square}`, { system: true, teamId: member.teamId, nickname: member.nickname });
    this.broadcastState();
  }

  private handleChat(token: string, body: string): void {
    const member = this.room.members[token];
    const nickname = member?.nickname ?? token.slice(0, 8);
    const teamId = member?.teamId ?? null;
    this.pushChat(body, { teamId, nickname, system: false, fromToken: token });
  }

  // Append to chat history (capped), broadcast a chat envelope to all sockets.
  // System messages set system:true and use teamId for color tinting (or null for neutral).
  private pushChat(body: string, opts: { teamId?: number | null; nickname?: string | null; system?: boolean; fromToken?: string } = {}): void {
    const envelope: Chat = {
      t: "chat",
      ts: Date.now(),
      from: opts.fromToken,
      data: {
        body,
        teamId: opts.teamId ?? null,
        nickname: opts.nickname ?? null,
        system: opts.system ?? false,
      },
    };
    this.chatHistory.push(envelope);
    if (this.chatHistory.length > CHAT_HISTORY_CAP) {
      this.chatHistory.splice(0, this.chatHistory.length - CHAT_HISTORY_CAP);
    }
    const raw = JSON.stringify(envelope);
    for (const ws of this.sockets) {
      ws.send(raw);
    }
  }

  private replayChatTo(ws: WebSocket): void {
    for (const envelope of this.chatHistory) {
      ws.send(JSON.stringify(envelope));
    }
  }

  private handleDisconnect(ws: WebSocket): void {
    const token = this.wsTokens.get(ws);
    this.wsTokens.delete(ws);
    if (!token) return;

    const member = this.room.members[token];
    if (!member) return;

    member.online = false;

    // Transfer host if needed
    if (this.room.hostToken === token) {
      this.room.hostToken = this.findNextOnline(token);
    }

    // Transfer team leadership if needed
    if (member.teamId !== null) {
      const team = this.room.teams[member.teamId];
      if (team.leaderToken === token) {
        const onlineMembers = team.memberTokens.filter(
          (t) => t !== token && this.room.members[t]?.online,
        );
        team.leaderToken = onlineMembers[0] ?? null;
      }
    }

    this.broadcastState();
  }

  // ─── Helpers ──────────────────────────────────────────────────────────────

  private pickNewLeader(memberTokens: string[]): string | null {
    for (const t of memberTokens) {
      if (this.room.members[t]?.online) return t;
    }
    return memberTokens[0] ?? null;
  }

  private findNextOnline(excludeToken: string): string | null {
    // Prefer earliest-joined online member
    const sorted = Object.entries(this.room.members)
      .filter(([t, m]) => t !== excludeToken && m.online)
      .sort(([, a], [, b]) => a.joinedAt - b.joinedAt);
    return sorted[0]?.[0] ?? null;
  }

  private broadcastState(): void {
    const envelope: State = { t: "state", ts: Date.now(), data: this.room };
    const raw = JSON.stringify(envelope);
    for (const ws of this.sockets) {
      ws.send(raw);
    }
  }

  private broadcastEnd(teamId: number, condition: import("./protocol").WinConditionKey, shape?: number[]): void {
    const envelope: EndMsg = { t: "end", ts: Date.now(), data: { teamId, condition, shape } };
    const raw = JSON.stringify(envelope);
    for (const ws of this.sockets) {
      ws.send(raw);
    }
    const teamName = this.room.teams[teamId]?.name ?? `Team ${teamId + 1}`;
    const shapeStr = shape ? ` (${shape.map((i) => coord(i, this.room.settings.boardSize)).join(", ")})` : "";
    this.pushChat(`${teamName} won by ${condition}${shapeStr}`, { system: true, teamId });
  }

  private sendError(ws: WebSocket, message: string, reason?: string): void {
    const envelope: ErrorMsg = { t: "error", ts: Date.now(), data: { message, reason } };
    ws.send(JSON.stringify(envelope));
  }
}
