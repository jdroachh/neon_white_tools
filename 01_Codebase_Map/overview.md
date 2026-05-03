# Project Overview

**Neon White Leaderboard Tool** — a Windows desktop app (v1.10.5) for scraping, exploring, and analyzing leaderboards for the game [Neon White](https://store.steampowered.com/app/1533420/Neon_White/) via Steam's Steamworks API.

## What it does

- **Global Leaderboard Export** — download the top N entries for every level and save to CSV
- **Level Search** — look up the leaderboard for any individual level
- **Player Lookup** — find a specific player's times across all levels, chapters, or a custom subset
- **Google Sheets Push** — write player data to a Google Sheet (OAuth authenticated)
- **Rush Tools** — a suite of 5 speedrun-focused utilities:
  - *Seed Finder* — searches 2.1B+ seeds to find randomizer runs where your target levels appear early
  - *Seed Parser* — decode any seed number into its resulting level play order
  - *Splits Updater* — reorder your existing split times to match a given seed
  - *Standard Medals* — display bronze/silver/gold/ace/dev medal targets per level
  - *Timer* — in-development speedrun timer (incomplete)

## How to run

```
python SteamScraper/neonwhite_app.py
```

Or launch the compiled `NeonWhiteLeaderboardTool.exe` (built with PyInstaller from `SteamScraper/neonwhite.spec`).

Requires `steam_api64.dll` (from the Neon White game install) at the path set in `neonwhite_config.json`.

## Who it's for

Neon White speedrunners and competitive players who want to analyze leaderboard standings, plan randomizer runs, or push data to community spreadsheets.
