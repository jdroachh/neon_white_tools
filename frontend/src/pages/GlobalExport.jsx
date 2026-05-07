import React, { useState, useEffect } from "react";
import { PageHead, Field, Seg, Btn, ErrorBanner, MedalBadge, MedalToggle } from "../shared.jsx";
import { runGlobalExport, stopLeaderboard, pickFolder } from "../api.js";

const TH = { padding: "4px 8px", fontWeight: 600, fontSize: "0.91em", borderBottom: "1px solid var(--border)", textAlign: "left" };
const TD = { padding: "3px 8px", fontSize: "1em" };

export default function GlobalExport({ outputFolder: defaultFolder = "" }) {
  const [count, setCount]         = useState("100");
  const [outMode, setOutMode]     = useState("display");
  const [folder, setFolder]       = useState(defaultFolder);
  const [running, setRunning]     = useState(false);
  const [status, setStatus]       = useState("");
  const [error, setError]         = useState("");
  const [rows, setRows]           = useState([]);
  const [progress, setProgress]   = useState(null);
  const [showMedals, setShowMedals] = useState(false);
  const [largeText, setLargeText]   = useState(false);

  // Sync folder when the app-level default changes (e.g. updated in Settings),
  // but only if the user hasn't manually overridden it this session.
  const [folderTouched, setFolderTouched] = useState(false);
  useEffect(() => {
    if (!folderTouched) setFolder(defaultFolder);
  }, [defaultFolder]);

  useEffect(() => {
    window._nwGlobalEvent = (ev) => {
      if (ev.type === "progress") {
        setProgress({ current: ev.level_idx, total: ev.total_levels });
        setStatus(`[${ev.level_idx}/${ev.total_levels}] ${ev.level_name}...`);
      } else if (ev.type === "row") {
        setRows(prev => [...prev, ev]);
      } else if (ev.type === "done") {
        setStatus(ev.csv_path ? `${ev.message} → ${ev.csv_path}` : ev.message);
        setRunning(false);
        setProgress(null);
      } else if (ev.type === "error") {
        setError(ev.message);
        setRunning(false);
        setProgress(null);
      }
    };
    return () => { window._nwGlobalEvent = null; };
  }, []);

  async function handlePickFolder() {
    const r = await pickFolder();
    if (r.ok && r.path) { setFolder(r.path); setFolderTouched(true); }
  }

  async function handleRun() {
    setError(""); setStatus("Starting..."); setRows([]); setProgress(null);
    const r = await runGlobalExport(count, outMode, folder);
    if (!r.ok) { setError(r.error); return; }
    setRunning(true);
  }

  async function handleStop() {
    await stopLeaderboard();
    setStatus("Stopping...");
  }

  function handleCopy() {
    const text = rows.map(r => `${r.rank}\t${r.level}\t${r.name}\t${r.time}`).join("\n");
    navigator.clipboard.writeText(text).catch(() => {});
  }

  const showFolder = outMode === "csv" || outMode === "both";

  return (
    <>
      <PageHead crumb="Leaderboard Tools" title="GLOBAL" accentWord="EXPORT"
        actions={<>
          {rows.length > 0 && !running && outMode !== "csv" &&
            <Btn kind="ghost" size="sm" icn="copy" onClick={handleCopy}>Copy</Btn>}
        </>}
      />
      <div className="body">
        <div className="panel-left">
          <div className="form">
            <Field label="Entries per level" hint="Top N entries fetched for each of the 121 levels.">
              <input className="input" value={count}
                     onChange={e => setCount(e.target.value)} disabled={running}
                     style={{ width: 100 }} />
            </Field>
            <Field label="Output">
              <Seg options={["display", "csv", "both"]} value={outMode} onChange={setOutMode} />
            </Field>
            {showFolder && (
              <Field label="Output folder" hint={`Saved as neon_white_top_${count || "N"}_entries.csv`}>
                <div style={{ display: "flex", gap: 8 }}>
                  <input className="input" style={{ flex: 1, fontSize: 10 }} value={folder}
                         onChange={e => { setFolder(e.target.value); setFolderTouched(true); }} disabled={running}
                         placeholder="Select a folder..." />
                  <Btn kind="ghost" size="sm" onClick={handlePickFolder} disabled={running}>Browse</Btn>
                </div>
              </Field>
            )}
            <ErrorBanner message={error} />
            <div style={{ display: "flex", gap: 8 }}>
              {running
                ? <Btn kind="danger" size="lg" onClick={handleStop}>Stop</Btn>
                : <Btn kind="primary" size="lg" icn="export" onClick={handleRun}>Run Export</Btn>}
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
                <span style={{ fontSize: 12, fontWeight: 600, flex: 1 }}>
                  {rows.length.toLocaleString()} entries
                </span>
                <div style={{ display: "flex", alignItems: "center", gap: 12, marginLeft: "auto" }}>
                  <MedalToggle value={showMedals} onChange={setShowMedals} />
                  <Seg value={largeText ? "Large" : "Normal"} onChange={v => setLargeText(v === "Large")}
                       options={["Normal", "Large"]} />
                </div>
              </div>
              <div style={{ fontSize: largeText ? 14 : 11, overflow: "auto", flex: 1 }}>
                <table style={{ width: "100%", borderCollapse: "collapse" }}>
                  <thead style={{ position: "sticky", top: 0, background: "var(--bg-2)" }}>
                    <tr>
                      <th style={TH}>Rank</th>
                      <th style={TH}>Level</th>
                      <th style={TH}>Player</th>
                      <th style={TH}>Time</th>
                      {showMedals && <th style={TH}>Medal</th>}
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((r, i) => (
                      <tr key={i} style={{ borderBottom: "1px solid var(--border)" }}>
                        <td style={TD}>{r.rank}</td>
                        <td style={TD}>{r.level}</td>
                        <td style={TD}>{r.name}</td>
                        <td style={TD}>{r.time}</td>
                        {showMedals && <td style={TD}><MedalBadge medal={r.medal} plain /></td>}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          ) : (
            <div className="muted" style={{ padding: 32, fontSize: 12, textAlign: "center" }}>
              {running ? "Fetching entries..." : "Configure and press Run Export to fetch leaderboards."}
            </div>
          )}
        </div>
      </div>
    </>
  );
}
