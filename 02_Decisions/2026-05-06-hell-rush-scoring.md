# Hell Rush Mode — Healthpack Data and Scoring Formula

**Date:** 2026-05-06  
**Status:** Implemented in `webview_app/hell_rush.py`

## Healthpack Levels (11 total, unweighted)

Glass Port, Jumper, The Clocktower, Apartment, Fuse, Estate, Ricochet, Fortress, The Third Temple, Congregation, Absolution

Authoritative source: user (2026-05-06). Stored in `data/healthpacks.json`.

## Scoring Formula

Given a shuffled 96-level order:

1. Find 1-indexed positions of all 11 HP stages.
2. Compute gaps: opening gap (0 → first HP) + gaps between consecutive HPs. **No trailing gap** (last HP → 96).
3. `ideal_gap = last_hp_position / hp_count`
4. Population std dev of those gaps (lower = more evenly spaced).
5. `early_penalty`: each HP in positions 1–3 → `(4 - pos) × 5`
6. `consecutive_penalty`: each adjacent HP pair:
   - gap ≤ 3 → `(4 - gap) × 15`
   - gap ≤ 5 → `(6 - gap) × 5`
7. `spread_penalty`: if last HP before position 70 → `(70 - lastPos) × 2`
8. `score = clamp(round(100 - std_dev / ideal_gap × 100) - earlyPenalty - consecutivePenalty - spreadPenalty, 0, 100)`

## Verification

Seed 712788 → score 77 (matches the mockup's hardcoded sample in `hifi-pages.jsx:356`). ✓
