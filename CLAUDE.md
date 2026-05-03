# Claude Startup Ritual

**At the start of every session:**

1. Read everything in `00_Inbox/` — these are new notes from the user since last time
2. Skim `01_Codebase_Map/overview.md` to refresh on the project
3. Check the most recent file in `03_Sessions/` for last session's context
4. Before doing any work, summarize: what's new in the inbox, and what you plan to do about it
5. After significant work, append a short log to `03_Sessions/YYYY-MM-DD.md`

## Vault Map

- `00_Inbox/` — user-authored notes between sessions: `ideas.md`, `questions.md`, `todo.md`. Always read first.
- `01_Codebase_Map/` — Claude's understanding of the code: `overview.md`, `architecture.md` (with line anchors into `neonwhite_app.py`), `glossary.md`.
- `02_Decisions/` — ADRs ("why we did X"). One file per decision, dated.
- `03_Sessions/` — per-session logs (`YYYY-MM-DD.md`). Append after significant work.
- `SteamScraper/` — the actual codebase. Live entry point is `neonwhite_app.py`; treat anything under `Neon White App versions/` and the standalone scripts (`leaderboard.py`, `discover.py`, `testingBalloon.py`, `test_sheets_write.py`) as dead code unless told otherwise.

## Working Style

- **Be terse.** Lead with the answer or the change. No throat-clearing, no recap of what was just discussed.
- **Confirm before risky actions** — anything destructive, anything that touches `SteamScraper/` source, or any third-party API/network call. Local vault edits don't need confirmation.
- **Keep `01_Codebase_Map/` curated** — when the code changes meaningfully, update overview/architecture/glossary in the same session. Don't let it rot.
- **Update memory when patterns emerge** — if a piece of feedback applies beyond this conversation, save it.
- **Don't restructure `SteamScraper/`** without asking. The user knows the layout is messy; cleanup is a separate, deliberate task.
