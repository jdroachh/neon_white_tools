import React, { useState, useEffect } from "react";
import { PageHead, Field, Seg, Btn, ErrorBanner, MedalBadge, MedalToggle } from "../shared.jsx";
import { getLevels, runLevelSearch, stopLeaderboard, pickFolder, getCheaterCount } from "../api.js";

const TH = { padding: "4px 8px", fontWeight: 600, fontSize: "0.91em", borderBottom: "1px solid var(--border)", textAlign: "left" };
const TD = { padding: "3px 8px", fontSize: "1em" };

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
  const [showMedals, setShowMedals]     = useState(false);
  const [largeText, setLargeText]       = useState(false);
  const [cheaterCount, setCheaterCount] = useState(0);

  useEffect(() => { getCheaterCount().then(n => { if (n > 0) setCheaterCount(n); }); }, []);

  useEffect(() => {
    let cancelled = false;
    let attempts = 0;
    function tryLoad() {
      getLevels().then(ls => {
        if (cancelled) return;
        if (Array.isArray(ls) && ls.length) {
          setLevels(ls);
          setLevel(ls[0].display);
        } else if (attempts++ < 20) {
          setTimeout(tryLoad, 250);
        }
      }).catch(() => {
        if (!cancelled && attempts++ < 20) setTimeout(tryLoad, 250);
      });
    }
    tryLoad();
    window._nwLevelEvent = (ev) => {
      if (ev.type === "status") {
        setStatus(ev.message);
      } else if (ev.type === "row") {
        setRows(prev => [...prev, ev]);
      } else if (ev.type === "done") {
        setStatus(ev.csv_path ? `${ev.message} → ${ev.csv_path}` : ev.message);
        setRunning(false);
        getCheaterCount().then(n => { if (n > 0) setCheaterCount(n); });
      } else if (ev.type === "error") {
        setError(ev.message);
        setRunning(false);
      }
    };
    return () => { cancelled = true; window._nwLevelEvent = null; };
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
            <div style={{ display: "flex", gap: 8 }}>
              {running
                ? <Btn kind="danger" size="lg" onClick={handleStop}>Stop</Btn>
                : <Btn kind="primary" size="lg" icn="search" onClick={handleRun} disabled={!levelName}>Search</Btn>}
            </div>
            {status && <div className="muted" style={{ fontSize: 11 }}>{status}</div>}
          </div>
        </div>
        <div className="panel-right" style={{ overflow: "auto", display: "flex", flexDirection: "column" }}>
          {outMode === "csv" ? (
            <div className="muted" style={{ padding: 32, fontSize: 12, textAlign: "center" }}>
              {running ? "Fetching and writing CSV..." : status || "Results will be saved to CSV only."}
            </div>
          ) : rows.length > 0 ? (
            <>
              <div style={{ display: "flex", alignItems: "center", gap: 12, padding: "10px 16px 6px", flexShrink: 0 }}>
                <span style={{ fontSize: 12, fontWeight: 600, flex: 1 }}>{levelName}</span>
                <div style={{ display: "flex", alignItems: "center", gap: 12, marginLeft: "auto" }}>
                  {cheaterCount > 0 && <span style={{ fontSize: 10, color: "var(--accent)" }}>{cheaterCount} cheaters filtered</span>}
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
                      <th style={TH}>Player</th>
                      <th style={TH}>Time</th>
                      {showMedals && <th style={TH}>Medal</th>}
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((r, i) => (
                      <tr key={i} style={{ borderBottom: "1px solid var(--border)" }}>
                        <td style={TD}>{r.rank}</td>
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
              {running ? "Fetching entries..." : "Select a level and press Search."}
            </div>
          )}
        </div>
      </div>
    </>
  );
}
