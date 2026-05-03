# Questions for Claude

<!-- Things you want explained or clarified next session. Examples:
- How does the seed search worker communicate progress back to the UI?
- Why does the splits updater need the seed *and* the existing splits file?
-->

- "Standard Medals" — `_build_rush_std`/`_run_std` exist in `neonwhite_app.py` (lines 1547/1598) but the user reports no such tab in the UI. Is the code dead/unwired, half-built, or wired up under a different visible name? If dead, remove it; if half-built, decide whether to finish or delete. Either way, fix `01_Codebase_Map/overview.md` (currently lists it as one of 5 Rush sub-tabs).
