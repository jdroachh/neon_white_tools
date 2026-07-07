import React, { useState, useEffect, useMemo, useRef } from "react";
import { PageHead, Field, Seg, Btn, ErrorBanner } from "../shared.jsx";
import {
  runAvgRankings, stopAvgRankings, pickFolder, getCheaterCount,
  getLevels, getChapters, getSteamStatus,
} from "../api.js";
import LevelPickerModal from "../components/LevelPickerModal.jsx";
import SavedProfilesDropdown from "../components/SavedProfilesDropdown.jsx";
import { loadLastSelection, saveLastSelection } from "../lib/customLevels.js";
import { loadProfiles } from "../lib/savedProfiles.js";
import { loadRosters, saveRosters, addRoster, removeRoster } from "../lib/savedRosters.js";
import { loadWithRetry } from "../lib/retryLevels.js";

const TH = { padding: "4px 8px", fontWeight: 600, fontSize: "0.91em", borderBottom: "1px solid var(--border)", textAlign: "left" };
const TD = { padding: "3px 8px", fontSize: "1em" };

// Times are intentionally absent here — this board ranks by AVERAGE per-level
// placement (consistency), not by any time. In depth mode the seed set is the
// top-K of GlobalNeonRankings (so only complete-game players appear); in roster
// mode it's an explicit Steam-ID list. See plans/2026-06-25-avg-placement-custom-filter.md.

const STEAM_ID_RE = /^\d{17}$/;
const ROSTER_MAX = 100;  // roster size cap = Valve's DownloadLeaderboardEntriesForUsers
                         // batch size, so a full roster is exactly one Steam call per board
                         // (101+ would force a second batch per board × up to 121 boards)

// Short Seg labels keep the 4-option control compact; the full meaning lives in
// the SCOPE_DESC line rendered under the Seg.
const SCOPES = { "All": "story+side", "Main": "story", "Side": "side", "Custom": "custom" };
const SCOPE_DESC = {
  "All": "All stages (121).",
  "Main": "Main-game stages only — excludes Red/Violet/Yellow (97).",
  "Side": "Sidequest stages only — Red/Violet/Yellow (24).",
  "Custom": "Pick the exact stages to score below.",
};
const SCOPE_BOARDS = { "All": 121, "Main": 97, "Side": 24 };
const OUTPUT_DESC = {
  display: "Show results in the app only.",
  csv: "Write results to a CSV file (pick a folder below).",
  both: "Show in the app and write a CSV.",
};

// Mirror avg_rankings.sort_rows: primary metric, then canonical chain, then sid.
const SORT_KEY = { "Avg place": "avg_rank", "Percentile": "avg_pct", "Median": "median_rank" };
const CANONICAL = ["avg_rank", "avg_pct", "median_rank"];

function sortRows(rows, metricLabel) {
  const primary = SORT_KEY[metricLabel] || "avg_rank";
  const order = [primary, ...CANONICAL.filter(k => k !== primary)];
  const cmp = (a, b) => {
    for (const k of order) {
      const av = a[k], bv = b[k];
      const an = av == null, bn = bv == null;
      if (an !== bn) return an ? 1 : -1;        // nulls last
      if (an && bn) continue;
      if (av !== bv) return av - bv;            // ascending — lower is better
    }
    return String(a.steam_id).localeCompare(String(b.steam_id));
  };
  return [...rows].sort(cmp);
}

function fmtEta(s) {
  if (s == null) return "";
  const t = Math.max(0, Math.round(s));
  const m = Math.floor(t / 60), sec = t % 60;
  return m > 0 ? `~${m}m ${sec}s left` : `~${sec}s left`;
}

function fmtPct(v, decimals = 3) {
  return v == null ? "—" : `top ${(v * 100).toFixed(decimals)}%`;
}

// Bare percentile (no "top " prefix) — used for the Copy payload so it pastes as
// a plain value into a spreadsheet.
function fmtPctBare(v, decimals = 3) {
  return v == null ? "" : `${(v * 100).toFixed(decimals)}%`;
}

