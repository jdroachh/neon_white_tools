import React, { useState, useEffect, useRef, useMemo } from "react";

import { MedalBadge, Seg, PageHead, Btn, MedalToggle } from "../shared.jsx";
import { loadProfiles } from "../lib/savedProfiles.js";
import SavedProfilesDropdown from "../components/SavedProfilesDropdown.jsx";
import LevelPickerModal from "../components/LevelPickerModal.jsx";
import { loadLastSelection, saveLastSelection } from "../lib/customLevels.js";
import { loadWithRetry } from "../lib/retryLevels.js";
import {
  loadRosters, saveRosters, addRoster, removeRoster, MAX as MAX_ROSTERS,
} from "../lib/savedRosters.js";
import { PLAYER_COLORS, hexFor, nextAvailableColor } from "../lib/playerColors.js";
import { getLevels, getChapters, getSteamStatus, runMultiCompare, stopMultiCompare, clearMultiCompareCache, getGlobalNeonRank, saveTextFile } from "../api.js";

const STEAM_ID_RE = /^\d{17}$/;
const MEDAL_TIER_ORDER = ["BLOOD DIAMOND","TOPAZ","SAPPHIRE","AMETHYST","EMERALD","DEV","ACE","GOLD","SILVER","BRONZE"];
const MIN_ROWS = 1;
const DEFAULT_ROWS = 3;
const MAX_ROWS = 16;

// ── Icons (verbatim from handoff multi-compare.jsx) ──────────────────────
function McIcon({ name, size = 14 }) {
  const s = { width: size, height: size, display: "inline-block", verticalAlign: "middle" };
  const sp = { fill: "none", stroke: "currentColor", strokeWidth: 1.6, strokeLinecap: "round", strokeLinejoin: "round" };
  switch (name) {
    case "export":   return <svg viewBox="0 0 16 16" style={s}><g {...sp}><path d="M8 11V2"/><path d="M5 5l3-3 3 3"/><path d="M3 11v3h10v-3"/></g></svg>;
    case "run":      return <svg viewBox="0 0 16 16" style={s}><g {...sp}><path d="M9 2.5l-2 4h3l-2 4M5 11l-1.5 2M11 11l-1 2"/></g></svg>;
    case "caret":    return <svg viewBox="0 0 16 16" style={s}><path d="M5 6l3 3 3-3" {...sp} /></svg>;
    case "close":    return <svg viewBox="0 0 16 16" style={s}><path d="M3 3l10 10M13 3l-10 10" {...sp} strokeWidth="1.4"/></svg>;
    case "copy":     return <svg viewBox="0 0 16 16" style={s}><g {...sp}><rect x="5" y="5" width="9" height="9"/><path d="M3 11V3a1 1 0 011-1h7"/></g></svg>;
    case "ghost":    return <svg viewBox="0 0 16 16" style={s}><g {...sp}><path d="M3 13V8a5 5 0 0110 0v5l-1.5-1L10 13l-2-1-2 1-1.5-1L3 13z"/></g></svg>;
    case "video":    return <svg viewBox="0 0 16 16" style={s}><g {...sp}><rect x="2" y="4" width="9" height="8" rx="1"/><path d="M11 7l3-2v6l-3-2z"/></g></svg>;
    default: return null;
  }
}

