# Release Process

How to ship a new version of Neon White Tools.

## Prerequisites

- Python 3.12+, Node 20+, PyInstaller (`pip install -r requirements.txt`)
- `git` and `gh` CLI authenticated as `jdroachh`
- Neon White installed on Steam (for smoke testing)

---

## Steps

### 1. Finish and commit your changes

Make sure everything is committed and pushed to `main`.

### 2. Bump the version

Edit `SteamScraper/webview_app/bridge.py` line 29:

```python
APP_VERSION = "1.x.x"
```

Commit and push:

```powershell
git add SteamScraper/webview_app/bridge.py
git commit -m "Chore: bump version to 1.x.x"
git push origin main
```

### 3. Build the EXE

From the repo root (`E:\Claude-Neon-White-App`):

```powershell
cd frontend
npm run build
cd ..\SteamScraper
pyinstaller neonwhite.spec
# Output: SteamScraper\dist\NeonWhiteLeaderboardTool\
```

### 4. Smoke test

Launch `SteamScraper\dist\NeonWhiteLeaderboardTool\NeonWhiteLeaderboardTool.exe` and verify:

- [ ] App opens, version shown matches the new version
- [ ] Welcome page or correct last tab appears on launch
- [ ] Steam connects successfully
- [ ] Level Search returns results
- [ ] Seed Finder runs and returns at least one seed
- [ ] Community Guides list populates
- [ ] No tracebacks in `SteamScraper\dist\NeonWhiteLeaderboardTool\logs\app.log`

### 5. Zip the build

```powershell
Compress-Archive `
  -Path "E:\Claude-Neon-White-App\SteamScraper\dist\NeonWhiteLeaderboardTool" `
  -DestinationPath "E:\Claude-Neon-White-App\NeonWhiteLeaderboardTool-1.x.x.zip" `
  -Force
```

### 6. Tag and push

```powershell
git tag v1.x.x
git push origin v1.x.x
```

### 7. Create the GitHub Release

Go to [Releases](https://github.com/jdroachh/neon_white_tools/releases) → **Draft a new release**:

- **Tag:** select `v1.x.x`
- **Title:** `v1.x.x`
- **Description:** what changed, known issues if any, install instructions link
- **Asset:** attach `NeonWhiteLeaderboardTool-1.x.x.zip`
- **Pre-release:** check if it's a beta

---

## Versioning

Follows [semver](https://semver.org/):

- `MAJOR` — breaking changes or full rewrites
- `MINOR` — new features
- `PATCH` — bug fixes

Suffix `-beta.N` for pre-releases (e.g. `v1.1.0-beta.1`).

Version source of truth: `SteamScraper/webview_app/bridge.py` → `APP_VERSION`. Keep it in sync with the git tag.

---

## Future: automated releases via GitHub Actions

The manual steps above can be fully automated — on `git tag v*`, a workflow can build the EXE, zip it, and publish the release automatically. Revisit after a few successful manual releases.