export default function AvgRankings({ outputFolder: defaultFolder = "", visible = false }) {
  const [source, setSource]       = useState("depth");   // depth | roster
  const [k, setK]                 = useState("500");   // user-set board depth
  const [scope, setScope]         = useState("All");
  const [outMode, setOutMode]     = useState("display");
  const [folder, setFolder]       = useState(defaultFolder);
  const [running, setRunning]     = useState(false);
  const [status, setStatus]       = useState("");
  const [error, setError]         = useState("");
  const [rows, setRows]           = useState([]);
  const [asOf, setAsOf]           = useState("");
  const [progress, setProgress]   = useState(null);   // {board_idx, total_boards, board_name, eta_seconds}
  const [sortBy, setSortBy]       = useState("Avg place");
  const [largeText, setLargeText] = useState(false);
  const [pctExtra, setPctExtra]   = useState(false);  // 3 vs 5 percentile decimals
  const [stoppedEmpty, setStoppedEmpty] = useState(false);  // stopped before anything qualified
  const [cheaterCount, setCheaterCount] = useState(0);
  const [nameFilter, setNameFilter]     = useState("");
  // Snapshot of the params the current rows were fetched with (for Refresh).
  const [lastParams, setLastParams]     = useState(null);
  const [emptyBoards, setEmptyBoards]   = useState([]);  // boards that returned no data

  // Custom stages (display names) + the catalog the picker needs.
  const [customLevels, setCustomLevels] = useState([]);
  const [pickerOpen, setPickerOpen]     = useState(false);
  const [levels, setLevels]             = useState([]);   // [{display, ...}]
  const [chapters, setChapters]         = useState([]);   // [{name, levels}]
  const customHydrated = useRef(false);

  // Roster source.
  const [roster, setRoster]               = useState([{ name: "", steam_id: "" }]);
  const [savedProfiles, setSavedProfiles] = useState([]);
  const [savedRosters, setSavedRosters]   = useState([]);

  const stageCount = scope === "Custom" ? customLevels.length : SCOPE_BOARDS[scope];

  // Sort the full board by the active metric, then stamp each row's position
  // (_pos) under that ordering. The name filter operates on this list, so _pos
  // stays the player's true board rank regardless of what's filtered out.
  const sortedRows = useMemo(
    () => sortRows(rows, sortBy).map((r, i) => ({ ...r, _pos: i + 1 })),
    [rows, sortBy]);
  const filteredRows = useMemo(() => {
    const q = nameFilter.trim().toLowerCase();
    if (!q) return sortedRows;
    return sortedRows.filter(r => r.name.toLowerCase().includes(q));
  }, [sortedRows, nameFilter]);

  // ── Roster validity ──────────────────────────────────────────────────────
  const idCounts = useMemo(() => {
    const counts = {};
    for (const r of roster) {
      const id = (r.steam_id || "").trim();
      if (id) counts[id] = (counts[id] || 0) + 1;
    }
    return counts;
  }, [roster]);
  const validRoster = useMemo(
    () => roster.filter(r => {
      const id = (r.steam_id || "").trim();
      return STEAM_ID_RE.test(id) && idCounts[id] === 1;
    }),
    [roster, idCounts]);
  const rosterIds = useMemo(
    () => new Set(roster.map(r => (r.steam_id || "").trim()).filter(Boolean)),
    [roster]);

  const [folderTouched, setFolderTouched] = useState(false);
  useEffect(() => { if (!folderTouched) setFolder(defaultFolder); }, [defaultFolder]);

  useEffect(() => { getCheaterCount().then(n => { if (n > 0) setCheaterCount(n); }); }, []);

  // Levels + chapters for the custom picker (first-boot bridge race → retry,
  // same as Player Lookup / Compare / Multi Compare). getChapters returns
  // [{name, levels}] which LevelPickerModal consumes directly.
  useEffect(() => {
    const cancelLevels = loadWithRetry(getLevels, { onData: setLevels });
    const cancelChapters = loadWithRetry(getChapters, { onData: setChapters });
    loadProfiles().then(setSavedProfiles).catch(() => {});
    loadRosters().then(setSavedRosters).catch(() => {});
    return () => { cancelLevels(); cancelChapters(); };
  }, []);

  // Reload saved profiles/rosters whenever the tab regains focus (they may have
  // been edited on Settings or another page).
  useEffect(() => {
    if (!visible) return;
    loadProfiles().then(setSavedProfiles).catch(() => {});
    loadRosters().then(setSavedRosters).catch(() => {});
  }, [visible]);

  // Hydrate the last-used custom selection the first time the user picks Custom.
  useEffect(() => {
    if (scope === "Custom" && !customHydrated.current) {
      customHydrated.current = true;
      loadLastSelection("avg").then(sel => { if (sel.length) setCustomLevels(sel); });
    }
  }, [scope]);

  useEffect(() => {
    // Self-rearming handler (a no-op failure path shouldn't strand the page).
    window._nwAvgRankEvent = (ev) => {
      if (ev.type === "status") {
        setStatus(ev.message);
      } else if (ev.type === "progress") {
        setProgress(ev);
        const part = ev.chunk_total > 1 ? ` · part ${ev.chunk_idx}/${ev.chunk_total}` : "";
        const eta = fmtEta(ev.eta_seconds);
        const slow = ev.slow ? " · taking longer than usual" : "";
        setStatus(`Fetching board ${ev.board_idx}/${ev.total_boards} · ${ev.board_name}${part}${eta ? " · " + eta : ""}${slow}`);
      } else if (ev.type === "done") {
        setRows(ev.rows || []);
        setAsOf(ev.as_of || "");
        setEmptyBoards(ev.empty_boards || []);
        setStoppedEmpty(!!ev.stopped && (!ev.rows || ev.rows.length === 0));
        setStatus(ev.csv_path ? `${ev.message} → ${ev.csv_path}` : ev.message);
        setRunning(false);
        setProgress(null);
        getCheaterCount().then(n => { if (n > 0) setCheaterCount(n); });
      } else if (ev.type === "error") {
        setError(ev.message);
        setRunning(false);
        setProgress(null);
      }
    };
    return () => { window._nwAvgRankEvent = null; };
  }, []);

  async function handlePickFolder() {
    const r = await pickFolder();
    if (r.ok && r.path) { setFolder(r.path); setFolderTouched(true); }
  }

  function handleCustomLevelsChange(next) {
    setCustomLevels(next);
    saveLastSelection("avg", next).catch(() => {});
  }

  // ── Roster mutations ───────────────────────────────────────────────────────
  function updateRow(idx, patch) {
    setRoster(prev => prev.map((r, i) => (i === idx ? { ...r, ...patch } : r)));
  }
  function addRow() {
    if (roster.length >= ROSTER_MAX) return;
    setRoster(prev => [...prev, { name: "", steam_id: "" }]);
  }
  function removeRow(idx) {
    setRoster(prev => (prev.length <= 1 ? prev : prev.filter((_, i) => i !== idx)));
  }
  function applyProfileToRow(idx, profile) {
    updateRow(idx, { name: profile.nickname || "", steam_id: profile.steam_id || "" });
  }
  async function handleUseMine(idx) {
    const s = await getSteamStatus();
    if (s.ready && s.steam_id) {
      const patch = { steam_id: String(s.steam_id) };
      if (s.player_name) patch.name = s.player_name;
      updateRow(idx, patch);
    } else {
      window.alert("Steam not connected. Connect in Settings first.");
    }
  }
  function handleSaveRoster() {
    if (validRoster.length === 0) return;
    const nickname = window.prompt(`Save this roster (${validRoster.length} players).\n\nName:`);
    if (nickname === null) return;
    const members = validRoster.map(r => ({ name: r.name || "", steam_id: r.steam_id.trim() }));
    const { error: err, list } = addRoster(savedRosters, { nickname, members });
    if (err) { setError(err); return; }
    setSavedRosters(list);
    saveRosters(list).catch(() => {});
  }
  function handleLoadSavedRoster(idx) {
    const sr = savedRosters[idx];
    if (!sr || !Array.isArray(sr.members) || sr.members.length === 0) return;
    setRoster(sr.members.slice(0, ROSTER_MAX).map(m => ({
      name: m.name || "", steam_id: m.steam_id || "",
    })));
  }
  function handleDeleteSavedRoster(idx) {
    const next = removeRoster(savedRosters, idx);
    setSavedRosters(next);
    saveRosters(next).catch(() => {});
  }

  async function start(params) {
    setError(""); setStatus("Starting…"); setRows([]); setAsOf(""); setProgress(null); setNameFilter(""); setEmptyBoards([]); setStoppedEmpty(false);
    // Set running before the await so a double-click can't start two runs.
    setRunning(true);
    try {
      const r = await runAvgRankings(params.k, params.scope, params.outMode, params.folder,
                                     params.source, params.sids, params.levels);
      if (!r.ok) { setError(r.error); setRunning(false); return; }
      setLastParams(params);
    } catch (err) {
      setError("Run failed."); setRunning(false);
    }
  }

  function handleRun() {
    start({
      k, scope: SCOPES[scope], outMode, folder, source,
      sids: source === "roster" ? validRoster.map(r => r.steam_id.trim()) : [],
      levels: scope === "Custom" ? JSON.stringify(customLevels) : "[]",
    });
  }

  function handleRefresh() {
    if (lastParams) start(lastParams);
  }

  async function handleStop() {
    await stopAvgRankings();
    setStatus("Stopping…");
  }

  function handleCopy() {
    const text = filteredRows
      .map(r => `${r._pos}\t${r.name}\t${r.avg_rank.toFixed(1)}\t${fmtPctBare(r.avg_pct, pctExtra ? 5 : 3)}`)
      .join("\n");
    navigator.clipboard.writeText(text).catch(() => {});
  }

  const showFolder = outMode === "csv" || outMode === "both";
  const runDisabled = (source === "roster" && validRoster.length === 0)
                   || (scope === "Custom" && customLevels.length === 0);

  return (
    <>
      <PageHead crumb={<>Leaderboard Tools <span style={{ color: "var(--text-3)", fontSize: "0.85em", fontWeight: 400 }}>· thanks Koyoi!</span></>} title="AVERAGE PLACEMENT" accentWord="LEADERBOARD"
        subtitle="Ranked by average per-level placement — consistency, not total time."
        actions={<>
          {filteredRows.length > 0 && !running && outMode !== "csv" &&
            <Btn kind="ghost" size="sm" icn="copy" onClick={handleCopy}>Copy</Btn>}
          {rows.length > 0 && !running && lastParams &&
            <Btn kind="ghost" size="sm" icn="refresh" onClick={handleRefresh}>Refresh</Btn>}
        </>}
      />
      <div className="body">
        <div className="panel-left">
          <div className="form">
            <Field label="Players from">
              <Seg options={["depth", "roster"]} value={source} onChange={setSource} />
              <div className="muted" style={{ fontSize: 10, marginTop: 4 }}>
                {source === "depth"
                  ? "Top players on the Global Rankings (total-time) board."
                  : "An explicit list of Steam IDs you choose."}
              </div>
            </Field>

            {source === "depth" && (
              <>
                <Field label="Board depth">
                  <input className="input" value={k} onChange={e => setK(e.target.value)}
                         disabled={running} style={{ width: 120 }} placeholder="500" />
                  <div className="muted" style={{ fontSize: 10, marginTop: 4 }}>
                    Scoring the top {Number(k) ? Number(k).toLocaleString() : "N"} players across {stageCount} stages.
                  </div>
                </Field>
                {Number(k) > 1000 && (
                  <div className="muted" style={{ fontSize: 10, color: "var(--accent)" }}>
                    Large depth — scoring {Number(k).toLocaleString()} players across every stage can take a while.
                  </div>
                )}
              </>
            )}

            {source === "roster" && (
              <Field label="Roster">
                <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                  {roster.map((row, idx) => {
                    const id = (row.steam_id || "").trim();
                    const dup = id && idCounts[id] > 1;
                    const bad = id && !STEAM_ID_RE.test(id);
                    return (
                      <div key={idx} style={{ display: "flex", gap: 6, alignItems: "center" }}>
                        <input className="input" style={{ flex: 1, fontSize: 11 }}
                               value={row.steam_id} disabled={running}
                               placeholder="17-digit Steam ID"
                               onChange={e => updateRow(idx, { steam_id: e.target.value })} />
                        <SavedProfilesDropdown
                          profiles={savedProfiles}
                          disabled={running}
                          disabledIds={rosterIds}
                          onSelect={p => applyProfileToRow(idx, p)}
                        />
                        <Btn kind="ghost" size="sm" disabled={running}
                             onClick={() => handleUseMine(idx)} title="Use my Steam ID">Mine</Btn>
                        <Btn kind="ghost" size="sm" disabled={running || roster.length <= 1}
                             onClick={() => removeRow(idx)} title="Remove">✕</Btn>
                        {(dup || bad) && (
                          <span style={{ fontSize: 10, color: "var(--bad, #e0533a)" }}>
                            {dup ? "dup" : "invalid"}
                          </span>
                        )}
                      </div>
                    );
                  })}
                  <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
                    <Btn kind="ghost" size="sm" disabled={running || roster.length >= ROSTER_MAX}
                         onClick={addRow}>+ Add player</Btn>
                    <Btn kind="ghost" size="sm" disabled={running || validRoster.length === 0}
                         onClick={handleSaveRoster}>Save roster…</Btn>
                    <span style={{ fontSize: 10, color: "var(--text-3)" }}>
                      {validRoster.length}/{roster.length} valid · max {ROSTER_MAX}
                    </span>
                  </div>
                  {savedRosters.length > 0 && (
                    <div style={{ display: "flex", flexWrap: "wrap", gap: 6, alignItems: "center" }}>
                      <span style={{ fontSize: 10, textTransform: "uppercase", letterSpacing: 0.5, color: "var(--text-3)" }}>
                        Saved
                      </span>
                      {savedRosters.map((sr, i) => (
                        <span key={`${sr.nickname}-${i}`} className="lpm-preset">
                          <span onClick={() => handleLoadSavedRoster(i)}
                                title={`Load ${sr.members?.length || 0} players`}>
                            {sr.nickname}
                          </span>
                          <span className="lpm-preset-x" onClick={() => handleDeleteSavedRoster(i)}
                                title="Delete roster">×</span>
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              </Field>
            )}

            <Field label="Stages">
              <Seg options={Object.keys(SCOPES)} value={scope} onChange={setScope} />
              <div className="muted" style={{ fontSize: 10, marginTop: 4 }}>
                {SCOPE_DESC[scope]}
              </div>
            </Field>
            {scope === "Custom" && (
              <Field label="Custom stages">
                <div style={{ display: "flex", gap: 8 }}>
                  <Btn kind="ghost" size="sm" onClick={() => setPickerOpen(true)} disabled={running}>
                    {customLevels.length ? `${customLevels.length} stages selected` : "Pick stages…"}
                  </Btn>
                  {customLevels.length > 0 && (
                    <Btn kind="ghost" size="sm" disabled={running}
                         onClick={() => handleCustomLevelsChange([])}>Clear</Btn>
                  )}
                </div>
              </Field>
            )}

            <Field label="Output">
              <Seg options={["display", "csv", "both"]} value={outMode} onChange={setOutMode} />
              <div className="muted" style={{ fontSize: 10, marginTop: 4 }}>
                {OUTPUT_DESC[outMode]}
              </div>
            </Field>
            {showFolder && (
              <Field label="Output folder" hint="Saved as avg_placement_<scope>_<depth|roster>.csv">
                <div style={{ display: "flex", gap: 8 }}>
                  <input className="input" style={{ flex: 1, fontSize: 10 }} value={folder}
                         onChange={e => { setFolder(e.target.value); setFolderTouched(true); }} disabled={running}
                         placeholder="Select a folder..." />
                  <Btn kind="ghost" size="sm" onClick={handlePickFolder} disabled={running}>Browse</Btn>
                </div>
              </Field>
            )}
            <div style={{
              fontSize: 10, color: "var(--text-3)", lineHeight: 1.5,
              padding: "6px 8px", border: "1px solid var(--border)",
              borderRadius: 4, background: "var(--surface-2)",
            }}>
              <span style={{ color: "var(--accent)", fontWeight: 600 }}>How it works:</span>{" "}
              {source === "depth" ? (
                <>Steam has no "average placement" board, so this takes the{" "}
                <span style={{ color: "var(--text-2)" }}>top {Number(k) || "N"} players</span> from
                the Global Rankings (total-time) board, measures each one's placement on every
                selected stage, and ranks them by their <span style={{ color: "var(--text-2)" }}>average
                placement</span>. Because the starting list is the total-time board, only{" "}
                <span style={{ color: "var(--text-2)" }}>complete-game players</span> appear. A full
                run fetches every stage and can take several minutes.</>
              ) : (
                <>This measures each player you list on the{" "}
                <span style={{ color: "var(--text-2)" }}>selected stages</span> and ranks them by
                their <span style={{ color: "var(--text-2)" }}>average placement</span>. Placement is
                each player's rank on the <span style={{ color: "var(--text-2)" }}>full Steam board</span>,
                not within your list. Everyone you add is shown — a player who hasn't charted on every
                stage appears with partial coverage rather than being dropped.</>
              )}
            </div>
            <ErrorBanner message={error} />
            <div style={{ display: "flex", gap: 8 }}>
              {running
                ? <Btn kind="danger" size="lg" onClick={handleStop}>Stop</Btn>
                : <Btn kind="primary" size="lg" icn="export" onClick={handleRun} disabled={runDisabled}>Run</Btn>}
            </div>
            {progress && (
              <div>
                <div style={{ height: 4, background: "var(--surface-2)", borderRadius: 2, marginBottom: 6 }}>
                  <div style={{
                    height: "100%", borderRadius: 2, background: "var(--accent)",
                    width: `${(progress.board_idx / progress.total_boards * 100).toFixed(1)}%`,
                    transition: "width 0.2s",
                  }} />
                </div>
                <div className="muted" style={{ fontSize: 10 }}>{status}</div>
              </div>
            )}
            {!progress && status && (
              <div className="muted" style={{ fontSize: 11 }}>{status}</div>
            )}
            {asOf && !running && (
              <div className="muted" style={{ fontSize: 10 }}>Updated {asOf}</div>
            )}
            {emptyBoards.length > 0 && !running && (
              <div style={{
                fontSize: 10, color: "var(--text-3)", lineHeight: 1.5,
                padding: "6px 8px", border: "1px solid var(--border)",
                borderRadius: 4, background: "var(--surface-2)",
              }}>
                <span style={{ color: "var(--accent)", fontWeight: 600 }}>
                  {emptyBoards.length} board{emptyBoards.length > 1 ? "s" : ""} returned no data
                </span>{" "}
                (counted against everyone's coverage): {emptyBoards.join(", ")}.
              </div>
            )}
          </div>
        </div>
        <div className="panel-right" style={{ overflow: "auto", display: "flex", flexDirection: "column" }}>
          {outMode === "csv" && running ? (
            <div className="muted" style={{ padding: 32, fontSize: 12, textAlign: "center" }}>
              Fetching boards…
            </div>
          ) : rows.length > 0 ? (
            <>
              <div style={{ display: "flex", alignItems: "center", gap: 12, padding: "10px 16px 6px", flexShrink: 0, flexWrap: "wrap" }}>
                <span style={{ fontSize: 12, fontWeight: 600 }}>
                  {nameFilter.trim()
                    ? `${filteredRows.length.toLocaleString()} of ${rows.length.toLocaleString()} players`
                    : `${rows.length.toLocaleString()} players`}
                </span>
                <input
                  className="input"
                  value={nameFilter}
                  onChange={e => setNameFilter(e.target.value)}
                  placeholder="Find a player by name…"
                  style={{ width: 200, fontSize: 11 }}
                />
                <Seg options={Object.keys(SORT_KEY)} value={sortBy} onChange={setSortBy} />
                <div style={{ display: "flex", alignItems: "center", gap: 12, marginLeft: "auto" }}>
                  {cheaterCount > 0 && <span style={{ fontSize: 10, color: "var(--accent)" }}>{cheaterCount} cheaters filtered</span>}
                  <span style={{ fontSize: 10, color: "var(--text-3)" }}>% decimals</span>
                  <Seg value={pctExtra ? "5" : "3"} onChange={v => setPctExtra(v === "5")}
                       options={["3", "5"]} />
                  <Seg value={largeText ? "Large" : "Normal"} onChange={v => setLargeText(v === "Large")}
                       options={["Normal", "Large"]} />
                </div>
              </div>
              <div style={{ fontSize: largeText ? 14 : 11, overflow: "auto", flex: 1 }}>
                <table className="nwt-hover-rows" style={{ width: "100%", borderCollapse: "collapse", tableLayout: "fixed" }}>
                  <colgroup>
                    <col style={{ width: largeText ? 64 : 56 }} />
                    <col />
                    <col style={{ width: largeText ? 110 : 90 }} />
                    <col style={{ width: largeText ? 150 : 110 }} />
                    <col style={{ width: largeText ? 96 : 80 }} />
                    <col style={{ width: largeText ? 104 : 90 }} />
                  </colgroup>
                  <thead style={{ position: "sticky", top: 0, background: "var(--bg-2)", zIndex: 2 }}>
                    <tr>
                      <th style={TH}>#</th>
                      <th style={TH}>Player</th>
                      <th style={TH}>Avg place</th>
                      <th style={TH}>Percentile</th>
                      <th style={TH}>Median</th>
                      <th style={TH}>Coverage</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredRows.map(r => (
                      <tr key={r.steam_id} style={{ borderBottom: "1px solid var(--border)" }}>
                        <td style={TD}>{r._pos}</td>
                        <td style={TD}>{r.name}</td>
                        <td style={{ ...TD, color: "var(--accent)", fontWeight: 600, whiteSpace: "nowrap" }}>#{r.avg_rank.toFixed(1)}</td>
                        <td style={{ ...TD, whiteSpace: "nowrap" }}>{fmtPct(r.avg_pct, pctExtra ? 5 : 3)}</td>
                        <td style={TD}>{Math.round(r.median_rank)}</td>
                        <td style={TD}
                            title={r.missing && r.missing.length ? `No entry on: ${r.missing.join(", ")}` : undefined}>
                          {r.boards_n === r.boards_total ? "—" : `${r.boards_n}/${r.boards_total}`}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          ) : (
            <div className="muted" style={{ padding: 32, fontSize: 12, textAlign: "center" }}>
              {running ? "Fetching boards…"
                : stoppedEmpty ? "Stopped before enough stages were scored to rank anyone."
                : "Configure and press Run to build the Average Placement Leaderboard."}
            </div>
          )}
        </div>
      </div>
      <LevelPickerModal
        open={pickerOpen}
        onClose={() => setPickerOpen(false)}
        value={customLevels}
        onChange={handleCustomLevelsChange}
        levels={levels}
        chapters={chapters}
      />
    </>
  );
}
