import React, { useState, useEffect } from "react";
import { PageHead, Field, Seg, Btn, ErrorBanner } from "../shared.jsx";
import { getLevels, runLevelSearch, stopLeaderboard, pickFolder } from "../api.js";

const TH = { padding: "4px 8px", fontWeight: 600, fontSize: 10, borderBottom: "1px solid var(--border)", textAlign: "left" };
const TD = { padding: "3px 8px", fontSize: 11 };

export default function LevelSearch({ outputFolder: defaultFolder = "" }) {
  const [levels, setLevels]     = useState([]);
  const [levelName, setLevel]   = useState("");
  const [count, setCount]       = useState("100");
  const [outMode, setOutMode]   = useState("display");
  const [folder, setFolder]     = useState(defaultFolder);
  const [folderTouched, setFolderTouched] = useState(false);
  const [running, setRunning]   = useState(false);
  const [status, setStatus]     = useState("");
  const [error, setError]       = useState("");
  const [rows, setRows]         = useState([]);

  useEffect(() => {
    getLevels().then(ls => {
      setLevels(ls);
      if (ls.length) setLevel(ls[0].display);
    });
    window._nwLevelEvent = (ev) => {
      if (ev.type === "status") {
        setStatus(ev.message);
      } else if (ev.type === "row") {
        setRows(prev => [...prev, ev]);
      } else if (ev.type === "done") {
        setStatus(ev.csv_path ? `${ev.message} → ${ev.csv_path}` : ev.message);
        setRunning(false);
      } else if (ev.type === "error") {
        setError(ev.message);
        setRunning(false);
      }
    };
    return () => { window._nwLevelEvent = null; };
  }, []);

  useEffect(() => {
    if (!folderTouched) setFolder(defaultFolder);
  }, [defaultFolder]);

  async function handlePickFolder() {
    const r = await pickFolder();
    if (r.ok && r.path) { setFolder(r.path); setFolderTouched(true); }
  }

  async function handleRun() {
    setError(""); setStatus(""); setRows([]);
    const r = await runLevelSearch(levelName, count, outMode, folder);
    if (!r.ok) { setError(r.error); return; }
    setRunning(true);
  }

  async function handleStop() {
    await stopLeaderboard();
    setStatus("Stopping...");
  }

  function handleCopy() {
    const text = rows.map(r => `${r.rank}\t${r.name}\t${r.time}`).join("\n");
    navigator.clipboard.writeText(text).catch(() => {});
  }

  const showFolder = outMode === "csv" || outMode === "both";

  return (
    <>
      <PageHead crumb="Leaderboard Tools" title="LEVEL" accentWord="SEARCH"
        actions={<>
          {rows.length > 0 && !running && outMode !== "csv" &&
            <Btn kind="ghost" size="sm" icn="copy" onClick={handleCopy}>Copy</Btn>}
          {running
            ? <Btn kind="danger" onClick={handleStop}>Stop</Btn>
            : <Btn kind="primary" icn="search" onClick={handleRun} disabled={!levelName}>Search</Btn>}
        </>}
      />
      <div className="body">
        <div className="panel-left">
          <div className="form">
            <Field label="Level">
              <select className="input" value={levelName}
                      onChange={e => setLevel(e.target.value)} disabled={running}>
                {levels.map(l => (
                  <option key={l.internal} value={l.display}>{l.display}</option>
                ))}
              </select>
            </Field>
            <Field label="Entries to fetch">
              <input className="input" value={count}
                     onChange={e => setCount(e.target.value)} disabled={running}
                     style={{ width: 100 }} />
            </Field>
            <Field label="Output">
              <Seg options={["display", "csv", "both"]} value={outMode} onChange={setOutMode} />
            </Field>
            {showFolder && (
              <Field label="Output folder"
                     hint={`Saved as ${(levelName || "Level").replace(/ /g, "_").replace(/'/g, "")}_top{count}.csv`}>
                <div style={{ display: "flex", gap: 8 }}>
                  <input className="input" style={{ flex: 1, fontSize: 10 }} value={folder}
                         onChange={e => { setFolder(e.target.value); setFolderTouched(true); }}
                         disabled={running} placeholder="Select a folder..." />
                  <Btn kind="ghost" size="sm" onClick={handlePickFolder} disabled={running}>Browse</Btn>
                </div>
              </Field>
            )}
            <ErrorBanner message={error} />
            {status && <div className="muted" style={{ fontSize: 11 }}>{status}</div>}
          </div>
        </div>
        <div className="panel-right" style={{ overflow: "auto" }}>
          {outMode === "csv" ? (
            <div className="muted" style={{ padding: 32, fontSize: 12, textAlign: "center" }}>
              {running ? "Fetching and writing CSV..." : status || "Results will be saved to CSV only."}
            </div>
          ) : rows.length > 0 ? (
            <table style={{ width: "100%", borderCollapse: "collapse" }}>
              <thead style={{ position: "sticky", top: 0, background: "var(--bg-2)" }}>
                <tr>
                  <th style={TH}>Rank</th>
                  <th style={TH}>Player</th>
                  <th style={TH}>Time</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r, i) => (
                  <tr key={i} style={{ borderBottom: "1px solid var(--border)" }}>
                    <td style={TD}>{r.rank}</td>
                    <td style={TD}>{r.name}</td>
                    <td style={TD}>{r.time}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div className="muted" style={{ padding: 32, fontSize: 12, textAlign: "center" }}>
              {running ? "Fetching entries..." : "Select a level and press Search."}
            </div>
          )}
        </div>
      </div>
    </>
  );
}
