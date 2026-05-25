import React, { useState, useEffect, useMemo } from "react";
import { PageHead, Field, Seg, Btn, ErrorBanner } from "../shared.jsx";
import { runGlobalNeonRankings, stopLeaderboard, pickFolder, getCheaterCount } from "../api.js";

const TH = { padding: "4px 8px", fontWeight: 600, fontSize: "0.91em", borderBottom: "1px solid var(--border)", textAlign: "left" };
const TD = { padding: "3px 8px", fontSize: "1em" };

// Times are intentionally hidden on this page. Steam's GlobalNeonRankings is
// story-only sum; in-game total adds Sidequest client-side, so every time here
// would look ~half of what users see in-game and trigger false bug reports.
// See project memory project_global_neon_rankings.md.

export default function GlobalNeonRankings({ outputFolder: defaultFolder = "" }) {
  const [count, setCount]         = useState("100");
  const [outMode, setOutMode]     = useState("display");
  const [folder, setFolder]       = useState(defaultFolder);
  const [running, setRunning]     = useState(false);
  const [status, setStatus]       = useState("");
  const [error, setError]         = useState("");
  const [rows, setRows]           = useState([]);
  const [progress, setProgress]   = useState(null);
  const [largeText, setLargeText] = useState(false);
  const [cheaterCount, setCheaterCount] = useState(0);
  const [nameFilter, setNameFilter]     = useState("");

  const filteredRows = useMemo(() => {
    const q = nameFilter.trim().toLowerCase();
    if (!q) return rows;
    return rows.filter(r => r.name.toLowerCase().includes(q));
  }, [rows, nameFilter]);

  const [folderTouched, setFolderTouched] = useState(false);
  useEffect(() => {
    if (!folderTouched) setFolder(defaultFolder);
  }, [defaultFolder]);

  useEffect(() => { getCheaterCount().then(n => { if (n > 0) setCheaterCount(n); }); }, []);

  useEffect(() => {
    window._nwNeonRankingsEvent = (ev) => {
      if (ev.type === "status") {
        setStatus(ev.message);
      } else if (ev.type === "progress") {
        setProgress({ current: ev.current, total: ev.total });
        setStatus(`Fetched ${ev.current} / ${ev.total}...`);
      } else if (ev.type === "row") {
        setRows(prev => [...prev, ev]);
      } else if (ev.type === "done") {
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
    return () => { window._nwNeonRankingsEvent = null; };
  }, []);

  async function handlePickFolder() {
    const r = await pickFolder();
    if (r.ok && r.path) { setFolder(r.path); setFolderTouched(true); }
  }

  async function handleRun() {
    setError(""); setStatus("Starting..."); setRows([]); setProgress(null); setNameFilter("");
    const r = await runGlobalNeonRankings(count, outMode, folder);
    if (!r.ok) { setError(r.error); return; }
    setRunning(true);
  }

  async function handleStop() {
    await stopLeaderboard();
    setStatus("Stopping...");
  }

  function handleCopy() {
    const text = filteredRows.map(r => `${r.rank}\t${r.name}`).join("\n");
    navigator.clipboard.writeText(text).catch(() => {});
  }

  const showFolder = outMode === "csv" || outMode === "both";

  return (
    <>
      <PageHead crumb="Leaderboard Tools" title="GLOBAL" accentWord="RANKINGS"
        actions={<>
          {filteredRows.length > 0 && !running && outMode !== "csv" &&
            <Btn kind="ghost" size="sm" icn="copy" onClick={handleCopy}>Copy</Btn>}
        </>}
      />
      <div className="body">
        <div className="panel-left">
          <div className="form">
            <Field label="Entries" hint="Top N entries from the Global Neon Rankings board.">
              <input className="input" value={count}
                     onChange={e => setCount(e.target.value)} disabled={running}
                     style={{ width: 100 }} />
            </Field>
            <Field label="Output">
              <Seg options={["display", "csv", "both"]} value={outMode} onChange={setOutMode} />
            </Field>
            {showFolder && (
              <>
                <Field label="Output folder" hint={`Saved as neon_white_global_rankings_top_${count || "N"}.csv`}>
                  <div style={{ display: "flex", gap: 8 }}>
                    <input className="input" style={{ flex: 1, fontSize: 10 }} value={folder}
                           onChange={e => { setFolder(e.target.value); setFolderTouched(true); }} disabled={running}
                           placeholder="Select a folder..." />
                    <Btn kind="ghost" size="sm" onClick={handlePickFolder} disabled={running}>Browse</Btn>
                  </div>
                </Field>
                <div style={{
                  fontSize: 10, color: "var(--text-3)", lineHeight: 1.5,
                  padding: "6px 8px", border: "1px solid var(--border)",
                  borderRadius: 4, background: "var(--surface-2)",
                }}>
                  <span style={{ color: "var(--accent)", fontWeight: 600 }}>Note:</span>{" "}
                  The CSV includes a time column, but times reflect{" "}
                  <span style={{ color: "var(--text-2)" }}>story levels only</span> —
                  Sidequest times are not included (the in-game ranking adds them
                  client-side per player, which Steam does not expose).
                </div>
              </>
            )}
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
                    width: `${(progress.current / progress.total * 100).toFixed(1)}%`,
                    transition: "width 0.2s",
                  }} />
                </div>
                <div className="muted" style={{ fontSize: 10 }}>{status}</div>
              </div>
            )}
            {!progress && status && (
              <div className="muted" style={{ fontSize: 11 }}>{status}</div>
            )}
            {rows.length > 0 && (
              <div className="muted" style={{ fontSize: 10 }}>
                {rows.length.toLocaleString()} rows loaded
              </div>
            )}
          </div>
        </div>
        <div className="panel-right" style={{ overflow: "auto", display: "flex", flexDirection: "column" }}>
          {outMode === "csv" ? (
            <div className="muted" style={{ padding: 32, fontSize: 12, textAlign: "center" }}>
              {running ? "Writing CSV..." : rows.length > 0 ? `${rows.length.toLocaleString()} rows written to CSV.` : "Results will be saved to CSV only."}
            </div>
          ) : rows.length > 0 ? (
            <>
              <div style={{ display: "flex", alignItems: "center", gap: 12, padding: "10px 16px 6px", flexShrink: 0 }}>
                <span style={{ fontSize: 12, fontWeight: 600 }}>
                  {nameFilter.trim()
                    ? `${filteredRows.length.toLocaleString()} of ${rows.length.toLocaleString()} entries`
                    : `${rows.length.toLocaleString()} entries`}
                </span>
                <input
                  className="input"
                  value={nameFilter}
                  onChange={e => setNameFilter(e.target.value)}
                  placeholder="Filter by player name…"
                  style={{ width: 200, fontSize: 11 }}
                />
                <div style={{ display: "flex", alignItems: "center", gap: 12, marginLeft: "auto" }}>
                  {cheaterCount > 0 && <span style={{ fontSize: 10, color: "var(--accent)" }}>{cheaterCount} cheaters filtered</span>}
                  <Seg value={largeText ? "Large" : "Normal"} onChange={v => setLargeText(v === "Large")}
                       options={["Normal", "Large"]} />
                </div>
              </div>
              <div style={{ fontSize: largeText ? 14 : 11, overflow: "auto", flex: 1 }}>
                <table style={{ width: "100%", borderCollapse: "collapse", tableLayout: "fixed" }}>
                  <colgroup>
                    <col style={{ width: 80 }} />
                    <col />
                  </colgroup>
                  <thead style={{ position: "sticky", top: 0, background: "var(--bg-2)" }}>
                    <tr>
                      <th style={TH}>Rank</th>
                      <th style={TH}>Player</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredRows.map(r => (
                      <tr key={r.rank} style={{ borderBottom: "1px solid var(--border)" }}>
                        <td style={TD}>{r.rank}</td>
                        <td style={TD}>{r.name}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          ) : (
            <div className="muted" style={{ padding: 32, fontSize: 12, textAlign: "center" }}>
              {running ? "Fetching entries..." : "Configure and press Run to fetch the Global Neon Rankings."}
            </div>
          )}
        </div>
      </div>
    </>
  );
}