// ── Helpers ───────────────────────────────────────────────────────────────
function formatTimeUs(us) {
  if (us == null) return "—";
  const totalSec = us / 1_000_000;
  const min = Math.floor(totalSec / 60);
  const sec = totalSec - min * 60;
  if (min > 0) return `${min}:${sec.toFixed(3).padStart(6, "0")}`;
  return `${sec.toFixed(3)}s`;
}
function formatGapUs(deltaUs) {
  if (deltaUs == null) return "—";
  if (deltaUs === 0) return "tie";
  const totalSec = deltaUs / 1_000_000;
  const min = Math.floor(totalSec / 60);
  const sec = totalSec - min * 60;
  if (min > 0) return `+${min}:${sec.toFixed(3).padStart(6, "0")}`;
  return `+${sec.toFixed(3)}s`;
}
function deriveInitial(name) {
  return (name || "").trim().charAt(0).toUpperCase();
}
function truncateSid(sid) {
  if (!sid || sid.length < 8) return sid || "";
  return `${sid.slice(0, 4)}…${sid.slice(-4)}`;
}
function chapterShortLabel(key) {
  const [head, tail] = (key || "").split(/\s*-\s*/, 2);
  if (/^\d+$/.test(head)) return `CH ${head}`;
  if ((head || "").toLowerCase().startsWith("sidequest")) return (tail || "").trim().toUpperCase();
  return key || "";
}
function makeEmptyRow(usedColors, rowIndex) {
  const playerNum = (rowIndex ?? usedColors.length) + 1;
  return {
    color: nextAvailableColor(usedColors),
    name: `Player ${playerNum}`,
    initial: String(playerNum),
    steam_id: "",
  };
}
// ── Main page ────────────────────────────────────────────────────────────
export default function MultiCompare({ visible = false, showMedals = true, setShowMedals } = {}) {
  const [roster, setRoster] = useState(() => {
    const rows = [];
    for (let i = 0; i < DEFAULT_ROWS; i++) rows.push(makeEmptyRow(rows.map(r => r.color), i));
    return rows;
  });

  const [levels, setLevels] = useState([]);
  const [chapters, setChapters] = useState({});  // {chapterKey: [displayNames]}
  const [savedProfiles, setSavedProfiles] = useState([]);
  const [savedRosters, setSavedRosters] = useState([]);

  const [savePromptOpen, setSavePromptOpen] = useState(false);
  const [savePromptNickname, setSavePromptNickname] = useState("");
  const [savePromptError, setSavePromptError] = useState("");

  const [mode, setMode] = useState("game");
  const [levelTarget, setLevelTarget] = useState("");
  const [chapterTarget, setChapterTarget] = useState("");
  const [running, setRunning] = useState(false);
  const [runError, setRunError] = useState("");
  const [progress, setProgress] = useState({ done: 0, total: 0 });
  const [results, setResults] = useState({});
  const [rosterEditing, setRosterEditing] = useState(true);  // expand-to-edit default open until first run
  // Collapse state for the roster pills row + the three summary strips. Plain
  // useState, expanded by default, reset each app launch (MC is permanently
  // mounted, so these survive page nav / mode switch within a session).
  const [rosterCollapsed, setRosterCollapsed] = useState(false);
  const [standingsCollapsed, setStandingsCollapsed] = useState(false);
  const [medalsCollapsed, setMedalsCollapsed] = useState(false);
  const [ranksCollapsed, setRanksCollapsed] = useState(false);
  const [drill, setDrill] = useState(null);  // {chapterKey, levelDisplay, cellKey} | null
  const [filterPlayer, setFilterPlayer] = useState(null);  // steam_id | null
  const [sortMode, setSortMode] = useState("chapter");  // chapter | most contested | biggest Δ
  const [neonRanks, setNeonRanks] = useState({});  // sid -> {ok, rank, score_ms, time}
  const [customLevels, setCustomLevels] = useState([]);  // display names
  const [pickerOpen, setPickerOpen] = useState(false);
  const customHydrated = useRef(false);

  const runIdRef = useRef(0);

  // ── Initial bridge load ─────────────────────────────────────────────────
  useEffect(() => {
    // Levels + chapters can lose the first-boot bridge race (empty/rejected on
    // the very first call past waitForApi), same as Compare Players / Player
    // Lookup — so retry them. getChapters returns [{name, levels}]; rebuild the
    // {name: levels} dict and seed the default targets only if still unset.
    const cancelLevels = loadWithRetry(getLevels, {
      onData: lv => {
        setLevels(lv);
        setLevelTarget(prev => prev || lv[0].display);
      },
    });
    const cancelChapters = loadWithRetry(getChapters, {
      onData: ch => {
        const chDict = {};
        for (const c of ch) chDict[c.name] = c.levels;
        setChapters(chDict);
        const chKeys = Object.keys(chDict);
        setChapterTarget(prev => prev || (chKeys.length ? chKeys[0] : prev));
      },
    });
    // Saved profiles/rosters are local config reads (no bridge race); plain load,
    // and the `visible` effect below reloads them on tab focus anyway.
    loadProfiles().then(setSavedProfiles).catch(() => {});
    loadRosters().then(setSavedRosters).catch(() => {});
    return () => { cancelLevels(); cancelChapters(); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!visible) return;
    loadProfiles().then(setSavedProfiles).catch(() => {});
    loadRosters().then(setSavedRosters).catch(() => {});
  }, [visible]);

  // ── Event listener ──────────────────────────────────────────────────────
  useEffect(() => {
    window._nwMultiCompareEvent = (evt) => {
      if (!evt || typeof evt !== "object") return;
      if (evt.type === "row") {
        const key = `${evt.steam_id}::${evt.level_code}`;
        setResults(prev => ({ ...prev, [key]: evt }));
      } else if (evt.type === "progress") {
        setProgress({ done: evt.done, total: evt.total });
      } else if (evt.type === "done") {
        setRunning(false);
        if (evt.message === "ok") setRosterEditing(false);
      }
    };
    return () => { delete window._nwMultiCompareEvent; };
  }, []);

  // ── Roster mutations ────────────────────────────────────────────────────
  function updateRow(idx, patch) {
    setRoster(prev => prev.map((r, i) => (i === idx ? { ...r, ...patch } : r)));
  }
  function addRow() {
    if (roster.length >= MAX_ROWS) return;
    setRoster(prev => [...prev, makeEmptyRow(prev.map(r => r.color), prev.length)]);
  }
  function removeRow(idx) {
    if (roster.length <= MIN_ROWS) return;
    setRoster(prev => prev.filter((_, i) => i !== idx));
  }
  function applyProfileToRow(idx, profile) {
    updateRow(idx, {
      name: profile.nickname || "",
      initial: deriveInitial(profile.nickname),
      steam_id: profile.steam_id || "",
    });
  }
  async function handleUseMine(idx) {
    const s = await getSteamStatus();
    if (s.ready && s.steam_id) {
      const patch = { steam_id: String(s.steam_id) };
      if (s.player_name) {
        patch.name = s.player_name;
        patch.initial = deriveInitial(s.player_name);
      }
      updateRow(idx, patch);
    } else {
      window.alert("Steam not connected. Connect in Settings first.");
    }
  }

  // ── Validity ─────────────────────────────────────────────────────────────
  const idCounts = useMemo(() => {
    const counts = {};
    for (const r of roster) {
      const id = (r.steam_id || "").trim();
      if (id) counts[id] = (counts[id] || 0) + 1;
    }
    return counts;
  }, [roster]);
  const validRoster = useMemo(
    () => roster.filter(r => {
      const id = (r.steam_id || "").trim();
      return STEAM_ID_RE.test(id) && idCounts[id] === 1;
    }),
    [roster, idCounts]
  );
  const canRun = !running && validRoster.length >= 1 && (
    mode === "game" ||
    (mode === "level" && !!levelTarget) ||
    (mode === "chapter" && !!chapterTarget) ||
    (mode === "custom" && customLevels.length > 0)
  );

  // ── Global Neon Rankings fetch (whole-game mode only) ──────────────────
  // Fired post-completion, sequentially per player. Story-only — see
  // project_global_neon_rankings.md. Sequential to avoid two concurrent
  // SteamAPI_RunCallbacks pumps from overlapping calls.
  useEffect(() => {
    if (mode !== "game" || running) return;
    if (Object.keys(results).length === 0) return;
    const pending = validRoster.filter(r => !(r.steam_id in neonRanks));
    if (pending.length === 0) return;
    let cancelled = false;
    (async () => {
      for (const r of pending) {
        if (cancelled) return;
        const sid = r.steam_id;
        try {
          const result = await getGlobalNeonRank(sid);
          if (cancelled) return;
          setNeonRanks(prev => ({ ...prev, [sid]: result }));
        } catch {
          if (cancelled) return;
          setNeonRanks(prev => ({ ...prev, [sid]: { ok: false } }));
        }
      }
    })();
    return () => { cancelled = true; };
  }, [running, mode, results, validRoster, neonRanks]);

  // Hydrate the last-used custom selection the first time the user picks "custom".
  useEffect(() => {
    if (mode === "custom" && !customHydrated.current) {
      customHydrated.current = true;
      loadLastSelection("mc").then(setCustomLevels);
    }
  }, [mode]);

  function handleCustomLevelsChange(next) {
    setCustomLevels(next);
    saveLastSelection("mc", next);
  }

  // chapters is a {name: [levels]} dict here; the modal wants [{name, levels}].
  const chaptersList = useMemo(
    () => Object.entries(chapters).map(([name, lv]) => ({ name, levels: lv })),
    [chapters]
  );
  // In custom mode, the set of picked levels that should stay active on the map.
  const customScope = useMemo(
    () => (mode === "custom" ? new Set(customLevels) : null),
    [mode, customLevels]
  );

  // Active scope for the summary strips (standings / medals / level count).
  // `null` = whole game (no filter). Mode-switching never clears `results`, so
  // the cached per-level data already covers every mode — we just re-scope the
  // aggregations below instead of re-querying Steam.
  const scopeSet = useMemo(() => {
    if (mode === "custom")  return new Set(customLevels);
    if (mode === "level")   return new Set(levelTarget ? [levelTarget] : []);
    if (mode === "chapter") return new Set(chapters[chapterTarget] || []);
    return null;  // game
  }, [mode, customLevels, levelTarget, chapterTarget, chapters]);
  const inScope = (disp) => !scopeSet || scopeSet.has(disp);

  function handleRun() {
    if (!canRun) return;
    setResults({});
    setRunError("");
    setProgress({ done: 0, total: 0 });
    setDrill(null);
    setFilterPlayer(null);
    setNeonRanks({});
    runIdRef.current += 1;
    setRunning(true);
    const steam_ids = validRoster.map(r => r.steam_id.trim());
    const target = mode === "custom"  ? JSON.stringify(customLevels)
                 : mode === "level"   ? levelTarget
                 : mode === "chapter" ? chapterTarget
                 : "";
    runMultiCompare(steam_ids, mode, target).then(res => {
      if (!res.ok) {
        console.error("[multi-compare] run failed:", res.error);
        setRunError(res.error || "Run failed.");
        setRunning(false);
      }
    }).catch(err => {
      console.error("[multi-compare] run threw:", err);
      setRunError("Run failed.");
      setRunning(false);
    });
  }
  function handleStop() { stopMultiCompare(); }

  // Refresh: keep the roster, drop its cached times, and re-run so the query
  // hits Steam fresh. Only meaningful once a run has produced results.
  async function handleRefresh() {
    if (!canRun || !anyResults) return;
    const steam_ids = validRoster.map(r => r.steam_id.trim());
    await clearMultiCompareCache(steam_ids);
    handleRun();
  }

  function openSavePrompt() {
    setSavePromptNickname(""); setSavePromptError(""); setSavePromptOpen(true);
  }
  function closeSavePrompt() { setSavePromptOpen(false); setSavePromptError(""); }
  function handleSaveRosterSubmit() {
    if (validRoster.length === 0) return;
    const members = validRoster.map(r => ({
      color: r.color, name: r.name, initial: r.initial, steam_id: r.steam_id.trim(),
    }));
    const { error, list } = addRoster(savedRosters, { nickname: savePromptNickname, members });
    if (error) { setSavePromptError(error); return; }
    setSavedRosters(list);
    saveRosters(list).catch(() => {});
    closeSavePrompt();
  }
  function handleLoadSavedRoster(idx) {
    const sr = savedRosters[idx];
    if (!sr || !Array.isArray(sr.members) || sr.members.length === 0) return;
    // Rosters saved elsewhere (e.g. Average Placement) carry no color field, so
    // auto-assign a distinct palette color per member instead of defaulting them
    // all to white. Members with a stored color keep it.
    const restored = [];
    for (const m of sr.members.slice(0, MAX_ROWS)) {
      const color = m.color || nextAvailableColor(restored.map(r => r.color));
      restored.push({ color, name: m.name || "", initial: m.initial || "", steam_id: m.steam_id || "" });
    }
    setRoster(restored);
    setRosterEditing(true);
    setResults({});
    setProgress({ done: 0, total: 0 });
    setDrill(null);
  }
  function handleDeleteSavedRoster(idx) {
    const next = removeRoster(savedRosters, idx);
    setSavedRosters(next);
    saveRosters(next).catch(() => {});
  }

  // ── Derived data ────────────────────────────────────────────────────────
  const rosterById = useMemo(() => {
    const m = {};
    for (const r of roster) {
      const id = (r.steam_id || "").trim();
      if (id) m[id] = r;
    }
    return m;
  }, [roster]);

  const chapterKeys = useMemo(() => Object.keys(chapters), [chapters]);

  // Aggregates per (chapterKey, levelDisplay):
  //   { winnerSid, winnerTime, winnerDelta, sortedRows[], rowsBySid{}, totalRosterRows, anyData }
  const mcData = useMemo(() => {
    const out = {};
    const rosterSids = Object.keys(rosterById);
    for (const ck of chapterKeys) {
      const levelDisplays = chapters[ck] || [];
      out[ck] = levelDisplays.map(disp => {
        // results are keyed by `${steam_id}::${level_code}`; match by level_display.
        const matching = Object.values(results).filter(r =>
          r.level_display === disp && rosterSids.includes(r.steam_id)
        );
        const present = matching.filter(r => !r.missing).slice().sort((a, b) => a.time_us - b.time_us);
        const winner = present.length ? present[0] : null;
        const second = present.length > 1 ? present[1] : null;
        const rowsBySid = {};
        for (const m of matching) rowsBySid[m.steam_id] = m;
        return {
          levelDisplay: disp,
          winnerSid: winner ? winner.steam_id : null,
          winnerTime: winner ? winner.time_us : null,
          winnerDelta: (winner && second) ? (second.time_us - winner.time_us) : null,
          sortedRows: present,
          missingRows: matching.filter(r => r.missing),
          rowsBySid,
          hasAnyData: matching.length > 0 && matching.some(r => !r.missing),
        };
      });
    }
    return out;
  }, [chapters, chapterKeys, results, rosterById]);

  // Wins per player (global) and per chapter
  const { winsPerPlayer, winsPerChapter, totalLevels } = useMemo(() => {
    const per = {};
    for (const sid of Object.keys(rosterById)) per[sid] = 0;
    const perChapter = {};
    let total = 0;
    for (const ck of chapterKeys) {
      const chWins = {};
      for (const sid of Object.keys(rosterById)) chWins[sid] = 0;
      for (const lvl of mcData[ck] || []) {
        if (!inScope(lvl.levelDisplay)) continue;
        total++;
        if (lvl.winnerSid) {
          per[lvl.winnerSid] = (per[lvl.winnerSid] || 0) + 1;
          chWins[lvl.winnerSid] = (chWins[lvl.winnerSid] || 0) + 1;
        }
      }
      perChapter[ck] = chWins;
    }
    return { winsPerPlayer: per, winsPerChapter: perChapter, totalLevels: total };
  }, [chapterKeys, mcData, rosterById, scopeSet]);

  // Medal counts per player — keyed by sid, then by medal tier.
  // Only counts rows in the current results scope (chapter/game/level mode handled
  // upstream by mcData composition).
  const medalsPerPlayer = useMemo(() => {
    const out = {};
    for (const sid of Object.keys(rosterById)) out[sid] = {};
    for (const ck of chapterKeys) {
      for (const lvl of mcData[ck] || []) {
        if (!inScope(lvl.levelDisplay)) continue;
        for (const row of lvl.sortedRows) {
          if (row.medal && out[row.steam_id]) {
            out[row.steam_id][row.medal] = (out[row.steam_id][row.medal] || 0) + 1;
          }
        }
      }
    }
    return out;
  }, [chapterKeys, mcData, rosterById, scopeSet]);

  // Sorted chapter order based on sortMode
  const sortedChapterKeys = useMemo(() => {
    if (sortMode === "chapter") return chapterKeys;
    if (sortMode === "most contested") {
      // Most-contested first: chapter where the most-winning player has the lowest share of wins.
      return [...chapterKeys].sort((a, b) => {
        const chA = winsPerChapter[a] || {}, chB = winsPerChapter[b] || {};
        const lenA = (chapters[a] || []).length || 1, lenB = (chapters[b] || []).length || 1;
        const maxA = Math.max(0, ...Object.values(chA)) / lenA;
        const maxB = Math.max(0, ...Object.values(chB)) / lenB;
        return maxA - maxB;
      });
    }
    if (sortMode === "biggest Δ") {
      return [...chapterKeys].sort((a, b) => {
        const dA = Math.max(0, ...((mcData[a] || []).map(l => l.winnerDelta || 0)));
        const dB = Math.max(0, ...((mcData[b] || []).map(l => l.winnerDelta || 0)));
        return dB - dA;
      });
    }
    return chapterKeys;
  }, [sortMode, chapterKeys, winsPerChapter, mcData, chapters]);

  // Standings (players ordered by wins desc)
  const standings = useMemo(() => {
    const sids = Object.keys(rosterById);
    return sids
      .map(sid => ({ sid, row: rosterById[sid], wins: winsPerPlayer[sid] || 0 }))
      .sort((a, b) => b.wins - a.wins);
  }, [rosterById, winsPerPlayer]);

  const anyResults = Object.keys(results).length > 0;
  // Drill panel is only meaningful outside Level mode (which already shows the
  // detailed rank table inline). Tying `drillVisible` to mode ensures the main
  // padding-right offset clears when mode flips to level.
  const drillVisible = !!drill && mode !== "level";

  // Close the drill whenever mode changes, so stale selection from a previous
  // mode doesn't linger as a blank rail.
  useEffect(() => { setDrill(null); }, [mode]);

  // Transient per-button confirmation: the clicked button's own icon flips to
  // a check (or warn on failure) briefly. Kept off the layout flow entirely —
  // no separate message element — so it never widens the actions cluster,
  // shifts the buttons, or squeezes the title in a narrow/windowed header.
  const [actionState, setActionState] = useState(null); // { key, ok } | null
  const actionTimer = useRef(null);
  function flash(key, ok = true) {
    setActionState({ key, ok });
    if (actionTimer.current) clearTimeout(actionTimer.current);
    actionTimer.current = setTimeout(() => setActionState(null), ok ? 1800 : 2600);
  }
  const iconFor = (key, base) =>
    actionState && actionState.key === key ? (actionState.ok ? "check" : "warn") : base;
  useEffect(() => () => { if (actionTimer.current) clearTimeout(actionTimer.current); }, []);

  function handleCellClick(chapterKey, levelDisplay, cellKey) {
    setDrill({ chapterKey, levelDisplay, cellKey });
  }

  // Build the detailed, per-player table for the levels currently in scope.
  // Columns are grouped per player: <name> time / rank / medal / delta(s).
  // "fastest" is the roster-fastest (the on-screen winner), delta is each
  // runner's gap behind it in seconds. Medal is always included (export is
  // data, not display, so it ignores the on-screen Medals toggle).
  function buildDetailTable() {
    const sids = Object.keys(rosterById);
    const nameFor = (sid) => rosterById[sid].name || truncateSid(sid);
    const headers = ["chapter", "level", "fastest_time", "fastest_runner"];
    for (const sid of sids) {
      const n = nameFor(sid);
      headers.push(`${n} time`, `${n} rank`, `${n} medal`, `${n} delta(s)`);
    }
    const rows = [];
    for (const ck of chapterKeys) {
      for (const lvl of mcData[ck] || []) {
        // Drop levels with no data for anyone — the export should reflect the
        // query, not pad it with empty rows for stages nobody has a time on.
        const hasData = sids.some((sid) => {
          const r = lvl.rowsBySid[sid];
          return r && !r.missing && r.time_us != null;
        });
        if (!hasData) continue;
        const row = [
          ck,
          lvl.levelDisplay,
          lvl.winnerTime != null ? formatTimeUs(lvl.winnerTime) : "",
          lvl.winnerSid ? nameFor(lvl.winnerSid) : "",
        ];
        for (const sid of sids) {
          const r = lvl.rowsBySid[sid];
          if (!r || r.missing || r.time_us == null) { row.push("", "", "", ""); continue; }
          row.push(
            formatTimeUs(r.time_us),
            r.rank != null ? String(r.rank) : "",
            r.medal || "",
            lvl.winnerTime != null ? ((r.time_us - lvl.winnerTime) / 1_000_000).toFixed(3) : "",
          );
        }
        rows.push(row);
      }
    }
    return { headers, rows };
  }

  function toCsv({ headers, rows }) {
    const esc = (c) => {
      const s = `${c}`;
      return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
    };
    return [headers, ...rows].map(r => r.map(esc).join(",")).join("\r\n");
  }
  function toTsv({ headers, rows }) {
    const esc = (c) => `${c}`.replace(/[\t\r\n]/g, " ");
    return [headers, ...rows].map(r => r.map(esc).join("\t")).join("\n");
  }

  function handleCopyStandings() {
    // Compact text summary of standings (players ordered by wins).
    const lines = [];
    lines.push(`Multi Compare — ${validRoster.length} players, ${totalLevels} levels`);
    for (const s of standings) {
      lines.push(`  ${s.row.name || truncateSid(s.sid)}: ${s.wins}`);
    }
    try { navigator.clipboard.writeText(lines.join("\n")); flash("standings"); } catch (e) { flash("standings", false); }
  }

  function handleCopyData() {
    // Tab-separated detailed table (pastes clean into Sheets/Excel) with the
    // standings summary appended below.
    const table = buildDetailTable();
    const lines = [toTsv(table), ""];
    lines.push(`Standings — ${validRoster.length} players, ${totalLevels} levels`);
    for (const s of standings) {
      lines.push(`${s.row.name || truncateSid(s.sid)}\t${s.wins}`);
    }
    try { navigator.clipboard.writeText(lines.join("\n")); flash("data"); } catch (e) { flash("data", false); }
  }

  async function handleExportCsv() {
    const csv = toCsv(buildDetailTable());
    try {
      const res = await saveTextFile("multi-compare.csv", csv);
      if (res && res.ok) flash("csv");
      else if (res && res.cancelled) { /* user dismissed the dialog — no signal */ }
      else { console.error("CSV export failed:", res && res.error); flash("csv", false); }
    } catch (e) { console.error("CSV export failed:", e); flash("csv", false); }
  }

  // ── Render ──────────────────────────────────────────────────────────────
  // Scope = levels in scope for the active mode. `totalLevels` is already
  // scoped (custom → picked count, chapter → that chapter, level → 1, game →
  // all), so it doubles as the level-count tag. Falls back to 121 pre-load.
  const scopeLevelCount = totalLevels;

  const totalsTag = `${scopeLevelCount || 121} levels · ${validRoster.length || roster.length} players`;
  const searchHint = mode === "level"
    ? `· level: ${levelTarget || "(none)"}`
    : mode === "chapter"
      ? `· chapter: ${chapterTarget || "(none)"}`
      : mode === "custom"
        ? `· custom: ${customLevels.length} level${customLevels.length === 1 ? "" : "s"}`
        : "· all 121 levels searched";
  const runStatusHint = running
    ? (progress.total ? `· running… ${progress.done} / ${progress.total}` : "· running…")
    : "";

  return (
    <div className="mc-scope">
      <main className="mc-main" style={{ paddingRight: drillVisible ? 600 : 0 }}>
        <PageHead
          crumb="Leaderboard Tools"
          title="MULTI"
          accentWord="COMPARE"
          subtitle={totalsTag}
          actions={<>
            {anyResults && setShowMedals && <MedalToggle value={showMedals} onChange={setShowMedals} />}
            {anyResults && <Btn kind="ghost" size="sm" icn={iconFor("standings", "copy")} onClick={handleCopyStandings}>Copy standings</Btn>}
            {anyResults && <Btn kind="ghost" size="sm" icn={iconFor("data", "copy")} onClick={handleCopyData}>Copy data</Btn>}
            {anyResults && <Btn kind="ghost" size="sm" icn={iconFor("csv", "export")} onClick={handleExportCsv}>Export CSV</Btn>}
          </>}
        />

        <div className="nwt-content">
          <RosterPanel
            roster={roster}
            validRoster={validRoster}
            editing={rosterEditing}
            onToggleEditing={() => setRosterEditing(e => !e)}
            collapsed={rosterCollapsed}
            onToggleCollapsed={() => setRosterCollapsed(c => !c)}
            savedProfiles={savedProfiles}
            savedRosters={savedRosters}
            idCounts={idCounts}
            onUpdateRow={updateRow}
            onAddRow={addRow}
            onRemoveRow={removeRow}
            onApplyProfile={applyProfileToRow}
            onUseMine={handleUseMine}
            onLoadSavedRoster={handleLoadSavedRoster}
            onDeleteSavedRoster={handleDeleteSavedRoster}
            savePromptOpen={savePromptOpen}
            savePromptNickname={savePromptNickname}
            savePromptError={savePromptError}
            onOpenSavePrompt={openSavePrompt}
            onCloseSavePrompt={closeSavePrompt}
            onSavePromptNicknameChange={setSavePromptNickname}
            onSaveRosterSubmit={handleSaveRosterSubmit}
          />

          <SearchModePanel
            mode={mode}
            onModeChange={setMode}
            levels={levels}
            chapters={chapters}
            levelTarget={levelTarget}
            chapterTarget={chapterTarget}
            onLevelTargetChange={setLevelTarget}
            onChapterTargetChange={setChapterTarget}
            running={running}
            canRun={canRun}
            anyResults={anyResults}
            onRun={handleRun}
            onStop={handleStop}
            onRefresh={handleRefresh}
            searchHint={searchHint}
            runStatusHint={runStatusHint}
            runError={runError}
            customCount={customLevels.length}
            onOpenPicker={() => setPickerOpen(true)}
            onClearCustom={() => handleCustomLevelsChange([])}
          />

          {mode === "game" && Object.keys(neonRanks).length > 0 && (
            <GlobalRanksStrip
              standings={standings} neonRanks={neonRanks}
              collapsed={ranksCollapsed} onToggle={() => setRanksCollapsed(c => !c)}
            />
          )}

          {mode !== "level" && standings.some(s => s.wins > 0) && (
            <StandingsStrip
              standings={standings} totalLevels={scopeLevelCount}
              collapsed={standingsCollapsed} onToggle={() => setStandingsCollapsed(c => !c)}
            />
          )}

          {mode !== "level" && showMedals && anyResults && (
            <MedalsStrip
              standings={standings} medalsPerPlayer={medalsPerPlayer}
              collapsed={medalsCollapsed} onToggle={() => setMedalsCollapsed(c => !c)}
            />
          )}

          {mode === "level" ? (
            <LevelResultPanel
              mcData={mcData}
              levelDisplay={levelTarget}
              rosterById={rosterById}
              showMedals={showMedals}
              anyResults={anyResults}
            />
          ) : (
            <ResultsGrid
              mode={mode}
              chapterKeys={mode === "chapter" ? (chapterTarget ? [chapterTarget] : []) : sortedChapterKeys}
              chapters={chapters}
              mcData={mcData}
              rosterById={rosterById}
              filterPlayer={filterPlayer}
              onFilterPlayer={setFilterPlayer}
              sortMode={sortMode}
              onSortMode={setSortMode}
              selectedKey={drill ? drill.cellKey : null}
              onCellClick={handleCellClick}
              anyResults={anyResults}
              scopeLevelCount={scopeLevelCount}
              chapterTarget={chapterTarget}
              customScope={customScope}
            />
          )}
        </div>
      </main>

      {drillVisible && mode !== "level" && (
        <DrillPanel
          drill={drill}
          mcData={mcData}
          rosterById={rosterById}
          showMedals={showMedals}
          onClose={() => setDrill(null)}
        />
      )}

      <LevelPickerModal
        open={pickerOpen} onClose={() => setPickerOpen(false)}
        value={customLevels} onChange={handleCustomLevelsChange}
        levels={levels} chapters={chaptersList}
      />
    </div>
  );
}

