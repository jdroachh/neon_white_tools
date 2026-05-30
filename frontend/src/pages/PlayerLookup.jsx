import React, { useState, useEffect, useMemo } from "react";
import { PageHead, Field, Seg, Btn, ErrorBanner, MedalBadge, MedalToggle } from "../shared.jsx";
import { getLevels, getChapters, getSteamStatus, runPlayerLookup, stopLeaderboard, pickFolder, getGlobalNeonRank } from "../api.js";
import { loadLevelsWithRetry } from "../lib/retryLevels.js";
import { loadProfiles, saveProfiles, addProfile, isValidNewId } from "../lib/savedProfiles.js";
import { loadLastSelection, saveLastSelection } from "../lib/customLevels.js";
import SavedProfilesDropdown from "../components/SavedProfilesDropdown.jsx";
import LevelPickerModal from "../components/LevelPickerModal.jsx";
import { useCrosshair } from "../lib/useCrosshair.js";

const TH = { padding: "4px 8px", fontWeight: 600, fontSize: "0.91em", borderBottom: "1px solid var(--border)", textAlign: "left" };
const TD = { padding: "3px 8px", fontSize: "1em" };

// Default sort direction per key — matches the CP convention.
const SORT_DEFAULTS = {
  level:      "asc",
  rank:       "asc",
  time:       "asc",
  medal_tier: "asc",
};

