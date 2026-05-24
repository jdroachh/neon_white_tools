import { DurableObject } from "cloudflare:workers";
import {
  parseEnvelope,
  makeInitialState,
  type RoomState,
  type MemberInfo,
  type ClaimInfo,
  type Envelope,
  type EndMsg,
  type ErrorMsg,
  type State,
} from "./protocol";
import { generateBoard, evaluateWin, evalTimeLimit } from "./board";

export class LobbyDO extends DurableObject {
  private room: RoomState = makeInitialState();
  // Standard (non-hibernating) accept: DO instance stays alive while any socket
  // is connected, so in-memory state (room, wsTokens) persists naturally.
  // Plan explicitly accepts the trade-off: "DO state is in-memory only during
  // a room's lifetime; once the last player disconnects, the room dies."
  private sockets = new Set<WebSocket>();
  private wsTokens = new Map<WebSocket, string>();

  async fetch(request: Request): Promise<Response> {
    const upgradeHeader = request.headers.get("Upgrade");
    if (!upgradeHeader || upgradeHeader.toLowerCase() !== "websocket") {
      return new Response("Expected WebSocket upgrade", { status: 426 });
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
      case "settings": this.handleSettings(ws, senderToken!, envelope.data); break;
      case "start":    this.handleStart(ws, senderToken!, envelope.data.seed); break;
      case "claim":    this.handleClaim(ws, senderToken!, envelope.data.squareIndex, envelope.data.timeMs); break;
      case "unclaim":  this.handleUnclaim(ws, senderToken!, envelope.data.squareIndex); break;
      case "chat":     this.handleChat(senderToken!, envelope.data.body); break;
    }
  }

  async alarm(): Promise<void> {
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
      this.broadcastState();
    }
  }

  // ─── Handlers ─────────────────────────────────────────────────────────────

  private handleHello(ws: WebSocket, token: string, nickname: string): void {
    this.wsTokens.set(ws, token);

    const existing = this.room.members[token];
    if (existing) {
      existing.online = true;
      existing.nickname = nickname;
    } else {
      const member: MemberInfo = { nickname, teamId: null, online: true, joinedAt: Date.now() };
      this.room.members[token] = member;
    }

    if (this.room.hostToken === null) {
      this.room.hostToken = token;
    }

    console.log(`[${new Date().toISOString()}] [worker] hello from ${nickname} (${token.slice(0, 8)})`);
    this.broadcastState();
  }

  private handleTeamJoin(ws: WebSocket, token: string, teamId: number | null): void {
    if (this.room.phase !== "lobby") {
      this.sendError(ws, "Cannot change teams after game started", "wrong_phase");
      return;
    }

    const member = this.room.members[token];
    if (!member) return;

    const oldTeamId = member.teamId;

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
    }

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

    const total = this.room.settings.boardSize ** 2;
    this.room.board = { seed, squares: result.squares };
    this.room.claims = Array(total).fill(null) as (ClaimInfo | null)[];

    if (this.room.settings.centerFree) {
      const centerIdx = Math.floor(total / 2);
      const now = Date.now();
      this.room.claims[centerIdx] = { teamId: -1, timeMs: null, player: "FREE", ts: now };
    }

    this.room.phase = "playing";
    this.room.startedAt = Date.now();

    if (this.room.settings.winConditions.includes("time_limit")) {
      this.ctx.storage.setAlarm(this.room.startedAt + this.room.settings.timeLimitSec * 1000);
    }

    console.log(`[${new Date().toISOString()}] [worker] Game started — seed=${seed} boardSize=${this.room.settings.boardSize}`);
    this.broadcastState();
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
    if (team.leaderToken !== token) {
      this.sendError(ws, "Only the team leader can claim squares", "not_leader");
      return;
    }

    const total = this.room.settings.boardSize ** 2;
    if (squareIndex < 0 || squareIndex >= total) {
      this.sendError(ws, "Square index out of range", "bad_index");
      return;
    }

    const existing = this.room.claims[squareIndex];

    // Center-free sentinel — never overwrite
    if (existing !== null && existing.teamId === -1) {
      return;
    }

    let accepted = false;
    const newClaim: ClaimInfo = { teamId: member.teamId, timeMs, player: member.nickname, ts: Date.now() };

    if (existing === null) {
      // Empty square — accept
      this.room.claims[squareIndex] = newClaim;
      accepted = true;
    } else if (existing.teamId === member.teamId) {
      // Same team — accept if new time beats old (non-null beats null; lower non-null beats higher)
      if (existing.timeMs === null && timeMs !== null) {
        // old had no time, new has a time — non-null beats null
        this.room.claims[squareIndex] = newClaim;
        accepted = true;
      } else if (timeMs !== null && existing.timeMs !== null && timeMs < existing.timeMs) {
        this.room.claims[squareIndex] = newClaim;
        accepted = true;
      }
    } else {
      // Different team — accept if new time is non-null AND beats old (or old was null)
      if (timeMs !== null && (existing.timeMs === null || timeMs < existing.timeMs)) {
        this.room.claims[squareIndex] = newClaim;
        accepted = true;
      }
    }

    if (!accepted) return;

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
    if (team.leaderToken !== token) {
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
    if (existing.teamId === -1) return;                  // FREE sentinel — never clear
    if (existing.teamId !== member.teamId) return;       // can't unclaim other teams

    this.room.claims[squareIndex] = null;
    this.broadcastState();
  }

  private handleChat(token: string, body: string): void {
    const member = this.room.members[token];
    const nickname = member?.nickname ?? token.slice(0, 8);
    const envelope: Envelope = {
      t: "chat",
      ts: Date.now(),
      from: token,
      data: { body: `<${nickname}> ${body}` },
    };
    const raw = JSON.stringify(envelope);
    for (const ws of this.sockets) {
      ws.send(raw);
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
  }

  private sendError(ws: WebSocket, message: string, reason?: string): void {
    const envelope: ErrorMsg = { t: "error", ts: Date.now(), data: { message, reason } };
    ws.send(JSON.stringify(envelope));
  }
}
