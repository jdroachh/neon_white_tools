import React, { useState, useEffect, useRef, useMemo } from "react";

import { PageHead, Seg, Btn } from "../shared.jsx";
import { loadProfiles } from "../lib/savedProfiles.js";
import SavedProfilesDropdown from "../components/SavedProfilesDropdown.jsx";
import {
  loadRosters, saveRosters, addRoster, removeRoster, MAX as MAX_ROSTERS,
} from "../lib/savedRosters.js";
import { PLAYER_COLORS, hexFor, nextAvailableColor } from "../lib/playerColors.js";
import { getLevels, getChapters, runMultiCompare, stopMultiCompare } from "../api.js";

const STEAM_ID_RE = /^\d{17}$/;
const MIN_ROWS = 1;
const DEFAULT_ROWS = 3;
const MAX_ROWS = 10;

// ── Time formatting (microseconds → display) ──────────────────────────────
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

function makeEmptyRow(usedColors, rowIndex) {
  const playerNum = (rowIndex ?? usedColors.length) + 1;
  return {
    color: nextAvailableColor(usedColors),
    name: `Player ${playerNum}`,
    initial: String(playerNum),
    steam_id: "",
  };
}

function deriveInitial(name) {
  return (name || "").trim().charAt(0).toUpperCase();
}