// ── Roster panel ─────────────────────────────────────────────────────────
function RosterPanel({
  roster, validRoster, editing, onToggleEditing, collapsed, onToggleCollapsed,
  savedProfiles, savedRosters, idCounts,
  onUpdateRow, onAddRow, onRemoveRow, onApplyProfile, onUseMine,
  onLoadSavedRoster, onDeleteSavedRoster,
  savePromptOpen, savePromptNickname, savePromptError,
  onOpenSavePrompt, onCloseSavePrompt, onSavePromptNicknameChange, onSaveRosterSubmit,
}) {
  return (
    <div className="nwt-panel">
      {/* Caret toggles the pills-row collapse; Edit button toggles the editor.
          Bar body is inert — the two actions have distinct, non-overlapping
          hit targets. */}
      <div className="nwt-panel-head">
        <span
          className={"car collapser" + (collapsed ? " collapsed" : "")}
          onClick={onToggleCollapsed}
          title={collapsed ? "Show roster" : "Hide roster"}
        >
          <McIcon name="caret" size={9} />
        </span>
        <span className="title">Roster</span>
        <span className="right">
          <span className="nwt-tag">{roster.length} / {MAX_ROWS}</span>
          <Btn kind="ghost" size="sm" onClick={onToggleEditing}>
            {editing ? "Done" : "Edit roster"}
          </Btn>
        </span>
      </div>

      {/* Pills row — hidden when the roster panel is collapsed. */}
      {!collapsed && (
        <div className="nwt-roster-row">
          {roster.map((p, i) => {
            const sid = (p.steam_id || "").trim();
            return (
              <div key={i} className={"nwt-pl-pill" + (sid ? "" : " empty")}>
                <span className="sw" style={{ background: hexFor(p.color) }} />
                <span>{p.name || `Player ${i + 1}`}</span>
                <span className="sid">{sid ? truncateSid(sid) : "no id"}</span>
              </div>
            );
          })}
        </div>
      )}

      {editing && (
        <div className="nwt-roster-editor">
          <SavedRostersDropdown
            rosters={savedRosters}
            onLoad={onLoadSavedRoster}
            onDelete={onDeleteSavedRoster}
          />
          <RosterEditor
            roster={roster}
            savedProfiles={savedProfiles}
            idCounts={idCounts}
            onUpdateRow={onUpdateRow}
            onRemoveRow={onRemoveRow}
            onApplyProfile={onApplyProfile}
            onUseMine={onUseMine}
          />
          <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
            <Btn kind="ghost" size="sm" onClick={onAddRow} disabled={roster.length >= MAX_ROWS}>
              + Add player
            </Btn>
            <Btn
              kind="ghost"
              size="sm"
              onClick={onOpenSavePrompt}
              disabled={validRoster.length === 0 || savedRosters.length >= MAX_ROSTERS}
            >
              ★ Save roster
            </Btn>
            <span style={{ flex: 1 }} />
            <span style={{ color: "var(--mc-text-3)", fontSize: 11 }}>
              {validRoster.length} valid steamID{validRoster.length === 1 ? "" : "s"}
            </span>
          </div>
          {savePromptOpen && (
            <SaveRosterPrompt
              nickname={savePromptNickname}
              error={savePromptError}
              onNicknameChange={onSavePromptNicknameChange}
              onSubmit={onSaveRosterSubmit}
              onCancel={onCloseSavePrompt}
              validCount={validRoster.length}
            />
          )}
        </div>
      )}
    </div>
  );
}