export default function PlayerLookup({ outputFolder: defaultFolder = "", visible = false }) {
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
  const { tbodyProps, cellHL }        = useCrosshair();
  const [rows, setRows]               = useState([]);
  const [playerName, setPlayerName]   = useState("");
  const [showMedals, setShowMedals]   = useState(false);
  const [largeText, setLargeText]     = useState(false);
  const [totalLevels, setTotalLevels] = useState(0);
  const [sortKey, setSortKey]         = useState("level");
  const [sortDir, setSortDir]         = useState("asc");
  const [filterKey, setFilterKey]     = useState("all");
  const [savedProfiles, setSavedProfiles] = useState([]);
  const [neonRank, setNeonRank]       = useState(null);
  const [mySteamId, setMySteamId]     = useState("");
  const [customLevels, setCustomLevels] = useState([]);
  const [pickerOpen, setPickerOpen]   = useState(false);
  const customHydrated = React.useRef(false);

  useEffect(() => {
    const cancelLevels = loadLevelsWithRetry(getLevels, {
      onLevels: ls => { setLevels(ls); setLevelName(ls[0].display); }
    });
    getChapters().then(cs => { setChapters(cs); if (cs.length) setChapterName(cs[0].name); });
    loadProfiles().then(setSavedProfiles);
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
    if (visible) {
      loadProfiles().then(setSavedProfiles);
      getSteamStatus().then(s => {
        setMySteamId(s.ready && s.steam_id ? String(s.steam_id) : "");
      }).catch(() => {});
    }
  }, [visible]);

  useEffect(() => {
    if (!folderTouched) setFolder(defaultFolder);
  }, [defaultFolder]);

  useEffect(() => {
    if (!showMedals) {
      if (sortKey === "medal_tier") { setSortKey("level"); setSortDir("asc"); }
      if (filterKey === "community_medal") setFilterKey("all");
    }
  }, [showMedals]);

  // Hydrate the last-used custom selection the first time the user picks "custom".
  useEffect(() => {
    if (mode === "custom" && !customHydrated.current) {
      customHydrated.current = true;
      loadLastSelection("pl").then(setCustomLevels);
    }
  }, [mode]);

  function handleCustomLevelsChange(next) {
    setCustomLevels(next);
    saveLastSelection("pl", next);
  }

  // Header click: same column → toggle direction; new column → reset to default.
  function applySort(key) {
    if (sortKey === key) {
      setSortDir(d => d === "asc" ? "desc" : "asc");
    } else {
      setSortKey(key);
      setSortDir(SORT_DEFAULTS[key] || "asc");
    }
  }
  // Dropdown change: reset direction to the new key's default.
  function onDropdownSort(v) {
    setSortKey(v);
    setSortDir(SORT_DEFAULTS[v] || "asc");
  }

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

  async function handleQuickSave(id) {
    const nickname = window.prompt(`Save this profile\nSteam ID: ${id}\n\nEnter a nickname (1–24 chars):`);
    if (nickname === null) return;
    const result = addProfile(savedProfiles, { nickname, steam_id: id });
    if (result.error) { setError(result.error); return; }
    setSavedProfiles(result.list);
    await saveProfiles(result.list);
  }

  function handleLoadProfile(profile) {
    setSteamId(profile.steam_id);
  }

  async function handleRun() {
    setError(""); setStatus(""); setRows([]); setPlayerName(""); setTotalLevels(0);
    setSortKey("level"); setFilterKey("all"); setNeonRank(null);
    const target = mode === "custom"  ? JSON.stringify(customLevels)
                 : mode === "level"   ? levelName
                 : mode === "chapter" ? chapterName
                 : "";
    const r = await runPlayerLookup(steamId, mode, target, outMode, folder);
    if (!r.ok) { setError(r.error); return; }
    setRunning(true);
  }

  // After a whole-game lookup finishes, fetch the player's GlobalNeonRankings
  // entry. Story-only — in-game total adds Sidequest client-side (see project memory).
  // Fired post-completion to avoid two threads sharing SteamAPI_RunCallbacks.
  useEffect(() => {
    if (mode === "game" && !running && rows.length > 0 && steamId && neonRank === null) {
      getGlobalNeonRank(steamId).then(setNeonRank).catch(() => setNeonRank({ ok: false }));
    }
  }, [running, mode, rows.length, steamId, neonRank]);

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
    if (sortKey === "level") {
      return sortDir === "asc" ? filtered : [...filtered].reverse();
    }
    const sign = sortDir === "asc" ? 1 : -1;
    return [...filtered].sort((a, b) => {
      let cmp = 0;
      switch (sortKey) {
        case "rank":       cmp = a.rank - b.rank; break;
        case "time":       cmp = (a.score_ms || 0) - (b.score_ms || 0); break;
        case "medal_tier": {
          const ai = MEDAL_TIER_ORDER.indexOf(a.medal); const bi = MEDAL_TIER_ORDER.indexOf(b.medal);
          cmp = (ai === -1 ? 99 : ai) - (bi === -1 ? 99 : bi);
          break;
        }
        default: return 0;
      }
      return sign * cmp;
    });
  }, [rows, sortKey, sortDir, filterKey]);

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
                <SavedProfilesDropdown
                  profiles={savedProfiles}
                  onSelect={handleLoadProfile}
                  disabled={running}
                />
                {isValidNewId(steamId, savedProfiles) && steamId !== mySteamId && (
                  <Btn kind="ghost" size="sm" disabled={running}
                       title="Save this ID as a profile"
                       onClick={() => handleQuickSave(steamId)}>★</Btn>
                )}
              </div>
            </Field>
            <Field label="Search mode">
              <Seg options={["level", "chapter", "game", "custom"]} value={mode}
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
            {mode === "custom" && (
              <Field label="Custom level set">
                <div style={{ display: "flex", gap: 8 }}>
                  <Btn kind="ghost" size="sm" onClick={() => setPickerOpen(true)} disabled={running}>
                    {customLevels.length ? `${customLevels.length} levels selected` : "Pick levels…"}
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
                : <Btn kind="primary" size="lg" icn="user" onClick={handleRun}
                       disabled={mode === "custom" && customLevels.length === 0}>Look Up</Btn>}
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
                  {mode === "game" && neonRank && (
                    <div style={{ fontSize: 11, color: "var(--text-3)", lineHeight: 1.7 }}>
                      Global rank:{" "}
                      {neonRank.ok ? (
                        <>
                          <span style={{ color: "var(--text)" }}>#{neonRank.rank.toLocaleString()}</span>
                          <span title="Steam stores story-level total only. The in-game 'Global Neon Rankings' adds Sidequest level times client-side per player, which is not Steam-queryable — so the rank may differ slightly from in-game."
                                style={{ color: "var(--accent)", cursor: "help", marginLeft: 2 }}>*</span>
                        </>
                      ) : (
                        <span style={{ color: "var(--text-3)" }}>— (no entry on Global Rankings)</span>
                      )}
                    </div>
                  )}
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
                    <select className="input" value={sortKey} onChange={e => onDropdownSort(e.target.value)}
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
                <table style={{ width: "100%", borderCollapse: "collapse", tableLayout: "fixed" }}>
                  {(() => {
                    // Percentage widths so columns spread evenly. "/ Total" is
                    // not sortable. Sortable: rank, time, medal_tier.
                    const cols = showMedals
                      ? [
                          { key: "level",      label: "Level",   width: "32%", align: "left"  },
                          { key: "rank",       label: "Rank",    width: "13%", align: "right" },
                          { key: "time",       label: "Time",    width: "16%", align: "right" },
                          { key: "medal_tier", label: "Medal",   width: "13%", align: "left"  },
                          { key: null,         label: "/ Total", width: "16%", align: "right" },
                        ]
                      : [
                          { key: "level",      label: "Level",   width: "38%", align: "left"  },
                          { key: "rank",       label: "Rank",    width: "16%", align: "right" },
                          { key: "time",       label: "Time",    width: "20%", align: "right" },
                          { key: null,         label: "/ Total", width: "20%", align: "right" },
                        ];
                    return <>
                      <colgroup>
                        {cols.map((c, i) => (
                          <col key={i} style={c.width ? { width: c.width } : undefined} />
                        ))}
                      </colgroup>
                      <thead style={{ position: "sticky", top: 0, background: "var(--bg-2)" }}>
                        <tr>
                          {cols.map((h, i) => {
                            const baseTh = { ...TH, textAlign: h.align };
                            if (mode === "level" || h.key == null) {
                              return <th key={i} style={baseTh}>{h.label}</th>;
                            }
                            const active = sortKey === h.key;
                            const arrow  = active ? (sortDir === "asc" ? " ▲" : " ▼") : "";
                            return (
                              <th key={i}
                                  style={{ ...baseTh, cursor: "pointer", userSelect: "none",
                                           color: active ? "var(--accent)" : undefined,
                                           whiteSpace: "nowrap" }}
                                  title={active ? "Click to reverse" : "Click to sort by " + h.label}
                                  onClick={() => applySort(h.key)}>
                                {h.label}{arrow}
                              </th>
                            );
                          })}
                        </tr>
                      </thead>
                      <tbody {...tbodyProps}>
                        {displayRows.map((r, i) => {
                          const numTd = { ...TD, textAlign: "right", whiteSpace: "nowrap" };
                          const lvlTd = { ...TD, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" };
                          // DOM column indices (shift when the medal col shows).
                          const c = showMedals
                            ? { level: 0, rank: 1, time: 2, medal: 3, total: 4 }
                            : { level: 0, rank: 1, time: 2, total: 3 };
                          return (
                            <tr key={r.level} data-row={i} style={{ borderBottom: "1px solid var(--border)" }}>
                              <td style={{ ...lvlTd, ...cellHL(i, c.level) }} title={r.level}>{r.level}</td>
                              <td style={{ ...numTd, ...cellHL(i, c.rank) }}>#{r.rank}</td>
                              <td style={{ ...numTd, ...cellHL(i, c.time) }}>{r.time}</td>
                              {showMedals && <td style={{ ...TD, ...cellHL(i, c.medal) }}><MedalBadge medal={r.medal} plain /></td>}
                              <td style={{ ...numTd, color: "var(--text-3)", ...cellHL(i, c.total) }}>
                                {r.total ? `/ ${r.total.toLocaleString()}` : ""}
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </>;
                  })()}
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
      <LevelPickerModal
        open={pickerOpen} onClose={() => setPickerOpen(false)}
        value={customLevels} onChange={handleCustomLevelsChange}
        levels={levels} chapters={chapters}
      />
    </>
  );
}