export default function MultiCompare({ visible = false } = {}) {
  // ── Roster ──────────────────────────────────────────────────────────────
  const [roster, setRoster] = useState(() => {
    const rows = [];
    for (let i = 0; i < DEFAULT_ROWS; i++) {
      rows.push(makeEmptyRow(rows.map(r => r.color), i));
    }
    return rows;
  });

  // ── Bridge data ─────────────────────────────────────────────────────────
  const [levels, setLevels] = useState([]);              // [{display, internal}]
  const [chapters, setChapters] = useState({});          // { chapterKey: [displayNames] }
  const [savedProfiles, setSavedProfiles] = useState([]); // [{nickname, steam_id}]
  const [savedRosters, setSavedRosters] = useState([]);   // [{nickname, members, saved_at}]

  // ── Save-roster inline prompt ───────────────────────────────────────────
  const [savePromptOpen, setSavePromptOpen] = useState(false);
  const [savePromptNickname, setSavePromptNickname] = useState("");
  const [savePromptError, setSavePromptError] = useState("");

  // ── View / run state ───────────────────────────────────────────────────
  const [mode, setMode] = useState("level"); // "level" | "chapter" | "game"
  const [levelTarget, setLevelTarget] = useState("");      // level display name
  const [chapterTarget, setChapterTarget] = useState("");  // chapter key
  const [running, setRunning] = useState(false);
  const [progress, setProgress] = useState({ done: 0, total: 0 });
  // Streamed results, keyed by `${steam_id}::${level_code}` -> row payload
  const [results, setResults] = useState({});
  // Drill-down drawer: level display name when open, null when closed.
  // Independent of `mode` so the underlying view stays put behind the drawer.
  const [drilldownLevel, setDrilldownLevel] = useState(null);
  // Roster auto-collapses after a successful run; user can re-expand via
  // the "edit roster" button. Stays open during entry and while running so
  // progress remains visible against roster context.
  const [rosterCollapsed, setRosterCollapsed] = useState(false);

  const runIdRef = useRef(0);

  // Section-level collapse (independent of the roster's pill-summary mode).
  // Click a section title to fully hide its contents.
  const [sectionsCollapsed, setSectionsCollapsed] = useState({ roster: false, view: false, result: false });
  function toggleSection(key) {
    setSectionsCollapsed(prev => ({ ...prev, [key]: !prev[key] }));
  }

  // ── Initial bridge load ─────────────────────────────────────────────────
  useEffect(() => {
    function load() {
      Promise.all([getLevels(), getChapters(), loadProfiles(), loadRosters()]).then(([lv, ch, pr, ro]) => {
        setLevels(lv);
        const chDict = {};
        for (const c of (ch || [])) chDict[c.name] = c.levels;
        setChapters(chDict);
        setSavedProfiles(pr);
        setSavedRosters(ro);
        if (!levelTarget && lv.length) setLevelTarget(lv[0].display);
        const chKeys = Object.keys(chDict);
        if (!chapterTarget && chKeys.length) setChapterTarget(chKeys[0]);
      });
    }
    if (window.pywebview) load();
    else window.addEventListener("pywebviewready", load, { once: true });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Re-pull profiles + rosters whenever the page becomes visible, so edits made
  // in Settings reflect here without an app restart. Levels/chapters are static.
  useEffect(() => {
    if (!visible) return;
    loadProfiles().then(setSavedProfiles).catch(() => {});
    loadRosters().then(setSavedRosters).catch(() => {});
  }, [visible]);

  // ── Multi-Compare event listener ────────────────────────────────────────
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
        // Auto-collapse the roster on natural completion only — a stopped
        // run leaves the roster open so the user can keep editing.
        if (evt.message === "ok") setRosterCollapsed(true);
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

  // ── Run / stop ──────────────────────────────────────────────────────────
  // Rows are valid only if format-correct AND their steam_id is unique
  // within the roster. Duplicates exclude *all* matching rows so the user
  // gets visual feedback to fix them.
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
    (mode === "chapter" && !!chapterTarget)
  );

  function handleRun() {
    if (!canRun) return;
    setResults({});
    setProgress({ done: 0, total: 0 });
    runIdRef.current += 1;
    setRunning(true);
    const steam_ids = validRoster.map(r => r.steam_id.trim());
    const target = mode === "level" ? levelTarget : (mode === "chapter" ? chapterTarget : "");
    runMultiCompare(steam_ids, mode, target).then(res => {
      if (!res.ok) {
        console.error("[multi-compare] run failed:", res.error);
        setRunning(false);
      }
    });
  }
  function handleStop() {
    stopMultiCompare();
  }

  // ── Saved roster actions ────────────────────────────────────────────────
  function openSavePrompt() {
    setSavePromptNickname("");
    setSavePromptError("");
    setSavePromptOpen(true);
  }
  function closeSavePrompt() {
    setSavePromptOpen(false);
    setSavePromptError("");
  }
  function handleSaveRosterSubmit() {
    if (validRoster.length === 0) return;
    const members = validRoster.map(r => ({
      color: r.color, name: r.name, initial: r.initial, steam_id: r.steam_id.trim(),
    }));
    const { error, list } = addRoster(savedRosters, {
      nickname: savePromptNickname,
      members,
    });
    if (error) {
      setSavePromptError(error);
      return;
    }
    setSavedRosters(list);
    saveRosters(list).catch(() => {}); // best-effort persist
    closeSavePrompt();
  }
  function handleLoadSavedRoster(idx) {
    const sr = savedRosters[idx];
    if (!sr || !Array.isArray(sr.members) || sr.members.length === 0) return;
    // Replace current roster entirely with the saved members (up to MAX_ROWS).
    const restored = sr.members.slice(0, MAX_ROWS).map(m => ({
      color: m.color || "white",
      name: m.name || "",
      initial: m.initial || "",
      steam_id: m.steam_id || "",
    }));
    setRoster(restored);
    setRosterCollapsed(false);
    setResults({});
    setProgress({ done: 0, total: 0 });
  }
  function handleDeleteSavedRoster(idx) {
    const next = removeRoster(savedRosters, idx);
    setSavedRosters(next);
    saveRosters(next).catch(() => {});
  }

  // ── Render ──────────────────────────────────────────────────────────────
  return (
    <>
      <PageHead crumb="Leaderboard Tools" title="MULTI" accentWord="COMPARE" />
      <div style={S.scrollBody}>
      <section style={S.section}>
        <SectionHeader
          label="Roster"
          collapsed={sectionsCollapsed.roster}
          onToggle={() => toggleSection("roster")}
        />
        {!sectionsCollapsed.roster && (rosterCollapsed ? (
          <CollapsedRoster roster={roster} onExpand={() => setRosterCollapsed(false)} />
        ) : (
          <>
            <SavedRostersBar
              rosters={savedRosters}
              onLoad={handleLoadSavedRoster}
              onDelete={handleDeleteSavedRoster}
            />
            <RosterTable
              roster={roster}
              savedProfiles={savedProfiles}
              idCounts={idCounts}
              onUpdateRow={updateRow}
              onRemoveRow={removeRow}
              onApplyProfile={applyProfileToRow}
            />
            <div style={S.rosterControls}>
              <button
                type="button"
                style={S.btn}
                onClick={addRow}
                disabled={roster.length >= MAX_ROWS}
              >
                + add player
              </button>
              <span style={S.muted}>{roster.length} / {MAX_ROWS}</span>
              <button
                type="button"
                style={S.btn}
                onClick={() => setRosterCollapsed(true)}
                title="Hide the roster fields"
              >
                ▴ collapse
              </button>
              <button
                type="button"
                style={S.btn}
                onClick={openSavePrompt}
                disabled={validRoster.length === 0 || savedRosters.length >= MAX_ROSTERS}
                title={
                  validRoster.length === 0 ? "Need at least one valid roster row"
                  : savedRosters.length >= MAX_ROSTERS ? `Limit: ${MAX_ROSTERS} saved rosters`
                  : "Save current roster"
                }
              >
                ★ save roster
              </button>
              {savedRosters.length >= MAX_ROSTERS && (
                <span style={{ ...S.muted, color: "var(--warn, #f5a623)" }}>
                  {savedRosters.length}/{MAX_ROSTERS} saved — delete one in Settings to save more.
                </span>
              )}
              <span style={{ flex: 1 }} />
              <span style={S.muted}>{validRoster.length} valid steamID{validRoster.length === 1 ? "" : "s"}</span>
            </div>
            {savePromptOpen && (
              <SaveRosterPrompt
                nickname={savePromptNickname}
                onNicknameChange={setSavePromptNickname}
                error={savePromptError}
                onSubmit={handleSaveRosterSubmit}
                onCancel={closeSavePrompt}
                validCount={validRoster.length}
              />
            )}
          </>
        ))}
      </section>

      <section style={S.section}>
        <SectionHeader
          label="Search Mode"
          collapsed={sectionsCollapsed.view}
          onToggle={() => toggleSection("view")}
        />
        {!sectionsCollapsed.view && (<>
        <ModeSelector
          mode={mode}
          onModeChange={setMode}
          levels={levels}
          chapters={chapters}
          levelTarget={levelTarget}
          onLevelTargetChange={setLevelTarget}
          chapterTarget={chapterTarget}
          onChapterTargetChange={setChapterTarget}
        />
        <div style={S.runControls}>
          {running
            ? <Btn kind="danger" size="lg" onClick={handleStop}>Stop</Btn>
            : <Btn kind="primary" size="lg" icn="compare" onClick={handleRun} disabled={!canRun}>Run</Btn>}
          {running && progress.total > 0 && (
            <span style={S.muted}>
              {progress.done} / {progress.total}
            </span>
          )}
        </div>
        </>)}
      </section>

      <section style={S.section}>
        <SectionHeader
          label="Result"
          collapsed={sectionsCollapsed.result}
          onToggle={() => toggleSection("result")}
        />
        {!sectionsCollapsed.result && (mode === "level" ? (
          <LevelRankTable levelTarget={levelTarget} roster={roster} results={results} />
        ) : mode === "chapter" ? (
          <ChapterStrip
            chapterTarget={chapterTarget}
            chapters={chapters}
            roster={roster}
            results={results}
            onCellClick={setDrilldownLevel}
          />
        ) : (
          <WholeGameGrid
            chapters={chapters}
            roster={roster}
            results={results}
            onCellClick={setDrilldownLevel}
          />
        ))}
      </section>

      </div>
      <LevelDrilldownDrawer
        levelDisplay={drilldownLevel}
        roster={roster}
        results={results}
        onClose={() => setDrilldownLevel(null)}
      />
    </>
  );
}

// ── Section header (click to collapse/expand) ─────────────────────────────
function SectionHeader({ label, collapsed, onToggle }) {
  return (
    <button type="button" onClick={onToggle} style={S.sectionHeaderBtn} aria-expanded={!collapsed}>
      <span style={S.sectionChevron}>{collapsed ? "▸" : "▾"}</span>
      <span className="field-label">{label}</span>
    </button>
  );
}

// ── Saved Rosters bar (top of roster section) ─────────────────────────────
function SavedRostersBar({ rosters, onLoad, onDelete }) {
  const [open, setOpen] = useState(false);
  const wrapRef = useRef(null);

  useEffect(() => {
    if (!open) return;
    function onDocClick(e) {
      if (wrapRef.current && !wrapRef.current.contains(e.target)) setOpen(false);
    }
    function onKey(e) { if (e.key === "Escape") setOpen(false); }
    document.addEventListener("mousedown", onDocClick);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDocClick);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  function handlePick(idx) {
    onLoad(idx);
    setOpen(false);
  }
  function handleDelete(e, idx) {
    e.stopPropagation();
    if (window.confirm(`Delete saved roster "${rosters[idx]?.nickname}"?`)) onDelete(idx);
  }

  return (
    <div style={S.savedRostersBar}>
      <div ref={wrapRef} style={{ position: "relative", display: "inline-block" }}>
        <button type="button" style={S.btn} onClick={() => setOpen(o => !o)}>
          ▾ saved rosters ({rosters.length})
        </button>
        {open && (
          <div style={S.savedRostersMenu}>
            {rosters.length === 0 ? (
              <div style={S.savedRosterEmpty}>
                No saved rosters yet — fill in players, then click ★ save roster.
              </div>
            ) : (
              rosters.slice().reverse().map((r, revIdx) => {
                const idx = rosters.length - 1 - revIdx; // original index
                return (
                  <div key={idx} style={S.savedRosterRow}>
                    <button
                      type="button"
                      style={S.savedRosterPick}
                      onClick={() => handlePick(idx)}
                      title="Load this roster (replaces current rows)"
                    >
                      <span style={S.savedRosterNick}>{r.nickname}</span>
                      <span style={S.savedRosterMeta}>
                        {(r.members || []).length} player{(r.members || []).length === 1 ? "" : "s"}
                      </span>
                    </button>
                    <button
                      type="button"
                      style={S.savedRosterDel}
                      onClick={(e) => handleDelete(e, idx)}
                      title="Delete this saved roster"
                    >
                      ✕
                    </button>
                  </div>
                );
              })
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// ── Inline "Save Roster" prompt ────────────────────────────────────────────
function SaveRosterPrompt({ nickname, onNicknameChange, error, onSubmit, onCancel, validCount }) {
  const inputRef = useRef(null);
  useEffect(() => { inputRef.current && inputRef.current.focus(); }, []);
  function onKey(e) {
    if (e.key === "Enter") onSubmit();
    else if (e.key === "Escape") onCancel();
  }
  return (
    <div style={S.savePrompt}>
      <span style={S.muted}>
        Save these {validCount} player{validCount === 1 ? "" : "s"} as a roster:
      </span>
      <input
        ref={inputRef}
        style={S.input}
        value={nickname}
        onChange={(e) => onNicknameChange(e.target.value)}
        onKeyDown={onKey}
        placeholder="Roster name (e.g. Top 5 friends)"
        maxLength={32}
      />
      <button type="button" style={S.btnPrimary} onClick={onSubmit}>save</button>
      <button type="button" style={S.btn} onClick={onCancel}>cancel</button>
      {error && <span style={S.savePromptError}>{error}</span>}
    </div>
  );
}

// ── Collapsed roster (post-run summary) ─────────────────────────────────
function CollapsedRoster({ roster, onExpand }) {
  const filled = roster.filter(r => (r.steam_id || "").trim());
  return (
    <div style={S.collapsedRoster}>
      <div style={S.collapsedPills}>
        {filled.length === 0 ? (
          <span style={S.muted}>No players in roster</span>
        ) : (
          filled.map((r, i) => (
            <span key={i} style={S.pill}>
              <span style={{ ...S.swatchSmall, background: hexFor(r.color) }} />
              <span>{r.name || `(${r.steam_id.slice(-4)})`}</span>
            </span>
          ))
        )}
      </div>
      <button type="button" style={S.btn} onClick={onExpand}>
        ▾ edit roster
      </button>
    </div>
  );
}

// ── Roster table ─────────────────────────────────────────────────────────
function RosterTable({ roster, savedProfiles, idCounts, onUpdateRow, onRemoveRow, onApplyProfile }) {
  const usedColors = roster.map(r => r.color);
  return (
    <div style={S.roster}>
      <div style={{ ...S.rosterRow, ...S.rosterHeader }}>
        <span style={S.colColor}>color</span>
        <span style={S.colName}>name</span>
        <span style={S.colInitial}>init</span>
        <span style={S.colSteamId}>steam id</span>
        <span style={S.colActions}></span>
      </div>
      {roster.map((row, idx) => {
        const trimmedId = (row.steam_id || "").trim();
        const formatOk = STEAM_ID_RE.test(trimmedId);
        const isDup = trimmedId && (idCounts?.[trimmedId] || 0) > 1;
        const errorBorder = (trimmedId && !formatOk) || isDup;
        const disabledIds = new Set(
          roster.filter((_, i) => i !== idx)
                .map(r => (r.steam_id || "").trim())
                .filter(Boolean)
        );
        return (
          <div key={idx} style={S.rosterRow}>
            <span style={S.colColor}>
              <ColorPicker
                value={row.color}
                onChange={(c) => onUpdateRow(idx, { color: c })}
                disallowed={usedColors.filter((c, i) => i !== idx)}
              />
            </span>
            <input
              style={S.input}
              value={row.name}
              onChange={(e) => onUpdateRow(idx, { name: e.target.value, initial: deriveInitial(e.target.value) })}
              placeholder="Player 1"
            />
            <input
              style={{ ...S.input, ...S.colInitial }}
              value={row.initial}
              onChange={(e) => onUpdateRow(idx, { initial: (e.target.value || "").slice(0, 2).toUpperCase() })}
              maxLength={2}
              placeholder="1"
            />
            <input
              style={{
                ...S.input,
                ...S.colSteamId,
                borderColor: errorBorder ? "#ef4444" : "var(--border)",
              }}
              value={row.steam_id}
              onChange={(e) => onUpdateRow(idx, { steam_id: e.target.value.trim() })}
              placeholder="76561198…"
              title={isDup ? "Duplicate of another row" : (trimmedId && !formatOk ? "Must be 17 digits" : undefined)}
            />
            <span style={S.colActions}>
              <SavedProfilesDropdown
                profiles={savedProfiles}
                onSelect={(p) => onApplyProfile(idx, p)}
                disabledIds={disabledIds}
              />
              <button
                type="button"
                style={S.btnDanger}
                onClick={() => onRemoveRow(idx)}
                disabled={roster.length <= MIN_ROWS}
                title={roster.length <= MIN_ROWS ? "Need at least 1 row" : "Remove this row"}
              >
                −
              </button>
            </span>
          </div>
        );
      })}
    </div>
  );
}

// ── Color picker (inline popover) ────────────────────────────────────────
function ColorPicker({ value, onChange, disallowed = [] }) {
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
        onClick={() => setOpen(o => !o)}
        style={{ ...S.swatch, background: hexFor(value) }}
        title={`color: ${value}`}
      />
      {open && (
        <div style={S.swatchMenu}>
          {PLAYER_COLORS.map(c => {
            const taken = disSet.has(c.key) && c.key !== value;
            return (
              <button
                key={c.key}
                type="button"
                onClick={() => { if (!taken) { onChange(c.key); setOpen(false); } }}
                disabled={taken}
                title={taken ? `${c.label} (in use)` : c.label}
                style={{
                  ...S.swatchOption,
                  background: c.hex,
                  opacity: taken ? 0.25 : 1,
                  outline: c.key === value ? "2px solid var(--accent)" : "none",
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

// ── Mode selector ────────────────────────────────────────────────────────
function ModeSelector({ mode, onModeChange, levels, chapters, levelTarget, onLevelTargetChange, chapterTarget, onChapterTargetChange }) {
  return (
    <div style={S.modeWrap}>
      <Seg
        options={["level", "chapter", "game"]}
        value={mode}
        onChange={onModeChange}
      />
      <div style={S.modeTarget}>
        {mode === "level" && (
          <select
            className="input"
            style={{ minWidth: 220 }}
            value={levelTarget}
            onChange={(e) => onLevelTargetChange(e.target.value)}
          >
            {levels.map(lv => <option key={lv.internal} value={lv.display}>{lv.display}</option>)}
          </select>
        )}
        {mode === "chapter" && (
          <select
            className="input"
            style={{ minWidth: 220 }}
            value={chapterTarget}
            onChange={(e) => onChapterTargetChange(e.target.value)}
          >
            {Object.keys(chapters).map(k => <option key={k} value={k}>{k}</option>)}
          </select>
        )}
        {mode === "game" && <span style={S.muted}>all 121 levels</span>}
      </div>
    </div>
  );
}

// ── Level mode renderer ──────────────────────────────────────────────────
function LevelRankTable({ levelTarget, roster, results, hideTitle = false }) {
  const rosterById = useMemo(() => {
    const map = {};
    roster.forEach(r => {
      const id = (r.steam_id || "").trim();
      if (id) map[id] = r;
    });
    return map;
  }, [roster]);

  const levelRows = useMemo(
    () => Object.values(results).filter(r => r.level_display === levelTarget),
    [results, levelTarget]
  );

  const { ranked, missing, firstTime } = useMemo(() => {
    const present = levelRows.filter(r => !r.missing).slice().sort((a, b) => a.time_us - b.time_us);
    let lastTime = null;
    let rank = 0;
    const rankedList = present.map(r => {
      if (r.time_us !== lastTime) {
        rank++;
        lastTime = r.time_us;
      }
      return { ...r, displayRank: rank };
    });
    return {
      ranked: rankedList,
      missing: levelRows.filter(r => r.missing),
      firstTime: rankedList.length ? rankedList[0].time_us : null,
    };
  }, [levelRows]);

  if (!levelTarget) {
    return <div style={S.placeholder}><span className="muted">Select a level.</span></div>;
  }
  if (levelRows.length === 0) {
    return (
      <div style={S.placeholder}>
        <span className="muted">No results yet for "{levelTarget}". Press Run.</span>
      </div>
    );
  }

  function rowPlayerCell(r) {
    const rosterRow = rosterById[r.steam_id];
    const name = rosterRow?.name || `(${r.steam_id.slice(-4)})`;
    const color = rosterRow?.color || "white";
    return (
      <span style={S.playerCell}>
        <span style={{ ...S.swatchSmall, background: hexFor(color) }} />
        <span>{name}</span>
      </span>
    );
  }

  return (
    <div>
      {!hideTitle && <div style={S.levelTitle}>{levelTarget}</div>}
      <table style={S.rankTable}>
        <thead>
          <tr>
            <th style={{ ...S.th, ...S.thNum }}>#</th>
            <th style={S.th}>player</th>
            <th style={{ ...S.th, ...S.thRight }}>time</th>
            <th style={{ ...S.th, ...S.thRight }}>Δ vs above</th>
            <th style={{ ...S.th, ...S.thRight }}>Δ vs 1st</th>
            <th style={{ ...S.th, ...S.thRight }}>LB rank</th>
          </tr>
        </thead>
        <tbody>
          {ranked.map((r, i) => {
            const above = i > 0 ? ranked[i - 1] : null;
            const gapAbove = above && above.time_us !== r.time_us ? r.time_us - above.time_us : null;
            const gapFirst = r.time_us !== firstTime ? r.time_us - firstTime : null;
            const isTie = above && above.time_us === r.time_us;
            return (
              <tr key={r.steam_id} style={isTie ? S.tieRow : null}>
                <td style={{ ...S.td, ...S.tdNum }}>{r.displayRank}</td>
                <td style={S.td}>{rowPlayerCell(r)}</td>
                <td style={{ ...S.td, ...S.tdMono, ...S.tdRight }}>{formatTimeUs(r.time_us)}</td>
                <td style={{ ...S.td, ...S.tdMono, ...S.tdRight, ...S.tdMuted }}>
                  {gapAbove == null ? (i === 0 ? "—" : "tie") : formatGapUs(gapAbove)}
                </td>
                <td style={{ ...S.td, ...S.tdMono, ...S.tdRight, ...S.tdMuted }}>
                  {gapFirst == null ? "—" : formatGapUs(gapFirst)}
                </td>
                <td style={{ ...S.td, ...S.tdMono, ...S.tdRight, ...S.tdMuted }}>#{r.rank}</td>
              </tr>
            );
          })}
          {missing.map(r => (
            <tr key={r.steam_id + "-miss"} style={S.missingRow}>
              <td style={{ ...S.td, ...S.tdNum, ...S.tdMuted }}>—</td>
              <td style={S.td}>{rowPlayerCell(r)}</td>
              <td colSpan={4} style={{ ...S.td, ...S.tdMuted, fontStyle: "italic" }}>
                no time on this level
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ── Chapter mode renderer ────────────────────────────────────────────────
const CHAPTER_STRIP_WIDTH = 10;

function resolveCell(display, rosterById, results) {
  if (!display) return { kind: "structural" };
  const rosterIds = new Set(Object.keys(rosterById));
  const matching = Object.values(results)
    .filter(r => r.level_display === display && rosterIds.has(r.steam_id));
  const present = matching.filter(r => !r.missing).slice().sort((a, b) => a.time_us - b.time_us);
  if (present.length === 0) return { kind: "missing", display };
  const fastest = present[0].time_us;
  const winners = present.filter(r => r.time_us === fastest);
  if (winners.length === 1) {
    return {
      kind: "winner",
      display,
      color: rosterById[winners[0].steam_id]?.color || "white",
      time_us: fastest,
      steam_id: winners[0].steam_id,
    };
  }
  return {
    kind: "tie",
    display,
    colors: winners.map(w => rosterById[w.steam_id]?.color || "white"),
    time_us: fastest,
    steam_ids: winners.map(w => w.steam_id),
  };
}

function ChapterStrip({ chapterTarget, chapters, roster, results, onCellClick }) {
  const rosterById = useMemo(() => {
    const map = {};
    roster.forEach(r => {
      const id = (r.steam_id || "").trim();
      if (id) map[id] = r;
    });
    return map;
  }, [roster]);

  const levelDisplays = chapters[chapterTarget] || [];

  if (!chapterTarget) {
    return <div style={S.placeholder}><span className="muted">Select a chapter.</span></div>;
  }

  const cells = [];
  for (let i = 0; i < CHAPTER_STRIP_WIDTH; i++) {
    const display = i < levelDisplays.length ? levelDisplays[i] : null;
    cells.push(resolveCell(display, rosterById, results));
  }

  const anyData = cells.some(c => c.kind === "winner" || c.kind === "tie");

  return (
    <div>
      <div style={S.chapterHeader}>
        <div style={S.levelTitle}>{chapterTarget}</div>
        <span style={S.muted}>
          {levelDisplays.length} level{levelDisplays.length === 1 ? "" : "s"}
          {levelDisplays.length < CHAPTER_STRIP_WIDTH
            ? ` · ${CHAPTER_STRIP_WIDTH - levelDisplays.length} structural cells`
            : ""}
        </span>
      </div>
      <div style={S.chapterStrip}>
        {cells.map((cell, i) => (
          <ChapterCell key={i} cell={cell} onClick={onCellClick} />
        ))}
      </div>
      {!anyData && (
        <div style={{ marginTop: 14 }}>
          <span style={S.muted}>No results yet. Press Run.</span>
        </div>
      )}
      <RosterLegend roster={roster} />
    </div>
  );
}

function ChapterCell({ cell, onClick }) {
  if (cell.kind === "structural") {
    return <div style={{ ...S.cell, ...S.cellStructural }} />;
  }

  const handleClick = () => onClick && onClick(cell.display);

  let bg, outline, subtext;
  if (cell.kind === "missing") {
    bg = undefined;
    subtext = "no time loaded";
  } else if (cell.kind === "tie") {
    const stops = cell.colors.map((c, i, arr) => {
      const start = (i * 100) / arr.length;
      const end = ((i + 1) * 100) / arr.length;
      return `${hexFor(c)} ${start}%, ${hexFor(c)} ${end}%`;
    }).join(", ");
    bg = `linear-gradient(135deg, ${stops})`;
    outline = "1px solid rgba(192,132,252,0.5)";
    subtext = `tie @ ${formatTimeUs(cell.time_us)}`;
  } else {
    bg = hexFor(cell.color);
    subtext = formatTimeUs(cell.time_us);
  }

  const buttonStyle = {
    ...S.cellBtn,
    ...(cell.kind === "missing" ? S.cellMissing : null),
    ...(bg ? { background: bg } : null),
    ...(outline ? { outline } : null),
  };

  return (
    <button
      type="button"
      className="heatmap-cell"
      onClick={handleClick}
      style={buttonStyle}
      aria-label={`${cell.display}, ${cell.kind}`}
    >
      <span className="heatmap-tooltip">
        <span className="ht-name">{cell.display}</span>
        <span className="ht-sub">{subtext}</span>
      </span>
    </button>
  );
}

// ── Whole Game mode renderer ─────────────────────────────────────────────
function chapterShortLabel(key) {
  const [head, tail] = key.split(/\s*-\s*/, 2);
  if (/^\d+$/.test(head)) return `Ch ${head}`;
  if (head.toLowerCase().startsWith("sidequest")) return (tail || "").trim();
  return key;
}

function WholeGameGrid({ chapters, roster, results, onCellClick }) {
  const rosterById = useMemo(() => {
    const map = {};
    roster.forEach(r => {
      const id = (r.steam_id || "").trim();
      if (id) map[id] = r;
    });
    return map;
  }, [roster]);

  const chapterKeys = Object.keys(chapters);
  if (chapterKeys.length === 0) {
    return <div style={S.placeholder}><span className="muted">No chapter data.</span></div>;
  }

  const anyData = Object.values(results).some(r => !r.missing);

  return (
    <div>
      <div style={S.wholeGameWrap}>
        {chapterKeys.map(key => {
          const levelDisplays = chapters[key];
          const cells = [];
          for (let i = 0; i < CHAPTER_STRIP_WIDTH; i++) {
            const display = i < levelDisplays.length ? levelDisplays[i] : null;
            cells.push(resolveCell(display, rosterById, results));
          }
          return (
            <div key={key} style={S.wholeGameRow}>
              <div style={S.wholeGameRowLabel} title={key}>{chapterShortLabel(key)}</div>
              <div style={S.chapterStrip}>
                {cells.map((cell, i) => (
                  <ChapterCell key={i} cell={cell} onClick={onCellClick} />
                ))}
              </div>
            </div>
          );
        })}
      </div>
      {!anyData && (
        <div style={{ marginTop: 14 }}>
          <span style={S.muted}>No results yet. Press Run.</span>
        </div>
      )}
      <RosterLegend roster={roster} />
    </div>
  );
}

function RosterLegend({ roster }) {
  const named = roster.filter(r => (r.steam_id || "").trim() && (r.name || "").trim());
  if (named.length === 0) return null;
  return (
    <div style={S.legend}>
      {named.map((r, i) => (
        <span key={i} style={S.legendItem}>
          <span style={{ ...S.swatchSmall, background: hexFor(r.color) }} />
          <span>{r.name}</span>
        </span>
      ))}
    </div>
  );
}

// ── Level drill-down drawer (used by Chapter and Whole Game cells) ───────
function LevelDrilldownDrawer({ levelDisplay, roster, results, onClose }) {
  const open = !!levelDisplay;

  useEffect(() => {
    if (!open) return;
    function onKey(e) { if (e.key === "Escape") onClose(); }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  const [lastLevel, setLastLevel] = useState(levelDisplay);
  useEffect(() => {
    if (levelDisplay) setLastLevel(levelDisplay);
  }, [levelDisplay]);

  return (
    <div
      style={{
        ...S.drawer,
        transform: open ? "translateX(0)" : "translateX(100%)",
        pointerEvents: open ? "auto" : "none",
      }}
      aria-hidden={!open}
    >
      <div style={S.drawerHeader}>
        <div style={S.drawerTitleWrap}>
          <span style={S.drawerKicker}>level detail</span>
          <span style={S.drawerTitle}>{lastLevel || ""}</span>
        </div>
        <button type="button" style={S.drawerClose} onClick={onClose} aria-label="Close drawer">
          ×
        </button>
      </div>
      <div style={S.drawerBody}>
        {lastLevel && (
          <LevelRankTable
            levelTarget={lastLevel}
            roster={roster}
            results={results}
            hideTitle
          />
        )}
      </div>
    </div>
  );
}

// ── Styles ───────────────────────────────────────────────────────────────
const S = {
  scrollBody: { flex: 1, overflow: "auto", padding: 24, minHeight: 0, scrollbarGutter: "stable" },
  section: {
    background: "var(--surface-2)", border: "1px solid var(--border)", borderRadius: 4,
    padding: 16, marginBottom: 16,
    display: "flex", flexDirection: "column", gap: 12,
  },
  sectionHeaderBtn: {
    display: "flex", alignItems: "center", gap: 8,
    background: "transparent", border: "none", padding: 0,
    cursor: "pointer", width: "100%",
    textAlign: "left",
    fontFamily: "inherit",  // <button> resets font; restore page font for .field-label inside
    color: "inherit",
  },
  sectionChevron: {
    color: "var(--text-3)", fontSize: 10, lineHeight: 1,
    width: 12, display: "inline-block",
  },
  muted: { color: "var(--text-3)", fontSize: 12 },

  // Roster
  roster: { display: "flex", flexDirection: "column", gap: 4 },
  rosterRow: {
    display: "grid",
    gridTemplateColumns: "32px 1fr 50px 200px 130px",
    gap: 8, alignItems: "center",
  },
  rosterHeader: { color: "var(--text-3)", fontSize: 10, textTransform: "uppercase", letterSpacing: 1, paddingBottom: 4 },
  colColor: { display: "flex", justifyContent: "center" },
  colName: {},
  colInitial: { textAlign: "center" },
  colSteamId: {},
  colActions: { display: "flex", gap: 6, alignItems: "center" },
  rosterControls: { display: "flex", gap: 12, alignItems: "center", marginTop: 12, flexWrap: "wrap" },

  // Saved rosters bar (top of roster section)
  savedRostersBar: { marginBottom: 10 },
  savedRostersMenu: {
    position: "absolute", top: "100%", left: 0, marginTop: 4, minWidth: 280, maxWidth: 380,
    background: "var(--surface-2)", border: "1px solid var(--border)", borderRadius: 3,
    boxShadow: "0 4px 12px rgba(0,0,0,0.4)", padding: 4, zIndex: 100,
    display: "flex", flexDirection: "column", gap: 2,
    maxHeight: 320, overflowY: "auto",
  },
  savedRosterEmpty: { padding: "12px 10px", color: "var(--text-3)", fontSize: 11 },
  savedRosterRow: {
    display: "flex", gap: 4, alignItems: "stretch",
  },
  savedRosterPick: {
    flex: 1, background: "transparent", color: "var(--text)", border: "none",
    padding: "6px 10px", fontFamily: "var(--data-font)", fontSize: 12, cursor: "pointer",
    textAlign: "left", display: "flex", justifyContent: "space-between", alignItems: "center",
    gap: 12, borderRadius: 2,
  },
  savedRosterNick: {},
  savedRosterMeta: { color: "var(--text-3)", fontSize: 11 },
  savedRosterDel: {
    background: "transparent", color: "var(--text-3)", border: "none",
    padding: "0 8px", fontSize: 13, cursor: "pointer", borderRadius: 2,
  },

  // Inline save-roster prompt
  savePrompt: {
    display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap",
    marginTop: 10, padding: 10,
    border: "1px dashed var(--border)", borderRadius: 3,
  },
  savePromptError: {
    color: "var(--bad, #f87171)", fontSize: 11, flexBasis: "100%",
  },
  collapsedRoster: { display: "flex", alignItems: "center", gap: 16, flexWrap: "wrap" },
  collapsedPills: { display: "flex", gap: 8, flexWrap: "wrap", flex: 1, minWidth: 0 },
  pill: {
    display: "inline-flex", alignItems: "center", gap: 8,
    background: "var(--bg-2)", border: "1px solid var(--border)",
    padding: "4px 12px", borderRadius: 14, fontSize: 12,
  },

  input: {
    background: "var(--bg-2)", color: "var(--text)", border: "1px solid var(--border)",
    padding: "4px 8px", fontFamily: "var(--data-font)", fontSize: 13, borderRadius: 2,
    minWidth: 0,
  },

  // Color swatch
  swatch: {
    width: 24, height: 24, border: "2px solid var(--border)", borderRadius: 4, cursor: "pointer",
    padding: 0,
  },
  swatchMenu: {
    position: "absolute", top: "100%", left: 0, marginTop: 4, zIndex: 100,
    background: "var(--surface-2)", border: "1px solid var(--border)", borderRadius: 4, padding: 6,
    display: "grid", gridTemplateColumns: "repeat(5, 24px)", gap: 6,
    boxShadow: "0 4px 12px rgba(0,0,0,0.4)",
  },
  swatchOption: {
    width: 24, height: 24, border: "1px solid var(--border)", borderRadius: 3, padding: 0,
  },

  // Mode
  modeWrap: { display: "flex", gap: 16, alignItems: "center", flexWrap: "wrap", minHeight: 32 },
  modeTarget: { display: "flex", gap: 8, alignItems: "center", minHeight: 32 },

  // Run controls
  runControls: { display: "flex", gap: 12, alignItems: "center", marginTop: 12 },
  btn: {
    background: "var(--bg-2)", color: "var(--text)", border: "1px solid var(--border)",
    padding: "5px 12px", fontFamily: "var(--data-font)", fontSize: 12, cursor: "pointer",
    borderRadius: 3,
  },
  btnPrimary: {
    background: "var(--accent)", color: "#000", border: "1px solid var(--accent)",
    padding: "6px 18px", fontFamily: "var(--data-font)", fontSize: 13, cursor: "pointer",
    borderRadius: 3, fontWeight: 600,
  },
  btnDanger: {
    background: "transparent", color: "var(--text-3)", border: "1px solid var(--border)",
    padding: "2px 8px", fontFamily: "var(--data-font)", fontSize: 14, cursor: "pointer",
    borderRadius: 3,
  },

  // Placeholder
  placeholder: {
    minHeight: 200, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center",
    border: "1px dashed var(--border)", borderRadius: 4, padding: 24,
  },

  // Level rank table
  levelTitle: {
    fontFamily: "var(--display-font)", fontSize: 22, color: "var(--accent)",
    marginBottom: 10, letterSpacing: 1,
  },
  rankTable: {
    width: "100%", borderCollapse: "collapse", fontSize: 13,
  },
  th: {
    textAlign: "left", padding: "6px 10px", color: "var(--text-3)",
    fontSize: 10, textTransform: "uppercase", letterSpacing: 1,
    borderBottom: "1px solid var(--border)", fontWeight: 500,
  },
  thNum: { textAlign: "center", width: 40 },
  thRight: { textAlign: "right" },
  td: { padding: "8px 10px", borderBottom: "1px solid var(--bg-2)" },
  tdNum: { textAlign: "center", fontFamily: "var(--data-font)", color: "var(--accent)", fontWeight: 600 },
  tdMono: { fontFamily: "var(--data-font)" },
  tdRight: { textAlign: "right" },
  tdMuted: { color: "var(--text-3)" },
  tieRow: { background: "rgba(192, 132, 252, 0.06)" },
  missingRow: { opacity: 0.6 },
  playerCell: { display: "inline-flex", alignItems: "center", gap: 8 },
  swatchSmall: {
    display: "inline-block", width: 14, height: 14, borderRadius: 3,
    border: "1px solid var(--border)", flexShrink: 0,
  },

  // Chapter strip
  chapterHeader: { display: "flex", alignItems: "baseline", gap: 16, marginBottom: 10 },
  chapterStrip: {
    display: "grid",
    gridTemplateColumns: "repeat(10, 80px)",
    gap: 4,
  },
  cell: {
    width: 80, height: 60,
    border: "1px solid var(--border)",
    borderRadius: 3,
  },
  cellBtn: {
    width: 80, height: 60,
    border: "1px solid var(--border)",
    borderRadius: 3,
    cursor: "pointer",
    padding: 0,
  },
  cellStructural: {
    background: "#3a3a3a",
    cursor: "default",
  },
  cellMissing: {
    background: `repeating-linear-gradient(
      45deg,
      #4a4a4a,
      #4a4a4a 4px,
      #5a5a5a 4px,
      #5a5a5a 8px
    )`,
  },
  legend: {
    display: "flex", gap: 14, flexWrap: "wrap", marginTop: 14,
    fontSize: 12, color: "var(--text)",
  },
  legendItem: { display: "inline-flex", alignItems: "center", gap: 6 },

  // Whole Game grid
  wholeGameWrap: { display: "flex", flexDirection: "column", gap: 6 },
  wholeGameRow: { display: "flex", gap: 12, alignItems: "center" },
  wholeGameRowLabel: {
    width: 70, flexShrink: 0,
    color: "var(--text-3)", fontSize: 11,
    textTransform: "uppercase", letterSpacing: 1,
    textAlign: "right",
  },

  // Drill-down drawer
  drawer: {
    position: "fixed", top: 0, right: 0, bottom: 0, width: 500,
    background: "var(--surface-2)", borderLeft: "1px solid var(--border)",
    boxShadow: "-8px 0 24px rgba(0,0,0,0.5)",
    display: "flex", flexDirection: "column", zIndex: 200,
    transition: "transform 200ms ease",
  },
  drawerHeader: {
    display: "flex", alignItems: "center", gap: 12,
    padding: "14px 18px", borderBottom: "1px solid var(--border)",
    background: "var(--bg-2)",
  },
  drawerTitleWrap: { display: "flex", flexDirection: "column", flex: 1, minWidth: 0 },
  drawerKicker: {
    fontSize: 10, color: "var(--text-3)", textTransform: "uppercase", letterSpacing: 2,
  },
  drawerTitle: {
    fontFamily: "var(--display-font)", fontSize: 22, color: "var(--accent)",
    whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis",
  },
  drawerClose: {
    background: "transparent", color: "var(--text-3)", border: "1px solid var(--border)",
    width: 32, height: 32, fontSize: 20, lineHeight: 1, borderRadius: 3,
    cursor: "pointer", padding: 0,
  },
  drawerBody: { padding: 18, overflowY: "auto", flex: 1 },
};
