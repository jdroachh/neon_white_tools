import React, { useState, useEffect, useMemo } from "react";
import { PageHead, Field, Seg, Btn, ErrorBanner } from "../shared.jsx";
import { runAvgRankings, stopAvgRankings, pickFolder, getCheaterCount } from "../api.js";

const TH = { padding: "4px 8px", fontWeight: 600, fontSize: "0.91em", borderBottom: "1px solid var(--border)", textAlign: "left" };
const TD = { padding: "3px 8px", fontSize: "1em" };

// Times are intentionally absent here — this board ranks by AVERAGE per-level
// placement (consistency), not by any time. The seed set is the top-K of
// GlobalNeonRankings, so players without a complete game are unrankable (no
// GlobalNeonRankings entry). See plans/2026-06-22-avg-rankings-in-app.md.

const SCOPES = { "All stages": "story+side", "Main game": "story", "Sidequests": "side" };
const SCOPE_DESC = {
  "All stages": "All 121 stages.",
  "Main game": "Main-game only (excludes Red/Violet/Yellow stages).",
  "Sidequests": "Sidequest stages only (24 Red/Violet/Yellow stages).",
};
const SCOPE_BOARDS = { "All stages": 121, "Main game": 97, "Sidequests": 24 };
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

export default function AvgRankings({ outputFolder: defaultFolder = "" }) {
  const [k, setK]                 = useState("500");   // user-set board depth
  const [scope, setScope]         = useState("All stages");
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

  const boardsTotal = rows[0]?.boards_total;

  const [folderTouched, setFolderTouched] = useState(false);
  useEffect(() => { if (!folderTouched) setFolder(defaultFolder); }, [defaultFolder]);

  useEffect(() => { getCheaterCount().then(n => { if (n > 0) setCheaterCount(n); }); }, []);

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

  async function start(params) {
    setError(""); setStatus("Starting…"); setRows([]); setAsOf(""); setProgress(null); setNameFilter(""); setEmptyBoards([]); setStoppedEmpty(false);
    const r = await runAvgRankings(params.k, params.scope, params.outMode, params.folder);
    if (!r.ok) { setError(r.error); return; }
    setLastParams(params);
    setRunning(true);
  }

  function handleRun() {
    start({ k, scope: SCOPES[scope], outMode, folder });
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
            <Field label="Board depth">
              <input className="input" value={k} onChange={e => setK(e.target.value)}
                     disabled={running} style={{ width: 120 }} placeholder="500" />
              <div className="muted" style={{ fontSize: 10, marginTop: 4 }}>
                Scoring the top {Number(k) ? Number(k).toLocaleString() : "N"} players across {SCOPE_BOARDS[scope]} stages.
              </div>
            </Field>
            {Number(k) > 1000 && (
              <div className="muted" style={{ fontSize: 10, color: "var(--accent)" }}>
                Large depth — scoring {Number(k).toLocaleString()} players across every stage can take a while.
              </div>
            )}
            <Field label="Stages">
              <Seg options={Object.keys(SCOPES)} value={scope} onChange={setScope} />
              <div className="muted" style={{ fontSize: 10, marginTop: 4 }}>
                {SCOPE_DESC[scope]}
              </div>
            </Field>
            <Field label="Output">
              <Seg options={["display", "csv", "both"]} value={outMode} onChange={setOutMode} />
              <div className="muted" style={{ fontSize: 10, marginTop: 4 }}>
                {OUTPUT_DESC[outMode]}
              </div>
            </Field>
            {showFolder && (
              <Field label="Output folder" hint="Saved as avg_placement_<scope>_topK.csv">
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
              Steam has no "average placement" board, so this takes the{" "}
              <span style={{ color: "var(--text-2)" }}>top {Number(k) || "N"} players</span> from
              the Global Rankings (total-time) board, measures each one's placement on every
              stage, and ranks them by their <span style={{ color: "var(--text-2)" }}>average
              placement</span>. Because the starting list is the total-time board, only{" "}
              <span style={{ color: "var(--text-2)" }}>complete-game players</span> appear. A full
              run fetches every stage and can take several minutes.
            </div>
            <ErrorBanner message={error} />
            <div style={{ display: "flex", gap: 8 }}>
              {running
                ? <Btn kind="danger" size="lg" onClick={handleStop}>Stop</Btn>
                : <Btn kind="primary" size="lg" icn="export" onClick={handleRun}>Run</Btn>}
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
    </>
  );
}
