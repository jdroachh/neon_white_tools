import React, { useState, useEffect, useMemo } from "react";
import { PageHead, Field, Seg, Btn, ErrorBanner, MedalBadge, MedalToggle } from "../shared.jsx";
import { getLevels, getChapters, getSteamStatus, runComparePlayers, stopLeaderboard, pickFolder, getGlobalNeonRank } from "../api.js";
import { loadProfiles, saveProfiles, addProfile, isValidNewId } from "../lib/savedProfiles.js";
import SavedProfilesDropdown from "../components/SavedProfilesDropdown.jsx";
import LevelPickerModal from "../components/LevelPickerModal.jsx";
import { loadLevelsWithRetry, loadWithRetry } from "../lib/retryLevels.js";
import { loadLastSelection, saveLastSelection } from "../lib/customLevels.js";
import { useCrosshair } from "../lib/useCrosshair.js";

const TH = { padding: "4px 8px", fontWeight: 600, fontSize: "0.91em", borderBottom: "1px solid var(--border)", textAlign: "left" };
const TD = { padding: "3px 8px", fontSize: "1em" };

// Default sort direction per key. Column-header clicks use these on first hit;
// repeat clicks toggle. Lower-is-better stats default asc (rank, time);
// "delta" defaults desc so the most P1-favored levels surface first, matching
// the existing "P1 Lead" dropdown option.
const SORT_DEFAULTS = {
  level:        "asc",
  rank_best_p1: "asc",
  rank_best_p2: "asc",
  time_p1:      "asc",
  time_p2:      "asc",
  delta:        "desc",
  gap_closest:  "asc",
  medal_tier_p1: "asc",
  medal_tier_p2: "asc",
};
const P1_BG    = "rgba(80, 160, 255, 0.18)";
const P1_COLOR = "rgb(80, 160, 255)";
const P2_BG    = "rgba(255, 90, 90, 0.18)";
const P2_COLOR = "rgb(255, 90, 90)";

function formatDelta(delta_ms) {
  const secs = delta_ms / 1000;
  if (secs === 0) return "0.000";
  const sign = secs > 0 ? "+" : "−";
  return `${sign}${Math.abs(secs).toFixed(3)}`;
}

