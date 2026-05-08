# Customizable Accent Color (Settings)

## Context

A user gave feedback that the default green accent (`#00e09a`) clashes with their taste. We want a Settings-page control that lets the user swap the accent for one of a curated set of presets. Persisted in `neonwhite_config.json` so it survives restarts. **UI chrome only** — medal colors, chart series, and other data colors stay untouched. This is a small, low-risk change because the codebase already routes every accent through a single CSS variable.

## Why this is easy

The whole design system reads from a single CSS custom property, `--accent`, defined in `frontend/src/styles.css:12-13`. Changing that one value retints buttons, segmented controls, toggles, borders, tags, and badges everywhere it's used (~50 references). Medal colors are a separate hard-coded `MEDAL_COLORS` map in `frontend/src/shared.jsx` and are not affected. There is no theming refactor required.

## Approach

### 1. Config schema — add `accent_color`
- **File:** `SteamScraper/webview_app/bridge.py` (around `_load_config` lines 83-103)
- Default to `"#00e09a"` when key is missing — preserves current behavior for existing users.
- No new bridge methods needed; `get_config` / `save_config_field` already handle arbitrary keys.

### 2. Curated preset swatches (8 colors)
A small palette chosen for legibility on the dark background. Final list to confirm during implementation, but starting set:
- Mint (default) `#00e09a`
- Cyan `#22d3ee`
- Sky blue `#38bdf8`
- Violet `#a78bfa`
- Magenta `#f472b6`
- Orange `#fb923c`
- Amber `#fbbf24`
- Rose `#fb7185`

### 3. Apply accent at app load + on change
- **File:** `frontend/src/main.jsx` (or wherever `<App>` mounts / config first loads)
- On startup, after `getConfig()` resolves, call `document.documentElement.style.setProperty('--accent', cfg.accent_color || '#00e09a')` — or set it on the `.hifi` root if that's where the variable lives.
- Expose a tiny helper `applyAccent(hex)` so the Settings page can update live without a reload.

### 4. Settings page UI
- **File:** `frontend/src/pages/Settings.jsx`
- Add a new `Field` row labeled **"Color Picker (Restrain setting)"** containing a horizontal row of 8 swatch buttons.
- Swatch = a small rounded square (~28px) filled with the preset hex; the currently-selected swatch gets a ring/outline using `--accent` to mirror the existing `Seg`/toggle "on" styling pattern from `frontend/src/shared.jsx`.
- Click handler: `applyAccent(hex)` immediately, then `saveConfigField('accent_color', hex)`.
- Help text in the right panel: "Changes the accent color used across buttons, toggles, and highlights. Medal colors are unchanged."

### 5. Out of scope (explicitly not touched)
- `MEDAL_COLORS` in `frontend/src/shared.jsx` (gold/silver/bronze/etc.)
- Any chart/comparison series colors
- Background, text, panel chrome — only the accent variable changes

## Critical files

| File | Change |
|---|---|
| `SteamScraper/webview_app/bridge.py` | Add `accent_color` default in `_load_config` |
| `frontend/src/main.jsx` (entry) | Apply saved accent to `--accent` on boot |
| `frontend/src/pages/Settings.jsx` | New "Color Picker (Restrain setting)" Field with swatch row |
| `frontend/src/styles.css` | (No structural change — `--accent` already exists at line 12-13) |
| `frontend/src/shared.jsx` | Optional: add a small `Swatch` primitive if reuse seems valuable |

## Verification

1. `cd frontend && npm run build` — confirm the React bundle compiles.
2. Launch the webview app (`python SteamScraper/webview_app/main.py` or the existing run command).
3. Open Settings → click each swatch → confirm buttons, toggles, and segmented controls retint immediately across all pages (Player Lookup, Compare Players, Ghosts, etc.).
4. Confirm medal badges in Player Lookup remain gold/silver/etc. (unchanged).
5. Close and relaunch the app → confirm the chosen accent persists.
6. Inspect `neonwhite_config.json` → confirm `"accent_color": "#xxxxxx"` is written.
7. Delete `accent_color` from the config file, relaunch → confirm it falls back to `#00e09a` without error.

## Estimated effort

~30-60 minutes. One config key, one CSS-variable assignment on boot, one new row in Settings. No backend logic, no migrations, no risk to data.
