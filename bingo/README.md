# Bingo Mode — Stage 1 (WebSocket relay smoke test)

No protocol, no board, no real UI. Two browser tabs, same room code, messages echo to each other. Stage 2 adds envelopes and the board.

---

## 1. Prerequisites

- Node 20+
- Cloudflare account (free tier is fine for Stage 1)
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
- `GET /ws/:roomCode` → WebSocket upgrade, forwarded to LobbyDO

**Terminal 2 — Frontend**

```sh
cd bingo/web
npm install
npm run dev
```

Vite serves the HTML page, by default at `http://localhost:5173`.

---

## 3. Smoke test

1. Open `http://localhost:5173` in **two separate browser tabs** (or two different browsers).
2. In each tab, enter any nickname (different ones help) and the **same** room code (e.g. `ROOM1`).
3. Click **Connect** in both tabs.
4. Type a message in Tab A and click **Send**. Confirm Tab B's log shows it.
5. Reply from Tab B. Confirm Tab A sees it.
6. That's it — the relay works.

The sender's own message is echoed locally in the log immediately; the other tab receives it via the Worker's Durable Object broadcast.

---

## 4. Deploy (placeholder)

Stage 1 is dev-only. Stage 3 adds proper deploy steps (Worker to `workers.dev`, frontend to Cloudflare Pages).

For reference, the commands will be:

```sh
cd bingo/worker && wrangler deploy
cd bingo/web && npm run build && wrangler pages deploy ./dist
```

Do not run these yet — the worker name and routes need finalizing in Stage 3.

---

## 5. Environment variable for prod WS URL

The frontend reads `VITE_WS_URL` at build time. For local dev the default `ws://localhost:8787` is used automatically. For a deployed build, create `bingo/web/.env.production`:

```
VITE_WS_URL=wss://bingo-worker.<your-subdomain>.workers.dev
```

---

## Stage notes

This is **Stage 1 of Phase 1**. The full plan is at `plans/bingo-mode-phase1-beta.md`.

- **Stage 2** — typed envelopes (`protocol.ts`), board generation (`board.ts`), leader-token claim logic.
- **Stage 3** — React UI, settings form, team picker, board grid, claim dialog, end screen, deploy automation.