// ── Roster editor (inline row table) ─────────────────────────────────────
function RosterEditor({ roster, savedProfiles, idCounts, onUpdateRow, onRemoveRow, onApplyProfile, onUseMine }) {
  const usedColors = roster.map(r => r.color);
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
      <div className="mc-row header">
        <span></span><span>name</span><span style={{ textAlign: "center" }}>init</span>
        <span>steam id</span><span></span>
      </div>
      {roster.map((row, idx) => {
        const trimmed = (row.steam_id || "").trim();
        const formatOk = STEAM_ID_RE.test(trimmed);
        const isDup = trimmed && (idCounts?.[trimmed] || 0) > 1;
        const errorBorder = (trimmed && !formatOk) || isDup;
        return (
          <div key={idx} className="mc-row">
            <ColorPickerInline
              value={row.color}
              onChange={(c) => onUpdateRow(idx, { color: c })}
              disallowed={usedColors.filter((c, i) => i !== idx)}
            />
            <input
              className="mc-input"
              value={row.name}
              onChange={(e) => onUpdateRow(idx, { name: e.target.value, initial: deriveInitial(e.target.value) })}
              placeholder={`Player ${idx + 1}`}
            />
            <input
              className="mc-input"
              style={{ textAlign: "center" }}
              value={row.initial}
              onChange={(e) => onUpdateRow(idx, { initial: (e.target.value || "").slice(0, 2).toUpperCase() })}
              maxLength={2}
              placeholder={String(idx + 1)}
            />
            <input
              className={"mc-input" + (errorBorder ? " error" : "")}
              value={row.steam_id}
              onChange={(e) => onUpdateRow(idx, { steam_id: e.target.value.trim() })}
              placeholder="76561198…"
              title={isDup ? "Duplicate of another row" : (trimmed && !formatOk ? "Must be 17 digits" : undefined)}
            />
            <span className="actions">
              <Btn kind="ghost" size="sm" onClick={() => onUseMine(idx)} title="Use my connected Steam ID">Mine</Btn>
              <SavedProfilesDropdown
                profiles={savedProfiles}
                onSelect={(p) => onApplyProfile(idx, p)}
                disabledIds={new Set(
                  roster.filter((_, i) => i !== idx)
                    .map(r => (r.steam_id || "").trim())
                    .filter(Boolean)
                )}
              />
              <Btn
                kind="ghost"
                size="sm"
                onClick={() => onRemoveRow(idx)}
                disabled={roster.length <= MIN_ROWS}
              >−</Btn>
            </span>
          </div>
        );
      })}
    </div>
  );
}

