import React, { useState, useEffect } from "react";
import { PageHead, Field, Btn, ErrorBanner } from "../shared.jsx";
import { runGlobalExport, stopLeaderboard } from "../api.js";

const TH = { padding: "4px 8px", fontWeight: 600, fontSize: 10, borderBottom: "1px solid var(--border)", textAlign: "left" };
const TD = { padding: "3px 8px", fontSize: 11 };

export default function GlobalExport() {
  const [count, setCount]       = useState("100");
  const [running, setRunning]   = useState(false);
  const [status, setStatus]     = useState("");
  const [error, setError]       = useState("");
  const [rows, setRows]         = useState([]);
  const [progress, setProgress] = useState(null);

  useEffect(() => {
    window._nwGlobalEvent = (ev) => {
      if (ev.type === "progress") {
        setProgress({ current: ev.level_idx, total: ev.total_levels });
        setStatus(`[${ev.level_idx}/${ev.total_levels}] ${ev.level_name}...`);
      } else if (ev.type === "row") {
        setRows(prev => [...prev, ev]);
      } else if (ev.type === "done") {
        setStatus(ev.message);
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

  async function handleRun() {
    setError(""); setStatus("Starting..."); setRows([]); setProgress(null);
    const r = await runGlobalExport(count);
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

  return (
    <>
      <PageHead crumb="Leaderboard Tools" title="GLOBAL" accentWord="EXPORT"
        actions={<>
          {rows.length > 0 && !running &&
            <Btn kind="ghost" size="sm" icn="copy" onClick={handleCopy}>Copy</Btn>}
          {running
            ? <Btn kind="danger" onClick={handleStop}>Stop</Btn>
            : <Btn kind="primary" icn="export" onClick={handleRun}>Run Export</Btn>}
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
            <ErrorBanner message={error} />
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
        <div className="panel-right" style={{ overflow: "auto" }}>
          {rows.length > 0 ? (
            <table style={{ width: "100%", borderCollapse: "collapse" }}>
              <thead style={{ position: "sticky", top: 0, background: "var(--bg-2)" }}>
                <tr>
                  <th style={TH}>Rank</th>
                  <th style={TH}>Level</th>
                  <th style={TH}>Player</th>
                  <th style={TH}>Time</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r, i) => (
                  <tr key={i} style={{ borderBottom: "1px solid var(--border)" }}>
                    <td style={TD}>{r.rank}</td>
                    <td style={TD}>{r.level}</td>
                    <td style={TD}>{r.name}</td>
                    <td style={TD}>{r.time}</td>
                  </tr>
                ))}
              </tbody>
            </table>
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
