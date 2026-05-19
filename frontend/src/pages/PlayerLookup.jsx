import React, { useState, useEffect, useMemo } from "react";
import { PageHead, Field, Seg, Btn, ErrorBanner, MedalBadge, MedalToggle } from "../shared.jsx";
import { getLevels, getChapters, getSteamStatus, runPlayerLookup, stopLeaderboard, pickFolder } from "../api.js";
import { loadLevelsWithRetry } from "../lib/retryLevels.js";

const TH = { padding: "4px 8px", fontWeight: 600, fontSize: "0.91em", borderBottom: "1px solid var(--border)", textAlign: "left" };
const TD = { padding: "3px 8px", fontSize: "1em" };

export default function PlayerLookup({ outputFolder: defaultFolder = "" }) {
  const [steamId, setSteamId]         = useState("");
  const [mode, setMode]               = useState("level");
  const [levels, setLevels]           = useState([]);
  const [chapters, setChapters]       = useState([]);
  const [levelName, setLevelName]     = useState("");
  const [chapterName, setChapterName] = useState("");
  const [outMode, setOutMode]         = useState("display");
  const [folder, setFolder]           = useState(defaultFolder);
  const [folderTouched, setFolderTouched] = useState(false);
  const [running, setRunning]         = useState(false);
  const [status, setStatus]           = useState("");
  const [error, setError]             = useState("");
  const [rows, setRows]               = useState([]);
  const [playerName, setPlayerName]   = useState("");
  const [showMedals, setShowMedals]   = useState(false);
  const [largeText, setLargeText]     = useState(false);
  const [totalLevels, setTotalLevels] = useState(0);
  const [sortKey, setSortKey]         = useState("level");
  const [filterKey, setFilterKey]     = useState("all");

  useEffect(() => {
    const cancelLevels = loadLevelsWithRetry(getLevels, {
      onLevels: ls => { setLevels(ls); setLevelName(ls[0].display); }
    });
    getChapters().then(cs => { setChapters(cs); if (cs.length) setChapterName(cs[0].name); });
    window._nwPlayerEvent = (ev) => {
      if (ev.type === "status") {
        setStatus(ev.message);
        if (ev.player_name) setPlayerName(ev.player_name);
      } else if (ev.type === "row") {
        setRows(prev => [...prev, ev]);
      } else if (ev.type === "done") {
        setStatus(ev.csv_path ? `${ev.message} → ${ev.csv_path}` : ev.message);
        setTotalLevels(ev.total_levels || 0);
        setRunning(false);
      } else if (ev.type === "error") {
        setError(ev.message);
        setRunning(false);
      }
    };
    return () => { cancelLevels(); window._nwPlayerEvent = null; };
  }, []);

  useEffect(() => {
    if (!folderTouched) setFolder(defaultFolder);
  }, [defaultFolder]);

  useEffect(() => {
    if (!showMedals) {
      if (sortKey === "medal_tier") setSortKey("level");
      if (filterKey === "community_medal") setFilterKey("all");
    }
  }, [showMedals]);

  async function handlePickFolder() {
    const r = await pickFolder();
    if (r.ok && r.path) { setFolder(r.path); setFolderTouched(true); }
  }

  async function handleUseMine() {
    const s = await getSteamStatus();
    if (s.ready && s.steam_id) {
      setSteamId(String(s.steam_id));
    } else {
      setError("Steam not connected. Connect in Settings first.");
    }
  }

  async function handleRun() {
    setError(""); setStatus(""); setRows([]); setPlayerName(""); setTotalLevels(0);
    setSortKey("level"); setFilterKey("all");
    const target = mode === "level" ? levelName : mode === "chapter" ? chapterName : "";
    const r = await runPlayerLookup(steamId, mode, target, outMode, folder);
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

  const showFolder = outMode === "csv" || outMode === "both";

  const MEDAL_TIER_ORDER = ["BLOOD DIAMOND","TOPAZ","SAPPHIRE","AMETHYST","EMERALD","DEV","ACE","GOLD","SILVER","BRONZE"];
  const COMMUNITY_MEDALS = new Set(["BLOOD DIAMOND","TOPAZ","SAPPHIRE","AMETHYST","EMERALD"]);

  function formatDuration(ms) {
    const totalSec = Math.round(ms / 1000);
    const h = Math.floor(totalSec / 3600);
    const m = Math.floor((totalSec % 3600) / 60);
    const s = totalSec % 60;
    if (h) return `${h}h ${m}m ${s}s`;
    if (m) return `${m}m ${s}s`;
    return `${s}s`;
  }

  const medalCounts = useMemo(() => {
    const counts = {};
    rows.forEach(r => { if (r.medal) counts[r.medal] = (counts[r.medal] || 0) + 1; });
    return counts;
  }, [rows]);

  const stats = useMemo(() => {
    if (!rows.length) return null;
    const ranks = rows.map(r => r.rank).sort((a, b) => a - b);
    const mid = Math.floor(ranks.length / 2);
    const medianRank = ranks.length % 2 ? ranks[mid] : Math.round((ranks[mid - 1] + ranks[mid]) / 2);
    const avgRank = Math.round(rows.reduce((s, r) => s + r.rank, 0) / rows.length);
    const best  = rows.reduce((b, r) => r.rank < b.rank ? r : b);
    const worst = rows.reduce((b, r) => r.rank > b.rank ? r : b);
    const top10  = rows.filter(r => r.rank <= 10).length;
    const top100 = rows.filter(r => r.rank <= 100).length;
    const top500 = rows.filter(r => r.rank <= 500).length;
    const totalTimeMs = rows.reduce((s, r) => s + (r.score_ms || 0), 0);
    return { avgRank, medianRank, best, worst, top10, top100, top500, totalTimeMs };
  }, [rows]);

  const displayRows = useMemo(() => {
    const filtered = rows.filter(r => {
      switch (filterKey) {
        case "top_10":          return r.rank <= 10;
        case "top_100":         return r.rank <= 100;
        case "top_500":         return r.rank <= 500;
        case "community_medal": return COMMUNITY_MEDALS.has(r.medal);
        default:                return true;
      }
    });
    if (sortKey === "level") return filtered;
    return [...filtered].sort((a, b) => {
      switch (sortKey) {
        case "rank":       return a.rank - b.rank;
        case "time":       return (a.score_ms || 0) - (b.score_ms || 0);
        case "medal_tier": {
          const ai = MEDAL_TIER_ORDER.indexOf(a.medal); const bi = MEDAL_TIER_ORDER.indexOf(b.medal);
          return (ai === -1 ? 99 : ai) - (bi === -1 ? 99 : bi);
        }
        default: return 0;
      }
    });
  }, [rows, sortKey, filterKey]);

  return (
    <>
      <PageHead crumb="Leaderboard Tools" title="PLAYER" accentWord="LOOKUP"
        actions={<>
          {rows.length > 0 && !running && outMode !== "csv" &&
            <Btn kind="ghost" size="sm" icn="copy" onClick={handleCopy}>Copy</Btn>}
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
            <Field label="Output">
              <Seg options={["display", "csv", "both"]} value={outMode} onChange={setOutMode} />
            </Field>
            {showFolder && (
              <Field label="Output folder" hint="Saved as {DisplayName}_{context}.csv">
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
                : <Btn kind="primary" size="lg" icn="user" onClick={handleRun}>Look Up</Btn>}
            </div>
            {status && <div className="muted" style={{ fontSize: 11 }}>{status}</div>}
          </div>
        </div>
        <div className="panel-right" style={{ overflow: "auto", display: "flex", flexDirection: "column" }}>
          {outMode === "csv" ? (
            <div className="muted" style={{ padding: 32, fontSize: 12, textAlign: "center" }}>
              {running ? "Looking up and writing CSV..." : status || "Results will be saved to CSV only."}
            </div>
          ) : rows.length > 0 ? (
            <>
              {mode !== "level" && stats && (
                <div style={{
                  borderBottom: "1px solid var(--border)",
                  padding: "8px 16px 6px",
                  flexShrink: 0,
                }}>
                  <div style={{ fontSize: 11, color: "var(--text-2)", lineHeight: 1.7 }}>
                    Avg <span style={{ color: "var(--text)" }}>#{stats.avgRank}</span>
                    {"  ·  "}Median <span style={{ color: "var(--text)" }}>#{stats.medianRank}</span>
                    {"  ·  "}Best <span style={{ color: "var(--text)" }}>#{stats.best.rank}</span>
                    {" "}<span style={{ color: "var(--text-3)" }}>({stats.best.level})</span>
                    {"  ·  "}Worst <span style={{ color: "var(--text)" }}>#{stats.worst.rank}</span>
                    {" "}<span style={{ color: "var(--text-3)" }}>({stats.worst.level})</span>
                  </div>
                  <div style={{ fontSize: 11, color: "var(--text-3)", lineHeight: 1.7 }}>
                    Top 10: <span style={{ color: "var(--text-2)" }}>{stats.top10}</span>
                    {"  ·  "}Top 100: <span style={{ color: "var(--text-2)" }}>{stats.top100}</span>
                    {"  ·  "}Top 500: <span style={{ color: "var(--text-2)" }}>{stats.top500}</span>
                    {"  ·  "}Total time: <span style={{ color: "var(--text-2)" }}>{formatDuration(stats.totalTimeMs)}</span>
                  </div>
                  {showMedals && MEDAL_TIER_ORDER.some(t => medalCounts[t]) && (
                    <div style={{ display: "flex", flexWrap: "wrap", gap: "4px 8px", marginTop: 4, fontSize: 11, color: "var(--text-3)" }}>
                      {MEDAL_TIER_ORDER.filter(t => medalCounts[t]).map(t => (
                        <span key={t} style={{ display: "inline-flex", alignItems: "center", gap: 3 }}>
                          <MedalBadge medal={t} />
                          <span style={{ color: "var(--text-3)" }}>{medalCounts[t]}</span>
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              )}
              <div style={{ display: "flex", alignItems: "center", gap: 12, padding: "10px 16px 6px", flexShrink: 0 }}>
                {playerName && (
                  <span style={{ fontSize: 12, fontWeight: 600, flex: 1 }}>{playerName}</span>
                )}
                <div style={{ display: "flex", alignItems: "center", gap: 12, marginLeft: "auto" }}>
                  {mode !== "level" && <>
                    <select className="input" value={sortKey} onChange={e => setSortKey(e.target.value)}
                            style={{ fontSize: 11 }}>
                      <option value="level">Sort: Level</option>
                      <option value="rank">Sort: Rank</option>
                      <option value="time">Sort: Time</option>
                      {showMedals && <option value="medal_tier">Sort: Medal</option>}
                    </select>
                    <select className="input" value={filterKey} onChange={e => setFilterKey(e.target.value)}
                            style={{ fontSize: 11 }}>
                      <option value="all">Filter: All</option>
                      <option value="top_10">Filter: Top 10</option>
                      <option value="top_100">Filter: Top 100</option>
                      <option value="top_500">Filter: Top 500</option>
                      {showMedals && <option value="community_medal">Filter: Community Medal</option>}
                    </select>
                  </>}
                  <MedalToggle value={showMedals} onChange={setShowMedals} />
                  <Seg value={largeText ? "Large" : "Normal"} onChange={(v) => setLargeText(v === "Large")}
                       options={["Normal", "Large"]} />
                </div>
              </div>
              <div style={{ fontSize: largeText ? 14 : 11, overflow: "auto", flex: 1 }}>
                <table style={{ width: "100%", borderCollapse: "collapse" }}>
                  <thead style={{ position: "sticky", top: 0, background: "var(--bg-2)" }}>
                    <tr>
                      <th style={TH}>Level</th>
                      <th style={TH}>Rank</th>
                      <th style={TH}>Time</th>
                      {showMedals && <th style={TH}>Medal</th>}
                      <th style={TH}>/ Total</th>
                    </tr>
                  </thead>
                  <tbody>
                    {displayRows.map((r, i) => (
                      <tr key={i} style={{ borderBottom: "1px solid var(--border)" }}>
                        <td style={TD}>{r.level}</td>
                        <td style={TD}>#{r.rank}</td>
                        <td style={TD}>{r.time}</td>
                        {showMedals && <td style={TD}><MedalBadge medal={r.medal} plain /></td>}
                        <td style={{ ...TD, color: "var(--text-3)" }}>
                          {r.total ? `/ ${r.total.toLocaleString()}` : ""}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {!running && rows.length > 0 && (() => {
                  const avgRank = Math.round(rows.reduce((s, r) => s + r.rank, 0) / rows.length);
                  return (
                    <div style={{
                      borderTop: "1px solid var(--border)",
                      padding: "8px 16px",
                      fontSize: largeText ? 13 : 11,
                      color: "var(--text-2)",
                    }}>
                      Average Placement: #{avgRank} across {rows.length} / {totalLevels} levels
                    </div>
                  );
                })()}
              </div>
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