export default function ComparePlayers({ outputFolder: defaultFolder = "", visible = false }) {
  const [steamId1, setSteamId1]           = useState("");
  const [steamId2, setSteamId2]           = useState("");
  const [mode, setMode]                   = useState("level");
  const [levels, setLevels]               = useState([]);
  const [chapters, setChapters]           = useState([]);
  const [levelName, setLevelName]         = useState("");
  const [chapterName, setChapterName]     = useState("");
  const [outMode, setOutMode]             = useState("display");
  const [folder, setFolder]               = useState(defaultFolder);
  const [folderTouched, setFolderTouched] = useState(false);
  const [running, setRunning]             = useState(false);
  const [status, setStatus]               = useState("");
  const [error, setError]                 = useState("");
  const { tbodyProps, cellHL }            = useCrosshair();
  const [rows, setRows]                   = useState([]);
  const [playerName1, setPlayerName1]     = useState("");
  const [playerName2, setPlayerName2]     = useState("");
  const [showMedals, setShowMedals]       = useState(false);
  const [largeText, setLargeText]         = useState(false);
  const [savedProfiles, setSavedProfiles] = useState([]);
  const [sortKey, setSortKey]             = useState("level");
  const [sortDir, setSortDir]             = useState("asc");
  const [filterKey, setFilterKey]         = useState("all");
  const [neonRank1, setNeonRank1]         = useState(null);
  const [neonRank2, setNeonRank2]         = useState(null);
  const [mySteamId, setMySteamId]         = useState("");
  const [customLevels, setCustomLevels]   = useState([]);
  const [pickerOpen, setPickerOpen]       = useState(false);
  const customHydrated = React.useRef(false);

  // Whole-game mode: fetch each player's GlobalNeonRankings entry after the
  // compare finishes. Story-only — see project_global_neon_rankings.md.
  useEffect(() => {
    if (mode === "game" && !running && rows.length > 0 && steamId1 && neonRank1 === null) {
      getGlobalNeonRank(steamId1).then(setNeonRank1).catch(() => setNeonRank1({ ok: false }));
    }
    if (mode === "game" && !running && rows.length > 0 && steamId2 && neonRank2 === null) {
      getGlobalNeonRank(steamId2).then(setNeonRank2).catch(() => setNeonRank2({ ok: false }));
    }
  }, [running, mode, rows.length, steamId1, steamId2, neonRank1, neonRank2]);

  useEffect(() => {
    const cancelLevels = loadLevelsWithRetry(getLevels, {
      onLevels: ls => { setLevels(ls); setLevelName(ls[0].display); }
    });
    const cancelChapters = loadWithRetry(getChapters, {
      onData: cs => { setChapters(cs); setChapterName(cs[0].name); }
    });
    loadProfiles().then(setSavedProfiles);
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
    return () => { cancelLevels(); cancelChapters(); window._nwCompareEvent = null; };
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
      if (sortKey === "medal_tier_p1" || sortKey === "medal_tier_p2") { setSortKey("level"); setSortDir("asc"); }
      if (filterKey === "medal_mismatch") setFilterKey("all");
    }
  }, [showMedals]);

  // Hydrate the last-used custom selection the first time the user picks "custom".
  useEffect(() => {
    if (mode === "custom" && !customHydrated.current) {
      customHydrated.current = true;
      loadLastSelection("cp").then(setCustomLevels);
    }
  }, [mode]);

  function handleCustomLevelsChange(next) {
    setCustomLevels(next);
    saveLastSelection("cp", next);
  }

  // Header click: same key → toggle direction; new key → reset to its default.
  function applySort(key) {
    if (sortKey === key) {
      setSortDir(d => d === "asc" ? "desc" : "asc");
    } else {
      setSortKey(key);
      setSortDir(SORT_DEFAULTS[key] || "asc");
    }
  }

  // Bridge dropdown ↔ (sortKey, sortDir). The dropdown keeps its legacy option
  // values ("gap_p1_lead" / "gap_p2_lead"); internally those collapse to a
  // single "delta" key with direction. Other values pass through 1:1.
  const dropdownValue = sortKey === "delta"
    ? (sortDir === "desc" ? "gap_p1_lead" : "gap_p2_lead")
    : sortKey;
  function onDropdownSort(v) {
    if (v === "gap_p1_lead")      { setSortKey("delta"); setSortDir("desc"); }
    else if (v === "gap_p2_lead") { setSortKey("delta"); setSortDir("asc");  }
    else                          { setSortKey(v);       setSortDir(SORT_DEFAULTS[v] || "asc"); }
  }

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

  async function handlePickFolder() {
    const r = await pickFolder();
    if (r.ok && r.path) { setFolder(r.path); setFolderTouched(true); }
  }

  async function handleQuickSave(steamId, slot) {
    const nickname = window.prompt(`Save this profile\nSteam ID: ${steamId}\n\nEnter a nickname (1–24 chars):`);
    if (nickname === null) return;
    const result = addProfile(savedProfiles, { nickname, steam_id: steamId });
    if (result.error) { setError(result.error); return; }
    setSavedProfiles(result.list);
    await saveProfiles(result.list);
  }

  function handleLoadProfile(profile, slot) {
    if (slot === "p1") setSteamId1(profile.steam_id);
    else setSteamId2(profile.steam_id);
  }

  async function handleRun() {
    setError(""); setStatus(""); setRows([]); setPlayerName1(""); setPlayerName2("");
    setNeonRank1(null); setNeonRank2(null);
    setSortKey("level"); setFilterKey("all");
    const target = mode === "custom"  ? JSON.stringify(customLevels)
                 : mode === "level"   ? levelName
                 : mode === "chapter" ? chapterName
                 : "";
    const r = await runComparePlayers(steamId1, steamId2, mode, target, outMode, folder);
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

  const MEDAL_TIER_ORDER = ["BLOOD DIAMOND","TOPAZ","SAPPHIRE","AMETHYST","EMERALD","DEV","ACE","GOLD","SILVER","BRONZE"];

  const stats = useMemo(() => {
    if (!rows.length) return null;
    const bothPresent = rows.filter(r => r.p1 && r.p2);
    const p1Wins = rows.filter(r => r.faster === "p1").length;
    const p2Wins = rows.filter(r => r.faster === "p2").length;
    const ties = bothPresent.filter(r => r.faster !== "p1" && r.faster !== "p2").length;
    const missing = rows.filter(r => !r.p1 || !r.p2).length;
    const totalDeltaMs = bothPresent.reduce((s, r) => s + r.delta_ms, 0);
    const biggestLead = bothPresent.length
      ? bothPresent.reduce((best, r) => Math.abs(r.delta_ms) > Math.abs(best.delta_ms) ? r : best)
      : null;
    const closestGap = bothPresent.length
      ? bothPresent.reduce((best, r) => Math.abs(r.delta_ms) < Math.abs(best.delta_ms) ? r : best)
      : null;
    const p1Rows = rows.filter(r => r.p1);
    const p2Rows = rows.filter(r => r.p2);
    const bestP1 = p1Rows.length ? p1Rows.reduce((best, r) => r.p1.rank < best.p1.rank ? r : best) : null;
    const bestP2 = p2Rows.length ? p2Rows.reduce((best, r) => r.p2.rank < best.p2.rank ? r : best) : null;
    const p1MedalCounts = {};
    const p2MedalCounts = {};
    rows.forEach(r => {
      if (r.p1?.medal) p1MedalCounts[r.p1.medal] = (p1MedalCounts[r.p1.medal] || 0) + 1;
      if (r.p2?.medal) p2MedalCounts[r.p2.medal] = (p2MedalCounts[r.p2.medal] || 0) + 1;
    });
    return { p1Wins, p2Wins, ties, missing, totalDeltaMs, biggestLead, closestGap, bestP1, bestP2, p1MedalCounts, p2MedalCounts };
  }, [rows]);

  const displayRows = useMemo(() => {
    const filtered = rows.filter(r => {
      switch (filterKey) {
        case "p1_leads":       return r.faster === "p1";
        case "p2_leads":       return r.faster === "p2";
        case "gap_over_1s":    return r.delta_ms != null && Math.abs(r.delta_ms) > 1000;
        case "medal_mismatch": return r.p1 && r.p2 && r.p1.medal !== r.p2.medal;
        case "missing":        return !r.p1 || !r.p2;
        default:               return true;
      }
    });
    if (sortKey === "level") {
      return sortDir === "asc" ? filtered : [...filtered].reverse();
    }
    const sign = sortDir === "asc" ? 1 : -1;
    return [...filtered].sort((a, b) => {
      const aMissing = !a.p1 || !a.p2;
      const bMissing = !b.p1 || !b.p2;
      if (aMissing && bMissing) return 0;
      if (aMissing) return 1;   // missing rows always sink to the bottom
      if (bMissing) return -1;
      let cmp = 0;
      switch (sortKey) {
        case "rank_best_p1": cmp = a.p1.rank     - b.p1.rank;     break;
        case "rank_best_p2": cmp = a.p2.rank     - b.p2.rank;     break;
        case "time_p1":      cmp = a.p1.score_ms - b.p1.score_ms; break;
        case "time_p2":      cmp = a.p2.score_ms - b.p2.score_ms; break;
        case "delta":        cmp = a.delta_ms    - b.delta_ms;    break;
        case "gap_closest":  cmp = Math.abs(a.delta_ms) - Math.abs(b.delta_ms); break;
        case "medal_tier_p1": {
          const ai = MEDAL_TIER_ORDER.indexOf(a.p1?.medal); const bi = MEDAL_TIER_ORDER.indexOf(b.p1?.medal);
          cmp = (ai === -1 ? 99 : ai) - (bi === -1 ? 99 : bi);
          break;
        }
        case "medal_tier_p2": {
          const ai = MEDAL_TIER_ORDER.indexOf(a.p2?.medal); const bi = MEDAL_TIER_ORDER.indexOf(b.p2?.medal);
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
      <PageHead crumb={<>Leaderboard Tools <span style={{ color: "var(--text-3)", fontSize: "0.85em", fontWeight: 400 }}>· thanks Ferex!</span></>} title="COMPARE" accentWord="PLAYERS"
        actions={<>
          {rows.length > 0 && !running && outMode !== "csv" &&
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
                <SavedProfilesDropdown
                  profiles={savedProfiles}
                  onSelect={(p) => handleLoadProfile(p, "p1")}
                  disabled={running}
                />
                {isValidNewId(steamId1, savedProfiles) && steamId1 !== mySteamId && (
                  <Btn kind="ghost" size="sm" disabled={running}
                       title="Save this ID as a profile"
                       onClick={() => handleQuickSave(steamId1, "p1")}>★</Btn>
                )}
              </div>
            </Field>
            <Field label="Player 2 Steam ID" hint="17-digit number from the player's Steam profile URL.">
              <div style={{ display: "flex", gap: 8 }}>
                <input className="input" style={{ flex: 1 }} value={steamId2}
                       onChange={e => setSteamId2(e.target.value)}
                       placeholder="76561198..." disabled={running} />
                <Btn kind="ghost" size="sm" onClick={handleUseMine2} disabled={running}>Mine</Btn>
                <SavedProfilesDropdown
                  profiles={savedProfiles}
                  onSelect={(p) => handleLoadProfile(p, "p2")}
                  disabled={running}
                />
                {isValidNewId(steamId2, savedProfiles) && steamId2 !== mySteamId && (
                  <Btn kind="ghost" size="sm" disabled={running}
                       title="Save this ID as a profile"
                       onClick={() => handleQuickSave(steamId2, "p2")}>★</Btn>
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
            {mode === "game" && (
              <div className="muted" style={{ fontSize: 11 }}>
                All 121 levels will be searched.
              </div>
            )}
            <Field label="Output">
              <Seg options={["display", "csv", "both"]} value={outMode} onChange={setOutMode} />
            </Field>
            {(outMode === "csv" || outMode === "both") && (
              <Field label="Output folder" hint="Saved as P1_vs_P2_context.csv">
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
                       disabled={mode === "custom" && customLevels.length === 0}>Compare</Btn>}
            </div>
            {status && <div className="muted" style={{ fontSize: 11 }}>{status}</div>}
          </div>
        </div>
        <div className="panel-right" style={{ overflow: "auto", display: "flex", flexDirection: "column" }}>
          {outMode === "csv" ? (
            <div className="muted" style={{ padding: 32, fontSize: 12, textAlign: "center" }}>
              {running ? "Comparing and writing CSV..." : status || "Results will be saved to CSV only."}
            </div>
          ) : rows.length > 0 ? (
            <>
              {mode !== "level" && stats && (
                <div style={{
                  borderBottom: "1px solid var(--border)",
                  padding: "8px 16px 6px",
                  flexShrink: 0,
                }}>
                  {mode === "game" && (neonRank1 || neonRank2) && (
                    <div style={{ fontSize: 11, color: "var(--text-3)", lineHeight: 1.7, marginBottom: 2 }}>
                      Global rank:{" "}
                      <span style={{ color: P1_COLOR }}>{playerName1 || "P1"}</span>{" "}
                      <span style={{ color: "var(--text)" }}>
                        {neonRank1?.ok ? `#${neonRank1.rank.toLocaleString()}` : "—"}
                      </span>
                      {"  ·  "}
                      <span style={{ color: P2_COLOR }}>{playerName2 || "P2"}</span>{" "}
                      <span style={{ color: "var(--text)" }}>
                        {neonRank2?.ok ? `#${neonRank2.rank.toLocaleString()}` : "—"}
                      </span>
                      <span title="Steam stores story-level total only. The in-game 'Global Neon Rankings' adds Sidequest level times client-side per player, which is not Steam-queryable — so the rank may differ slightly from in-game."
                            style={{ color: "var(--accent)", cursor: "help", marginLeft: 2 }}>*</span>
                    </div>
                  )}
                  <div style={{ fontSize: 11, color: "var(--text-2)", lineHeight: 1.7 }}>
                    <span style={{ fontWeight: 600, color: "var(--text)" }}>{playerName1 || "Player 1"}</span>
                    {" "}{stats.p1Wins}–{stats.p2Wins}{" "}
                    <span style={{ fontWeight: 600, color: "var(--text)" }}>{playerName2 || "Player 2"}</span>
                    {"  ·  "}{formatDelta(stats.totalDeltaMs)}s total
                    {"  ·  "}{stats.ties} ties{"  ·  "}{stats.missing} missing
                  </div>
                  <div style={{ fontSize: 11, color: "var(--text-3)", lineHeight: 1.7 }}>
                    {stats.biggestLead && <>
                      Biggest lead:{" "}
                      <span style={{ color: "var(--text-2)" }}>
                        {stats.biggestLead.delta_ms < 0 ? (playerName1 || "P1") : (playerName2 || "P2")}
                        {" "}{stats.biggestLead.level}{" "}({formatDelta(stats.biggestLead.delta_ms)}s)
                      </span>
                    </>}
                    {stats.closestGap && <>
                      {"  ·  "}Closest:{" "}
                      <span style={{ color: "var(--text-2)" }}>
                        {stats.closestGap.level} (±{(Math.abs(stats.closestGap.delta_ms) / 1000).toFixed(3)}s)
                      </span>
                    </>}
                    {stats.bestP1 && <>
                      {"  ·  "}Best P1:{" "}
                      <span style={{ color: "var(--text-2)" }}>
                        {stats.bestP1.level} #{stats.bestP1.p1.rank}
                      </span>
                    </>}
                    {!stats.bestP1 && <>{"  ·  "}Best P1: <span style={{ color: "var(--text-2)" }}>—</span></>}
                    {stats.bestP2 && <>
                      {"  ·  "}Best P2:{" "}
                      <span style={{ color: "var(--text-2)" }}>
                        {stats.bestP2.level} #{stats.bestP2.p2.rank}
                      </span>
                    </>}
                    {!stats.bestP2 && <>{"  ·  "}Best P2: <span style={{ color: "var(--text-2)" }}>—</span></>}
                  </div>
                  {showMedals && (
                    <div style={{ marginTop: 4 }}>
                      {[
                        { label: playerName1 || "P1", counts: stats.p1MedalCounts },
                        { label: playerName2 || "P2", counts: stats.p2MedalCounts },
                      ].map(({ label, counts }) => (
                        <div key={label} style={{ display: "flex", alignItems: "center", flexWrap: "wrap", gap: "4px 8px", fontSize: 11, color: "var(--text-3)", marginTop: 2 }}>
                          <span style={{ color: "var(--text-3)", minWidth: 24 }}>{label}:</span>
                          {MEDAL_TIER_ORDER.some(t => counts[t])
                            ? MEDAL_TIER_ORDER.filter(t => counts[t]).map(t => (
                                <span key={t} style={{ display: "inline-flex", alignItems: "center", gap: 3 }}>
                                  <MedalBadge medal={t} />
                                  <span style={{ color: "var(--text-3)" }}>{counts[t]}</span>
                                </span>
                              ))
                            : <span>—</span>
                          }
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
              <div style={{ display: "flex", alignItems: "center", gap: 12, padding: "10px 16px 6px", flexShrink: 0 }}>
                <span style={{ fontSize: 12, fontWeight: 600, flex: 1 }}>
                  {playerName1 || "Player 1"} vs {playerName2 || "Player 2"}
                </span>
                <div style={{ display: "flex", alignItems: "center", gap: 12, marginLeft: "auto" }}>
                  {mode !== "level" && <>
                    <select className="input" value={dropdownValue} onChange={e => onDropdownSort(e.target.value)}
                            style={{ fontSize: 11 }}>
                      <option value="level">Sort: Level</option>
                      <option value="rank_best_p1">Sort: P1 Rank</option>
                      <option value="time_p1">Sort: P1 Time</option>
                      <option value="rank_best_p2">Sort: P2 Rank</option>
                      <option value="time_p2">Sort: P2 Time</option>
                      <option value="gap_p1_lead">Sort: P1 Lead</option>
                      <option value="gap_p2_lead">Sort: P2 Lead</option>
                      <option value="gap_closest">Sort: Closest</option>
                      {showMedals && <option value="medal_tier_p1">Sort: P1 Medal</option>}
                      {showMedals && <option value="medal_tier_p2">Sort: P2 Medal</option>}
                    </select>
                    <select className="input" value={filterKey} onChange={e => setFilterKey(e.target.value)}
                            style={{ fontSize: 11 }}>
                      <option value="all">Filter: All</option>
                      <option value="p1_leads">Filter: P1 Leads</option>
                      <option value="p2_leads">Filter: P2 Leads</option>
                      <option value="gap_over_1s">Filter: Gap &gt; 1s</option>
                      {showMedals && <option value="medal_mismatch">Filter: Medal Mismatch</option>}
                      <option value="missing">Filter: Missing</option>
                    </select>
                  </>}
                  <MedalToggle value={showMedals} onChange={setShowMedals} />
                  <Seg value={largeText ? "Large" : "Normal"} onChange={v => setLargeText(v === "Large")}
                       options={["Normal", "Large"]} />
                </div>
              </div>
              <div style={{ fontSize: largeText ? 14 : 11, overflow: "auto", flex: 1 }}>
                <table style={{ width: "100%", borderCollapse: "collapse", tableLayout: "fixed" }}>
                  {(() => {
                    // Column widths in em so they scale with largeText. Level
                    // column omits width → eats remaining space.
                    // Percentage widths so columns spread proportionally as the
                    // panel grows — no more "Level eats everything, numerics
                    // bunch on the right". Sums to 100 per medal-toggle state.
                    const cols = showMedals
                      ? [
                          { key: "level",        label: "Level",    width: "22%", align: "left"  },
                          { key: "rank_best_p1", label: "P1 Rank",  width: "10%", align: "right" },
                          { key: "time_p1",      label: "P1 Time",  width: "13%", align: "right" },
                          { key: "medal_tier_p1", label: "P1 Medal", width: "9%",  align: "left"  },
                          { key: "delta",        label: "Δ",        width: "14%", align: "right" },
                          { key: "medal_tier_p2", label: "P2 Medal", width: "9%",  align: "left"  },
                          { key: "time_p2",      label: "P2 Time",  width: "13%", align: "right" },
                          { key: "rank_best_p2", label: "P2 Rank",  width: "10%", align: "right" },
                        ]
                      : [
                          { key: "level",        label: "Level",   width: "30%", align: "left"  },
                          { key: "rank_best_p1", label: "P1 Rank", width: "12%", align: "right" },
                          { key: "time_p1",      label: "P1 Time", width: "15%", align: "right" },
                          { key: "delta",        label: "Δ",       width: "16%", align: "right" },
                          { key: "time_p2",      label: "P2 Time", width: "15%", align: "right" },
                          { key: "rank_best_p2", label: "P2 Rank", width: "12%", align: "right" },
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
                          const p1bg    = r.faster === "p1" ? P1_BG : undefined;
                          const p2bg    = r.faster === "p2" ? P2_BG : undefined;
                          const dColor  = r.faster === "p1" ? P1_COLOR : r.faster === "p2" ? P2_COLOR : undefined;
                          const delta   = r.delta_ms != null ? formatDelta(r.delta_ms) : "—";
                          const numTd   = { ...TD, textAlign: "right", whiteSpace: "nowrap" };
                          const lvlTd   = { ...TD, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" };
                          // DOM column indices (shift when the medal cols show).
                          const c = showMedals
                            ? { level: 0, p1rank: 1, p1time: 2, p1medal: 3, delta: 4, p2medal: 5, p2time: 6, p2rank: 7 }
                            : { level: 0, p1rank: 1, p1time: 2, delta: 3, p2time: 4, p2rank: 5 };
                          return (
                            <tr key={r.level} data-row={i} style={{ borderBottom: "1px solid var(--border)" }}>
                              <td style={{ ...lvlTd, ...cellHL(i, c.level) }} title={r.level}>{r.level}</td>
                              <td style={{ ...numTd, ...cellHL(i, c.p1rank) }}>{r.p1 ? `#${r.p1.rank}` : "—"}</td>
                              <td style={{ ...numTd, backgroundColor: p1bg, ...cellHL(i, c.p1time) }}>{r.p1 ? r.p1.time : "—"}</td>
                              {showMedals && <td style={{ ...TD, ...cellHL(i, c.p1medal) }}>{r.p1 ? <MedalBadge medal={r.p1.medal} plain /> : "—"}</td>}
                              <td style={{ ...numTd, color: dColor, ...cellHL(i, c.delta) }}>{delta}</td>
                              {showMedals && <td style={{ ...TD, ...cellHL(i, c.p2medal) }}>{r.p2 ? <MedalBadge medal={r.p2.medal} plain /> : "—"}</td>}
                              <td style={{ ...numTd, backgroundColor: p2bg, ...cellHL(i, c.p2time) }}>{r.p2 ? r.p2.time : "—"}</td>
                              <td style={{ ...numTd, ...cellHL(i, c.p2rank) }}>{r.p2 ? `#${r.p2.rank}` : "—"}</td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </>;
                  })()}
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
      <LevelPickerModal
        open={pickerOpen} onClose={() => setPickerOpen(false)}
        value={customLevels} onChange={handleCustomLevelsChange}
        levels={levels} chapters={chapters}
      />
    </>
  );
}
