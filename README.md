# Neon White Tools

A speedrun analysis app for [Neon White](https://store.steampowered.com/app/1533420/Neon_White/) that pulls live leaderboard data via the Steamworks SDK and surfaces it in a fast local UI.

**[Download the latest release →](https://github.com/jdroachh/neon_white_tools/releases/latest)**



---

## Features

- **Global Export** — download full leaderboard snapshots for any level or all 96 levels at once
- **Level Search** — look up top entries on any level; filter by rank range or player name
- **Player Lookup** — pull all ranked entries for one or more Steam profiles across every level
- **Rush Tools** — Seed Finder (find seeds that contain a given level order), Seed Parser, Run Timer with split analysis
- **Community Guides** — browse community-curated guide videos; mark watchlist / watched
- **Ghosts Library** — browse ghost replay files (Drive-sourced) filtered by level

See [docs/USAGE.md](docs/USAGE.md) for a per-page walkthrough.

---

## Requirements

- Windows 10 or later (x64)
- Own [Neon White on Steam](https://store.steampowered.com/app/1533420/Neon_White/) (game must be installed — the app reads `steam_api64.dll` from your install)
- Steam must be running when you use the leaderboard features

The app locates `steam_api64.dll` automatically via the Steam registry → `libraryfolders.vdf` → recursive game-directory search. The Welcome page walks you through it on first launch.

---

## Installation

1. Download `NeonWhiteLeaderboardTool-<version>.zip` from the [Releases page](https://github.com/jdroachh/neon_white_tools/releases/latest)
2. Unzip anywhere (e.g. `C:\Games\NeonWhiteLeaderboardTool\`)
3. Run `NeonWhiteLeaderboardTool.exe`
4. On first launch the Welcome page will guide you through finding `steam_api64.dll`

No installer. No admin rights required. Settings are stored in `neonwhite_config.json` next to the EXE.

---

## Building from source

**Prerequisites:** Python 3.12+, Node 20+

```powershell
# 1. Install Python dependencies
pip install -r requirements.txt

# 2. Build the React frontend
cd frontend
npm install
npm run build
cd ..

# 3. Run in dev mode (no EXE needed)
python -m SteamScraper.webview_app.main

# 4. Build the EXE (one-dir, ~73 MB)
cd SteamScraper
pyinstaller neonwhite.spec
# Output: SteamScraper/dist/NeonWhiteLeaderboardTool/
```

`neonwhite.spec` is production-ready and correctly excludes `steam_api64.dll` (users supply their own DLL at runtime).

Copy `neonwhite_config.example.json` to `neonwhite_config.json` and fill in your `dll_path` to skip the Welcome-page setup flow on first launch.

### Config schema (`neonwhite_config.json`)

| Key | Type | Description |
|-----|------|-------------|
| `dll_path` | string | Absolute path to `steam_api64.dll` from your Neon White install |
| `output_folder` | string | Default folder for exported CSV files |
| `entry_count` | int | Max leaderboard entries to fetch per level (default 200) |
| `accent_color` | string | UI accent hex color (e.g. `"#00d4ff"`) |
| `saved_profiles` | array | Saved Steam profile URLs / IDs for quick lookup |
| `guide_watchlist` | array | YouTube video IDs marked as watchlist |
| `guide_watched` | array | YouTube video IDs marked as watched |
| `guide_hide_watched` | bool | Filter out watched guides |
| `guide_watchlist_only` | bool | Show only watchlisted guides |
| `welcome_seen` | bool | Skip Welcome page on next launch |
| `last_tab` | string | Re-open to this tab on launch |

---

## Credits

- **Steamworks SDK** — Valve Corporation (trademark; users must own Neon White on Steam)

---

## License

MIT — see [LICENSE](LICENSE)
