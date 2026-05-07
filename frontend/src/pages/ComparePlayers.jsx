import React, { useState, useEffect } from "react";
import { PageHead, Field, Seg, Btn, ErrorBanner, MedalBadge, MedalToggle } from "../shared.jsx";
import { getLevels, getChapters, getSteamStatus, runComparePlayers, stopLeaderboard } from "../api.js";

const TH = { padding: "4px 8px", fontWeight: 600, fontSize: "0.91em", borderBottom: "1px solid var(--border)", textAlign: "left" };
const TD = { padding: "3px 8px", fontSize: "1em" };
const FASTER_BG    = "rgba(120, 220, 160, 0.12)";
const FASTER_COLOR = "rgb(120, 220, 160)";

function formatDelta(delta_ms) {
  const secs = delta_ms / 1000;
  if (secs === 0) return "0.000";
  const sign = secs > 0 ? "+" : "−";
  return `${sign}${Math.abs(secs).toFixed(3)}`;
}

export default function ComparePlayers() {
  const [steamId1, setSteamId1]       = useState("");
  const [steamId2, setSteamId2]       = useState("");
  const [mode, setMode]               = useState("level");
  const [levels, setLevels]           = useState([]);
  const [chapters, setChapters]       = useState([]);
  const [levelName, setLevelName]     = useState("");
  const [chapterName, setChapterName] = useState("");
  const [running, setRunning]         = useState(false);
  const [status, setStatus]           = useState("");
  const [error, setError]             = useState("");
  const [rows, setRows]               = useState([]);
  const [playerName1, setPlayerName1] = useState("");
  const [playerName2, setPlayerName2] = useState("");
  const [showMedals, setShowMedals]   = useState(false);
  const [largeText, setLargeText]     = useState(false);

  useEffect(() => {
    getLevels().then(ls => { setLevels(ls); if (ls.length) setLevelName(ls[0].display); });
    getChapters().then(cs => { setChapters(cs); if (cs.length) setChapterName(cs[0].name); });
    window._nwCompareEvent = (ev) => {
      if (ev.type === "status") {
        setStatus(ev.message);
        if (ev.player_name_1) setPlayerName1(ev.player_name_1);
        if (ev.player_name_2) setPlayerName2(ev.player_name_2);
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
    return () => { window._nwCompareEvent = null; };
  }, []);

  async function handleUseMine1() {
    const s = await getSteamStatus();
    if (s.ready && s.steam_id) {
      setSteamId1(String(s.steam_id));
    } else {
      setError("Steam not connected. Connect in Settings first.");
    }
  }

  async function handleUseMine2() {
    const s = await getSteamStatus();
    if (s.ready && s.steam_id) {
      setSteamId2(String(s.steam_id));
    } else {
      setError("Steam not connected. Connect in Settings first.");
    }
  }

  async function handleRun() {
    setError(""); setStatus(""); setRows([]); setPlayerName1(""); setPlayerName2("");
    const target = mode === "level" ? levelName : mode === "chapter" ? chapterName : "";
    const r = await runComparePlayers(steamId1, steamId2, mode, target);
    if (!r.ok) { setError(r.error); return; }
    setRunning(true);
  }

  async function handleStop() {
    await stopLeaderboard();
    setStatus("Stopping...");
  }

  function handleCopy() {
    const p1 = playerName1 || "Player 1";
    const p2 = playerName2 || "Player 2";
    const header = `Level\t${p1} Rank\t${p1} Time\tΔ\t${p2} Time\t${p2} Rank`;
    const lines = rows.map(r => {
      const p1rank = r.p1 ? `#${r.p1.rank}` : "—";
      const p1time = r.p1 ? r.p1.time : "—";
      const p2rank = r.p2 ? `#${r.p2.rank}` : "—";
      const p2time = r.p2 ? r.p2.time : "—";
      const delta  = r.delta_ms != null ? formatDelta(r.delta_ms) : "—";
      return `${r.level}\t${p1rank}\t${p1time}\t${delta}\t${p2time}\t${p2rank}`;
    });
    navigator.clipboard.writeText([header, ...lines].join("\n")).catch(() => {});
  }

  return (
    <>
      <PageHead crumb="Leaderboard Tools" title="COMPARE" accentWord="PLAYERS"
        actions={<>
          {rows.length > 0 && !running &&
            <Btn kind="ghost" size="sm" icn="copy" onClick={handleCopy}>Copy</Btn>}
        </>}
      />
      <div className="body">
        <div className="panel-left">
          <div className="form">
            <Field label="Player 1 Steam ID" hint="17-digit number from the player's Steam profile URL.">
              <div style={{ display: "flex", gap: 8 }}>
                <input className="input" style={{ flex: 1 }} value={steamId1}
                       onChange={e => setSteamId1(e.target.value)}
                       placeholder="76561198..." disabled={running} />
                <Btn kind="ghost" size="sm" onClick={handleUseMine1} disabled={running}>Mine</Btn>
              </div>
            </Field>
            <Field label="Player 2 Steam ID" hint="17-digit number from the player's Steam profile URL.">
              <div style={{ display: "flex", gap: 8 }}>
                <input className="input" style={{ flex: 1 }} value={steamId2}
                       onChange={e => setSteamId2(e.target.value)}
                       placeholder="76561198..." disabled={running} />
                <Btn kind="ghost" size="sm" onClick={handleUseMine2} disabled={running}>Mine</Btn>
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
            <div style={{ display: "flex", gap: 8 }}>
              {running
                ? <Btn kind="danger" size="lg" onClick={handleStop}>Stop</Btn>
                : <Btn kind="primary" size="lg" icn="user" onClick={handleRun}>Compare</Btn>}
            </div>
            {status && <div className="muted" style={{ fontSize: 11 }}>{status}</div>}
          </div>
        </div>
        <div className="panel-right" style={{ overflow: "auto", display: "flex", flexDirection: "column" }}>
          {rows.length > 0 ? (
            <>
              <div style={{ display: "flex", alignItems: "center", gap: 12, padding: "10px 16px 6px", flexShrink: 0 }}>
                <span style={{ fontSize: 12, fontWeight: 600, flex: 1 }}>
                  {playerName1 || "Player 1"} vs {playerName2 || "Player 2"}
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
                      <th style={TH}>Level</th>
                      <th style={TH}>P1 Rank</th>
                      <th style={TH}>P1 Time</th>
                      {showMedals && <th style={TH}>P1 Medal</th>}
                      <th style={TH}>&Delta;</th>
                      {showMedals && <th style={TH}>P2 Medal</th>}
                      <th style={TH}>P2 Time</th>
                      <th style={TH}>P2 Rank</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((r, i) => {
                      const p1bg    = r.faster === "p1" ? FASTER_BG : undefined;
                      const p2bg    = r.faster === "p2" ? FASTER_BG : undefined;
                      const dColor  = (r.faster === "p1" || r.faster === "p2") ? FASTER_COLOR : undefined;
                      const delta   = r.delta_ms != null ? formatDelta(r.delta_ms) : "—";
                      return (
                        <tr key={i} style={{ borderBottom: "1px solid var(--border)" }}>
                          <td style={TD}>{r.level}</td>
                          <td style={TD}>{r.p1 ? `#${r.p1.rank}` : "—"}</td>
                          <td style={{ ...TD, backgroundColor: p1bg }}>{r.p1 ? r.p1.time : "—"}</td>
                          {showMedals && <td style={TD}>{r.p1 ? <MedalBadge medal={r.p1.medal} plain /> : "—"}</td>}
                          <td style={{ ...TD, color: dColor }}>{delta}</td>
                          {showMedals && <td style={TD}>{r.p2 ? <MedalBadge medal={r.p2.medal} plain /> : "—"}</td>}
                          <td style={{ ...TD, backgroundColor: p2bg }}>{r.p2 ? r.p2.time : "—"}</td>
                          <td style={TD}>{r.p2 ? `#${r.p2.rank}` : "—"}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </>
          ) : (
            <div className="muted" style={{ padding: 32, fontSize: 12, textAlign: "center" }}>
              {running ? "Comparing players..." : "Enter two Steam IDs and press Compare."}
            </div>
          )}
        </div>
      </div>
    </>
  );
}
