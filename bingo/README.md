# Bingo Mode — Phase 1 (local dev)

Stage 1 (WebSocket relay) + Stage 2 (real protocol, board generation, claims, win conditions).

---

## 1. Prerequisites

- Node 20+
- Cloudflare account (free tier is fine for the beta)
- Wrangler CLI: `npm i -g wrangler`
- Log in once: `wrangler login`

---

## 2. Local dev

Open two terminals.

**Terminal 1 — Worker**

```sh
cd bingo/worker
npm install
wrangler dev
```

Worker listens on `http://localhost:8787`. Routes:
- `GET /health` → `200 ok`
- `GET /ws/:roomCode` → WebSocket upgrade, forwarded to `LobbyDO`

**Terminal 2 — Frontend**

```sh
cd bingo/web
npm install
npm run dev
```

Vite serves the HTML page at `http://localhost:5173` by default.

---

## 3. Smoke test — Stage 2

1. Open `http://localhost:5173` in **two separate browser tabs**.
2. Tab A: enter `Alice` as nickname, `TEST` as room code, click Connect.
3. Tab B: enter `Bob` as nickname, `TEST` as room code, click Connect.
4. Both tabs will be in the **Lobby**. Alice (first to connect) is the host (👑).
5. Alice joins Team 1; Bob joins Team 2. Each becomes their team's leader (★).
6. Alice (host) sees the Settings panel. Adjust if desired, then click **Start Game**.
7. A 5×5 board appears in both tabs. Alice and Bob each click squares as team leaders.
8. Enter an optional time (in seconds) in the prompt that appears.
9. The first team to complete a line (or whichever win condition is set) triggers an end screen.
10. The end screen shows the winning team and highlights the winning shape.

**Tab refresh / reconnect:** closing and reopening a tab reconnects automatically using the `bingo_token` cookie. The member's team slot is preserved; leadership transfers immediately on disconnect and can be reclaimed via the team picker on reconnect.

---

## 4. Deploy (placeholder)

Stage 1–2 are dev-only. Stage 3 adds proper deploy steps.

For reference, the commands will be:

```sh
cd bingo/worker && wrangler deploy
cd bingo/web && npm run build && wrangler pages deploy ./dist
```

---

## 5. Environment variable for prod WS URL

The frontend reads `VITE_WS_URL` at build time. For local dev the default `ws://localhost:8787` is used automatically. For a deployed build, create `bingo/web/.env.production`:

```
VITE_WS_URL=wss://bingo-worker.<your-subdomain>.workers.dev
```

---

## Stage notes

This is **Stage 2 of Phase 1**. The full plan is at `plans/bingo-mode-phase1-beta.md`.

### What Stage 2 added

- **`protocol.ts`** (worker + web) — typed envelope union (`hello`, `team_join`, `settings`, `start`, `claim`, `chat`, `state`, `end`, `error`), `parseEnvelope()` type guard, `RoomState` schema.
- **`board.ts`** (worker) — `generateBoard()` ingests `squares.json`, builds a section-filtered honor-only pool, runs a Mulberry32 seeded shuffle, returns the square name list. All five win evaluators: `line`, `four_corners`, `full_house`, `first_to_n`, `time_limit`.
- **`lobby.ts`** — full state machine replacing Stage 1's broadcast-only relay. Handles hello / team_join / settings / start / claim / chat with proper leader-token gating, same-team time-improvement overwrites, and cross-team lower-time overwrites. DO alarm for `time_limit` win condition.
- **`main.ts`** — token-cookie identity, typed WS client, lobby/board/end-screen rendering, team picker, settings form (host-only), board grid with claim prompts.
- The original Stage 1 chat-only mode is gone — superseded by the full envelope flow.

### What Stage 3 will add

- React UI, design tokens, real CSS (no more inline styles).
- Settings form polish, claim dialog, chat panel.
- Deploy automation to Cloudflare Workers + Pages.