function ColorPickerInline({ value, onChange, disallowed = [] }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  const disSet = new Set(disallowed);
  useEffect(() => {
    if (!open) return;
    function onDoc(e) { if (ref.current && !ref.current.contains(e.target)) setOpen(false); }
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [open]);
  return (
    <span ref={ref} style={{ position: "relative", display: "inline-block" }}>
      <button
        type="button"
        className="mc-swatch"
        onClick={() => setOpen(o => !o)}
        style={{ background: hexFor(value) }}
        title={`color: ${value}`}
      />
      {open && (
        <div className="mc-swatch-menu">
          {PLAYER_COLORS.map(c => {
            const taken = disSet.has(c.key) && c.key !== value;
            return (
              <button
                key={c.key}
                type="button"
                className="mc-swatch-option"
                onClick={() => { if (!taken) { onChange(c.key); setOpen(false); } }}
                disabled={taken}
                title={taken ? `${c.label} (in use)` : c.label}
                style={{
                  background: c.hex,
                  opacity: taken ? 0.25 : 1,
                  outline: c.key === value ? "2px solid var(--mc-accent)" : "none",
                  cursor: taken ? "not-allowed" : "pointer",
                }}
              />
            );
          })}
        </div>
      )}
    </span>
  );
}

// Saved Rosters dropdown — mirrors the shared SavedProfilesDropdown pattern
// (Btn toggle, fixed-overlay outside-click backdrop, right-anchored menu).
function SavedRostersDropdown({ rosters, onLoad, onDelete }) {
  const [open, setOpen] = useState(false);
  return (
    <div style={{ position: "relative", display: "inline-block" }}>
      <Btn kind="ghost" size="sm" onClick={() => setOpen(v => !v)}>
        ▾ Saved rosters ({rosters.length})
      </Btn>
      {open && (
        <>
          <div style={{ position: "fixed", inset: 0, zIndex: 199 }} onClick={() => setOpen(false)} />
          <div style={{
            position: "absolute", top: "100%", left: 0, zIndex: 200,
            background: "var(--bg-2)", border: "1px solid var(--border)",
            borderRadius: 6, minWidth: 260, boxShadow: "0 4px 16px rgba(0,0,0,0.4)",
            marginTop: 4, maxHeight: 360, overflowY: "auto",
          }}>
            {rosters.length === 0 ? (
              <div style={{ padding: "10px 12px", fontSize: 11, color: "var(--text-3)" }}>
                No saved rosters yet — fill in players, then ★ Save roster.
              </div>
            ) : rosters.slice().reverse().map((r, revIdx) => {
              const idx = rosters.length - 1 - revIdx;
              const memberCount = (r.members || []).length;
              return (
                <div key={idx} style={{ display: "flex", alignItems: "stretch" }}>
                  <button
                    type="button"
                    onClick={() => { onLoad(idx); setOpen(false); }}
                    style={{
                      flex: 1, textAlign: "left", padding: "7px 12px",
                      background: "none", border: "none", color: "var(--text)",
                      cursor: "pointer", fontSize: 12,
                    }}
                    onMouseEnter={e => e.currentTarget.style.background = "var(--bg-3, var(--surface-2))"}
                    onMouseLeave={e => e.currentTarget.style.background = "none"}
                  >
                    <span style={{ fontWeight: 600 }}>{r.nickname}</span>
                    <span style={{ color: "var(--text-3)", marginLeft: 8, fontSize: 10 }}>
                      {memberCount} player{memberCount === 1 ? "" : "s"}
                    </span>
                  </button>
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      if (window.confirm(`Delete saved roster "${r.nickname}"?`)) onDelete(idx);
                    }}
                    title="Delete this saved roster"
                    style={{
                      background: "none", border: "none", color: "var(--text-3)",
                      padding: "0 12px", cursor: "pointer", fontSize: 12,
                    }}
                    onMouseEnter={e => e.currentTarget.style.color = "var(--bad, #f87171)"}
                    onMouseLeave={e => e.currentTarget.style.color = "var(--text-3)"}
                  >
                    ✕
                  </button>
                </div>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}

function SaveRosterPrompt({ nickname, error, onNicknameChange, onSubmit, onCancel, validCount }) {
  const inputRef = useRef(null);
  useEffect(() => { inputRef.current && inputRef.current.focus(); }, []);
  function onKey(e) {
    if (e.key === "Enter") onSubmit();
    else if (e.key === "Escape") onCancel();
  }
  return (
    <div className="mc-save-prompt">
      <span style={{ color: "var(--mc-text-3)", fontSize: 11 }}>
        Save these {validCount} player{validCount === 1 ? "" : "s"} as a roster:
      </span>
      <input
        ref={inputRef}
        value={nickname}
        onChange={(e) => onNicknameChange(e.target.value)}
        onKeyDown={onKey}
        placeholder="Roster name (e.g. Top 5 friends)"
        maxLength={32}
      />
      <Btn kind="primary" size="sm" onClick={onSubmit}>Save</Btn>
      <Btn kind="ghost" size="sm" onClick={onCancel}>Cancel</Btn>
      {error && <span className="err">{error}</span>}
    </div>
  );
}

// ── Search mode panel ────────────────────────────────────────────────────
function SearchModePanel({
  mode, onModeChange, levels, chapters, levelTarget, chapterTarget,
  onLevelTargetChange, onChapterTargetChange,
  running, canRun, anyResults, onRun, onStop, onRefresh, searchHint, runStatusHint,
  runError, customCount, onOpenPicker, onClearCustom,
}) {
  return (
    <div className="nwt-panel">
      <div className="nwt-panel-head">
        <span className="car"><McIcon name="caret" size={9} /></span>
        <span className="title">Search mode</span>
      </div>
      <div className="nwt-controls-row">
        <Seg options={["level", "chapter", "game", "custom"]} value={mode} onChange={onModeChange} />
        {mode === "custom" && (
          <>
            <Btn kind="ghost" size="sm" onClick={onOpenPicker} disabled={running}>
              {customCount ? `${customCount} levels selected` : "Pick levels…"}
            </Btn>
            {customCount > 0 && (
              <Btn kind="ghost" size="sm" onClick={onClearCustom} disabled={running}>Clear</Btn>
            )}
          </>
        )}
        {mode === "level" && (
          <select
            className="nwt-select"
            value={levelTarget}
            onChange={(e) => onLevelTargetChange(e.target.value)}
          >
            {levels.map(lv => <option key={lv.internal} value={lv.display}>{lv.display}</option>)}
          </select>
        )}
        {mode === "chapter" && (
          <select
            className="nwt-select"
            value={chapterTarget}
            onChange={(e) => onChapterTargetChange(e.target.value)}
          >
            {Object.keys(chapters).map(k => <option key={k} value={k}>{k}</option>)}
          </select>
        )}
        <span style={{ color: "var(--mc-text-3)", fontSize: 11 }}>{searchHint}</span>
        <span style={{ flex: 1 }} />
        {running
          ? <Btn kind="danger" size="lg" onClick={onStop}>Stop</Btn>
          : <>
              {anyResults && (
                <Btn kind="ghost" size="lg" icn="refresh" onClick={onRefresh} disabled={!canRun}
                     title="Clear these players' cached times and re-run for fresh data">Refresh</Btn>
              )}
              <Btn kind="primary" size="lg" icn="multicompare" onClick={onRun} disabled={!canRun}>Run</Btn>
            </>}
        {runStatusHint && (
          <span style={{ color: "var(--mc-text-3)", fontSize: 11 }}>{runStatusHint}</span>
        )}
      </div>
      {runError && (
        <div style={{ color: "var(--bad, #f87171)", fontSize: 11, marginTop: 6 }}>{runError}</div>
      )}
    </div>
  );
}

// ── Summary strips ───────────────────────────────────────────────────────
// Shared shell for the three summary strips. Only the caret is the click
// target (keeps the Global-rank asterisk tooltip clickable without collapsing
// the strip). `label` accepts a node; `style` passes through for MedalsStrip's
// flex-wrap. Children (chips, winbars) are dropped when collapsed.
function CollapsibleStrip({ label, collapsed, onToggle, style, children }) {
  return (
    <div className="nwt-sum-strip" style={style}>
      <span className={"lbl collapser" + (collapsed ? " collapsed" : "")}>
        <span className="car" onClick={onToggle} title={collapsed ? "Expand" : "Collapse"}>
          <McIcon name="caret" size={9} />
        </span>
        {label}
      </span>
      {!collapsed && children}
    </div>
  );
}

function GlobalRanksStrip({ standings, neonRanks, collapsed, onToggle }) {
  return (
    <CollapsibleStrip
      collapsed={collapsed} onToggle={onToggle}
      label={<>
        Global rank
        <span title="Steam stores story-level total only. The in-game 'Global Neon Rankings' adds Sidequest level times client-side per player, which is not Steam-queryable — so the rank may differ slightly from in-game."
              style={{ color: "var(--accent)", cursor: "help", marginLeft: 2 }}>*</span>
      </>}
    >
      {standings.map((s, i) => {
        const nr = neonRanks[s.sid];
        const label = nr === undefined ? "…" : nr?.ok ? `#${nr.rank.toLocaleString()}` : "—";
        return (
          <React.Fragment key={s.sid}>
            <span className="nwt-sum-chip">
              <span className="sw" style={{ background: hexFor(s.row.color) }} />
              <span>{s.row.name || truncateSid(s.sid)}</span>
              <span className="n">{label}</span>
            </span>
            {i < standings.length - 1 && <span className="sep">·</span>}
          </React.Fragment>
        );
      })}
    </CollapsibleStrip>
  );
}

function StandingsStrip({ standings, totalLevels, collapsed, onToggle }) {
  return (
    <CollapsibleStrip label="Standings" collapsed={collapsed} onToggle={onToggle}>
      {standings.map((s, i) => (
        <React.Fragment key={s.sid}>
          <span className="nwt-sum-chip">
            <span className="sw" style={{ background: hexFor(s.row.color) }} />
            <span>{s.row.name || truncateSid(s.sid)}</span>
            <span className="n">{s.wins}</span>
            {i === 0 && <span className="total">/ {totalLevels}</span>}
          </span>
          {i < standings.length - 1 && <span className="sep">·</span>}
        </React.Fragment>
      ))}
      <span style={{ flex: 1 }} />
      <div className="winbars">
        {standings.map(s => {
          const pct = totalLevels ? (s.wins / totalLevels) * 100 : 0;
          return <div key={s.sid} className="seg" style={{ width: pct + "%", background: hexFor(s.row.color) }} />;
        })}
      </div>
    </CollapsibleStrip>
  );
}

function MedalsStrip({ standings, medalsPerPlayer, collapsed, onToggle }) {
  // Iterates in standings order (most wins first). Gradient repaints on
  // moved-node reorders are handled by translateZ(0) in MedalBadge.
  return (
    <CollapsibleStrip
      label="Medals" collapsed={collapsed} onToggle={onToggle}
      style={{ flexWrap: "wrap", rowGap: 8, columnGap: 8 }}
    >
      {standings.map(s => {
        const counts = medalsPerPlayer[s.sid] || {};
        const tiers = MEDAL_TIER_ORDER.filter(t => counts[t]);
        const hex = hexFor(s.row.color);
        return (
          <span
            key={s.sid}
            className="nwt-sum-chip"
            style={{
              gap: 6,
              padding: "3px 8px",
              border: `1px solid ${hex}`,
              background: `${hex}1a`,
              borderRadius: 4,
            }}
          >
            <span style={{ color: hex, fontWeight: 600 }}>{s.row.name || truncateSid(s.sid)}</span>
            {tiers.length === 0
              ? <span className="n" style={{ opacity: 0.5 }}>—</span>
              : tiers.map(t => (
                  <span key={t} style={{ display: "inline-flex", alignItems: "center", gap: 3 }}>
                    <MedalBadge medal={t} />
                    <span className="n">{counts[t]}</span>
                  </span>
                ))
            }
          </span>
        );
      })}
    </CollapsibleStrip>
  );
}

// ── Results grid ─────────────────────────────────────────────────────────
function ResultsGrid({
  mode, chapterKeys, chapters, mcData, rosterById,
  filterPlayer, onFilterPlayer, sortMode, onSortMode,
  selectedKey, onCellClick, anyResults, scopeLevelCount, chapterTarget, customScope,
}) {
  const rosterEntries = Object.entries(rosterById);  // [[sid, row], ...]
  // Sort seg only meaningful when there's more than one chapter to reorder.
  const showSort = mode === "game";
  const titleText = mode === "chapter"
    ? `Result · ${chapterTarget || "(no chapter)"} · ${(chapters[chapterTarget] || []).length} levels`
    : `Result · all ${scopeLevelCount || Object.values(chapters).reduce((a, l) => a + l.length, 0) || 121} levels`;
  return (
    <div className="nwt-grid-wrap">
      {/* Row 1 — title + descriptive hint */}
      <div className="nwt-grid-toolbar">
        <span className="title">{titleText}</span>
        <span className="hint">cells coloured by winner — click a cell for the breakdown</span>
      </div>
      {/* Row 2 — filter chips + sort segmented. Kept on its own row so the long
          chapter-mode title can't push the chips off-screen via flex wrap. */}
      <div className="nwt-grid-toolbar" style={{ paddingTop: 10 }}>
        <span className="ctrl-label">Show only</span>
        <span
          className={"nwt-fchip" + (filterPlayer === null ? " on" : "")}
          onClick={() => onFilterPlayer(null)}
        >
          all
        </span>
        {rosterEntries.map(([sid, p]) => (
          <span
            key={sid}
            className={"nwt-fchip" + (filterPlayer === sid ? " on" : (filterPlayer ? " dim" : ""))}
            onClick={() => onFilterPlayer(filterPlayer === sid ? null : sid)}
          >
            <span className="sw" style={{ background: hexFor(p.color) }} />
            <span>{p.name || truncateSid(sid)}</span>
          </span>
        ))}
        <span className="right">
          <span className="ctrl-label">Sort</span>
          {showSort ? (
            <Seg
              options={["chapter", "most contested", "biggest Δ"]}
              value={sortMode}
              onChange={onSortMode}
            />
          ) : (
            // Chapter mode has one chapter to "sort" — nothing to reorder. Show the
            // seg disabled instead of hiding it so cell positioning stays consistent
            // with Game mode (the seg height is what pads the toolbar row).
            <div
              style={{ opacity: 0.35, pointerEvents: "none" }}
              title="Sort only applies when comparing multiple chapters"
            >
              <Seg
                options={["chapter", "most contested", "biggest Δ"]}
                value={sortMode}
                onChange={() => {}}
              />
            </div>
          )}
        </span>
      </div>

      {!anyResults && (
        <div className="mc-placeholder">No results yet. Configure a roster, pick a mode, and press <strong>run</strong>.</div>
      )}

      {chapterKeys.map(ck => (
        <ChapterRow
          key={ck}
          chapterKey={ck}
          levels={chapters[ck] || []}
          levelData={mcData[ck] || []}
          rosterById={rosterById}
          filterPlayer={filterPlayer}
          selectedKey={selectedKey}
          onCellClick={onCellClick}
          customScope={customScope}
        />
      ))}
    </div>
  );
}

function ChapterRow({ chapterKey, levels, levelData, rosterById, filterPlayer, selectedKey, onCellClick, customScope }) {
  const padded = [];
  for (let i = 0; i < 10; i++) {
    padded.push(i < levelData.length ? levelData[i] : null);
  }
  return (
    <div className="nwt-ch-row">
      <div className="nwt-ch-label">
        <span className="name">{chapterShortLabel(chapterKey)}</span>
      </div>
      <div className="nwt-ch-cells">
        {padded.map((lvl, i) => {
          if (!lvl) {
            return <div key={i} className="nwt-cell compact empty" />;
          }
          const cellKey = chapterKey + "::" + i;
          // In custom mode, levels outside the picked set stay on the map but are
          // darkened + non-interactive ("scope mask").
          const outOfScope = customScope && !customScope.has(lvl.levelDisplay);
          const dim = filterPlayer && lvl.winnerSid !== filterPlayer;
          const sel = selectedKey === cellKey;
          let bg = "transparent";
          let extraClass = "";
          if (lvl.winnerSid) {
            bg = hexFor(rosterById[lvl.winnerSid]?.color || "white");
          } else if (lvl.missingRows.length > 0) {
            extraClass = " missing";
          } else {
            extraClass = " empty";  // no data yet
          }
          const classes = ["nwt-cell", "compact", sel ? "selected" : "",
                           dim ? "filtered-out" : "", outOfScope ? "out-of-scope" : "", extraClass.trim()]
            .filter(Boolean).join(" ");
          return (
            <div
              key={i}
              className={classes}
              style={(lvl.winnerSid && !outOfScope) ? { background: bg } : undefined}
              onClick={outOfScope ? undefined : () => onCellClick(chapterKey, lvl.levelDisplay, cellKey)}
              title={
                outOfScope
                  ? `${lvl.levelDisplay} — not in custom set`
                  : lvl.winnerSid
                    ? `${lvl.levelDisplay} — ${rosterById[lvl.winnerSid]?.name || ""} ${formatTimeUs(lvl.winnerTime)}${lvl.winnerDelta != null ? ` (+${formatTimeUs(lvl.winnerDelta).replace("s","")}s)` : ""}`
                    : lvl.levelDisplay
              }
            />
          );
        })}
      </div>
    </div>
  );
}

// ── Reusable bits used by both the drill panel and the Level-mode result ──
function MetaStrip({ lvl, rosterById, showMedals }) {
  const sorted = lvl ? lvl.sortedRows : [];
  const winnerRow = sorted[0] || null;
  const winner = lvl && lvl.winnerSid ? rosterById[lvl.winnerSid] : null;
  if (!winnerRow) {
    return (
      <div style={{ padding: "14px 24px", borderBottom: "1px solid var(--mc-border)", color: "var(--mc-text-3)", fontSize: 12 }}>
        No times yet for this level.
      </div>
    );
  }
  return (
    <div className="nwt-drill-meta-strip">
      <div className="item">
        <span className="lbl">Winner</span>
        <span className="val" style={{ display: "flex", gap: 6, alignItems: "center" }}>
          <span style={{ width: 10, height: 10, borderRadius: 2, background: hexFor(winner?.color || "white") }} />
          <span style={{ color: hexFor(winner?.color || "white") }}>{winner?.name || truncateSid(winnerRow.steam_id)}</span>
        </span>
      </div>
      <div className="item">
        <span className="lbl">Winning time</span>
        <span className="val accent">{formatTimeUs(winnerRow.time_us)}</span>
      </div>
      <div className="item">
        <span className="lbl">Lead Δ vs 2nd</span>
        <span className="val">{lvl.winnerDelta != null ? `+${formatTimeUs(lvl.winnerDelta).replace(/s$/, "")}s` : "—"}</span>
      </div>
      {showMedals && (
        <div className="item">
          <span className="lbl">Top medal</span>
          <span className="val">{winnerRow.medal ? <MedalBadge medal={winnerRow.medal} plain /> : "—"}</span>
        </div>
      )}
      <div className="item">
        <span className="lbl">Top global rank</span>
        <span className="val">{winnerRow.rank != null ? `#${winnerRow.rank.toLocaleString()}` : "—"}</span>
      </div>
    </div>
  );
}

function RankTable({ lvl, rosterById, showMedals }) {
  const sorted = lvl ? lvl.sortedRows : [];
  const missing = lvl ? lvl.missingRows : [];
  return (
    <table className="nwt-drill-table">
      <thead>
        <tr>
          <th>#</th>
          <th>Player</th>
          <th className="r">Time</th>
          <th className="r">Δ vs above</th>
          <th className="r">Δ vs 1st</th>
          {showMedals && <th>Medal</th>}
          <th className="r">LB rank</th>
        </tr>
      </thead>
      <tbody>
        {sorted.map((row, i) => {
          const p = rosterById[row.steam_id];
          const above = i === 0 ? null : sorted[i - 1];
          const dAbove = above ? row.time_us - above.time_us : null;
          const d1 = i === 0 ? null : row.time_us - sorted[0].time_us;
          return (
            <tr key={row.steam_id} className={i === 0 ? "winner" : ""}>
              <td className="rank-col">{i + 1}</td>
              <td className="player">
                <span className="pp">
                  <span className="sw" style={{ background: hexFor(p?.color || "white") }} />
                  <span>{p?.name || truncateSid(row.steam_id)}</span>
                </span>
              </td>
              <td className="r time">{formatTimeUs(row.time_us)}</td>
              <td className="r delta">{dAbove == null ? "—" : (dAbove === 0 ? "tie" : `+${formatTimeUs(dAbove).replace(/s$/, "")}s`)}</td>
              <td className="r delta">{d1 == null ? "—" : (d1 === 0 ? "tie" : `+${formatTimeUs(d1).replace(/s$/, "")}s`)}</td>
              {showMedals && <td>{row.medal ? <MedalBadge medal={row.medal} plain /> : "—"}</td>}
              <td className="r lb">{row.rank != null ? `#${row.rank.toLocaleString()}` : "—"}</td>
            </tr>
          );
        })}
        {missing.map(row => {
          const p = rosterById[row.steam_id];
          return (
            <tr key={row.steam_id + "-miss"} style={{ opacity: 0.5 }}>
              <td className="rank-col">—</td>
              <td className="player">
                <span className="pp">
                  <span className="sw" style={{ background: hexFor(p?.color || "white") }} />
                  <span>{p?.name || truncateSid(row.steam_id)}</span>
                </span>
              </td>
              <td className="r delta" colSpan={showMedals ? 5 : 4} style={{ fontStyle: "italic", textAlign: "left" }}>
                no time on this level
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

// ── Level-mode result (inline, no drill panel) ───────────────────────────
function LevelResultPanel({ mcData, levelDisplay, rosterById, showMedals, anyResults }) {
  const lvl = useMemo(() => {
    for (const entries of Object.values(mcData)) {
      const hit = entries.find(l => l.levelDisplay === levelDisplay);
      if (hit) return hit;
    }
    return null;
  }, [mcData, levelDisplay]);

  if (!anyResults || !lvl) {
    return (
      <div className="nwt-grid-wrap">
        <div className="nwt-grid-toolbar">
          <span className="title">Result · {levelDisplay || "(no level)"}</span>
        </div>
        <div className="mc-placeholder">
          No results yet. Configure a roster, pick a level, and press <strong>run</strong>.
        </div>
      </div>
    );
  }

  return (
    <div className="nwt-grid-wrap" style={{ padding: 0 }}>
      <div className="nwt-grid-toolbar" style={{ padding: "14px 18px 12px" }}>
        <span className="title">Result · {levelDisplay}</span>
      </div>
      <MetaStrip lvl={lvl} rosterById={rosterById} showMedals={showMedals} />
      <RankTable lvl={lvl} rosterById={rosterById} showMedals={showMedals} />
    </div>
  );
}

// ── Drill panel ──────────────────────────────────────────────────────────
function DrillPanel({ drill, mcData, rosterById, showMedals, onClose }) {
  useEffect(() => {
    function onKey(e) { if (e.key === "Escape") onClose(); }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  const lvl = useMemo(() => {
    if (!drill) return null;
    const arr = mcData[drill.chapterKey] || [];
    return arr.find(l => l.levelDisplay === drill.levelDisplay) || null;
  }, [drill, mcData]);

  if (!drill) return null;

  return (
    <aside className="nwt-drill">
      <div className="nwt-drill-head">
        <div>
          <div className="crumb">Level detail · {chapterShortLabel(drill.chapterKey)}</div>
          <h2 className="title">{drill.levelDisplay}</h2>
        </div>
        <div className="right">
          <button className="x" onClick={onClose} title="Close">
            <McIcon name="close" size={11}/>
          </button>
        </div>
      </div>

      <MetaStrip lvl={lvl} rosterById={rosterById} showMedals={showMedals} />

      <div className="nwt-drill-body">
        <RankTable lvl={lvl} rosterById={rosterById} showMedals={showMedals} />
        <div style={{ padding: "18px 24px 24px", color: "var(--mc-text-3)", fontSize: 11, lineHeight: 1.7 }}>
          <div style={{ marginBottom: 6, color: "var(--mc-text-2)", letterSpacing: "0.12em", textTransform: "uppercase", fontSize: 10 }}>Notes</div>
          <div>· Δ vs above measures gap to next-faster player in this roster.</div>
          <div>· LB rank is each player's individual global ranking, not their position within the roster.</div>
        </div>
      </div>
    </aside>
  );
}
