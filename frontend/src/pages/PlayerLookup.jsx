import React, { useState, useEffect } from "react";
import { PageHead, Field, Seg, Btn, ErrorBanner } from "../shared.jsx";
import { getLevels, getChapters, getSteamStatus, runPlayerLookup, stopLeaderboard } from "../api.js";

const TH = { padding: "4px 8px", fontWeight: 600, fontSize: 10, borderBottom: "1px solid var(--border)", textAlign: "left" };
const TD = { padding: "3px 8px", fontSize: 11 };

export default function PlayerLookup() {
  const [steamId, setSteamId]       = useState("");
  const [mode, setMode]             = useState("level");
  const [levels, setLevels]         = useState([]);
  const [chapters, setChapters]     = useState([]);
  const [levelName, setLevelName]   = useState("");
  const [chapterName, setChapterName] = useState("");
  const [running, setRunning]       = useState(false);
  const [status, setStatus]         = useState("");
  const [error, setError]           = useState("");
  const [rows, setRows]             = useState([]);
  const [playerName, setPlayerName] = useState("");

  useEffect(() => {
    getLevels().then(ls => { setLevels(ls); if (ls.length) setLevelName(ls[0].display); });
    getChapters().then(cs => { setChapters(cs); if (cs.length) setChapterName(cs[0].name); });
    window._nwPlayerEvent = (ev) => {
      if (ev.type === "status") {
        setStatus(ev.message);
        if (ev.player_name) setPlayerName(ev.player_name);
      } else if (ev.type === "row") {
        setRows(prev => [...prev, ev]);
      } else if (ev.type === "done") {
        setStatus(ev.message);
        setRunning(false);
      } else if (ev.type === "error") {
        setError(ev.message);
        setRunning(false);
      }
    };
    return () => { window._nwPlayerEvent = null; };
  }, []);

  async function handleUseMine() {
    const s = await getSteamStatus();
    if (s.ready && s.steam_id) {
      setSteamId(String(s.steam_id));
    } else {
      setError("Steam not connected. Connect in Settings first.");
    }
  }

  async function handleRun() {
    setError(""); setStatus(""); setRows([]); setPlayerName("");
    const target = mode === "level" ? levelName : mode === "chapter" ? chapterName : "";
    const r = await runPlayerLookup(steamId, mode, target);
    if (!r.ok) { setError(r.error); return; }
    setRunning(true);
  }

  async function handleStop() {
    await stopLeaderboard();
    setStatus("Stopping...");
  }

  function handleCopy() {
    const header = playerName ? `${playerName}\n` : "";
    const text = header + rows.map(r => `${r.level}\t#${r.rank}\t${r.time}`).join("\n");
    navigator.clipboard.writeText(text).catch(() => {});
  }

  return (
    <>
      <PageHead crumb="Leaderboard Tools" title="PLAYER" accentWord="LOOKUP"
        actions={<>
          {rows.length > 0 && !running &&
            <Btn kind="ghost" size="sm" icn="copy" onClick={handleCopy}>Copy</Btn>}
          {running
            ? <Btn kind="danger" onClick={handleStop}>Stop</Btn>
            : <Btn kind="primary" icn="user" onClick={handleRun}>Look Up</Btn>}
        </>}
      />
      <div className="body">
        <div className="panel-left">
          <div className="form">
            <Field label="Steam ID" hint="17-digit number from the player's Steam profile URL.">
              <div style={{ display: "flex", gap: 8 }}>
                <input className="input" style={{ flex: 1 }} value={steamId}
                       onChange={e => setSteamId(e.target.value)}
                       placeholder="76561198..." disabled={running} />
                <Btn kind="ghost" size="sm" onClick={handleUseMine} disabled={running}>Mine</Btn>
              </div>
            </Field>
            <Field label="Search mode">
              <Seg options={["level", "chapter", "game"]} value={mode}
                   onChange={v => { setMode(v); setError(""); }} />
            </Field>
            {mode === "level" && (
              <Field label="Level">
                <select className="input" value={levelName}
                        onChange={e => setLevelName(e.target.value)} disabled={running}>
                  {levels.map(l => (
                    <option key={l.internal} value={l.display}>{l.display}</option>
                  ))}
                </select>
              </Field>
            )}
            {mode === "chapter" && (
              <Field label="Chapter">
                <select className="input" value={chapterName}
                        onChange={e => setChapterName(e.target.value)} disabled={running}>
                  {chapters.map(c => (
                    <option key={c.name} value={c.name}>{c.name}</option>
                  ))}
                </select>
              </Field>
            )}
            {mode === "game" && (
              <div className="muted" style={{ fontSize: 11 }}>
                All 121 levels will be searched.
              </div>
            )}
            <ErrorBanner message={error} />
            {status && <div className="muted" style={{ fontSize: 11 }}>{status}</div>}
          </div>
        </div>
        <div className="panel-right" style={{ overflow: "auto" }}>
          {rows.length > 0 ? (
            <>
              {playerName && (
                <div style={{ padding: "12px 16px 0", fontSize: 12, fontWeight: 600 }}>
                  {playerName}
                </div>
              )}
              <table style={{ width: "100%", borderCollapse: "collapse" }}>
                <thead style={{ position: "sticky", top: 0, background: "var(--bg-2)" }}>
                  <tr>
                    <th style={TH}>Level</th>
                    <th style={TH}>Rank</th>
                    <th style={TH}>Time</th>
                    <th style={TH}>/ Total</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r, i) => (
                    <tr key={i} style={{ borderBottom: "1px solid var(--border)" }}>
                      <td style={TD}>{r.level}</td>
                      <td style={TD}>#{r.rank}</td>
                      <td style={TD}>{r.time}</td>
                      <td style={{ ...TD, color: "var(--text-3)" }}>
                        {r.total ? `/ ${r.total.toLocaleString()}` : ""}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          ) : (
            <div className="muted" style={{ padding: 32, fontSize: 12, textAlign: "center" }}>
              {running ? "Looking up entries..." : "Enter a Steam ID and press Look Up."}
            </div>
          )}
        </div>
      </div>
    </>
  );
}
