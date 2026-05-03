# Glossary

Terms and acronyms you'll encounter in this codebase and the Neon White community.

---

**ACE medal** — The highest medal tier in Neon White, above Gold. Beating ACE time is required for top leaderboard positions. (See also: Dev medal)

**App ID** — Steam's numeric identifier for a game. Neon White's is `1533420` (stored in [`steam_appid.txt`](../SteamScraper/steam_appid.txt)).

**Callback / CallResult** — Steam's async mechanism. You initiate a request (e.g. find leaderboard) and Steam fires a callback with the result. The app polls for these via `SteamAPI_ManualDispatch_RunFrame`.

**Cheater list** — A community-maintained JSON list of SteamIDs known to have illegitimate scores. Fetched at startup from the NeonLite GitHub repo and used to flag/filter entries.

**Community medals** — Unofficial target times set by the Neon White speedrun community (faster than ACE). Also fetched from the NeonLite repo at startup.

**ctypes** — Python's built-in FFI library. The app uses it to call Steam's C++ Steamworks DLL directly, without a Python SDK wrapper.

**Dev medal** — Fastest official target time per level, set by the developers. Faster than ACE.

**DLL path** — The filesystem path to `steam_api64.dll`, configured in `neonwhite_config.json`. Required for the app to function.

**IL (Individual Level)** — Refers to running/timing a single level in isolation, as opposed to a full-game run.

**ISteamUserStats** — The Steam interface that exposes leaderboard APIs. The app fetches a pointer to it via `SteamClient021`.

**LeaderboardEntry** — A ctypes struct representing one row in a Steam leaderboard: SteamID, global rank, score (milliseconds), details count, UGC handle.

**LeaderboardFindResult** — Steam callback struct returned after `FindLeaderboard()`. Contains the leaderboard handle and a found flag.

**LeaderboardScoresDownloaded** — Steam callback struct returned after `DownloadLeaderboardEntries()`. Contains the entries handle and count.

**NeonLite** — A community mod for Neon White. The app uses its GitHub repo (`Faustas156/NeonLite`) as the source for cheater list and community medal data.

**Randomizer / Rush** — A Neon White game mode that shuffles the level order. The Rush Tools in this app are designed to help speedrunners find and analyze favorable randomizer seeds.

**Seed** — An integer that determines the level order in a randomizer run. The Seed Finder searches ~2.1 billion seeds to find ones where desired levels appear early.

**Seed Finder** — The most computationally intensive feature. Uses a compiled C extension (`shuffle.dll`) to search seeds at ~200,000+ seeds/sec in a separate process.

**shuffle.dll** — A C-compiled library built by [`compile_shuffle.py`](../SteamScraper/compile_shuffle.py). Contains the fast Fisher-Yates shuffle used by the Seed Finder.

**SteamClient021 / SteamClient020** — Versioned interfaces into the Steam client. The app tries `021` first, falls back to `020`.

**SteamID** — Steam's 64-bit unique identifier for a user account.

**Steamworks API / steam_api64.dll** — Steam's C++ SDK for games. The app loads this DLL from the game's install directory to access leaderboard data.

**Treeview** — tkinter's table/tree widget, used to display leaderboard results in the app's UI.

**UGC handle** — A Steam "User Generated Content" handle attached to each leaderboard entry. Not used meaningfully by this app (stored but not acted on).
