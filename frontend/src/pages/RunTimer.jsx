import React, { useState, useEffect, useRef, useMemo } from "react";
import { getStandardOrder, loadTimerSeed, calculateTimer, getLevels, getChapters } from "../api.js";
import { PageHead, Field, Seg, Btn, RushSelect, ErrorBanner, MedalBadge, MedalToggle, RUSHES } from "../shared.jsx";
import { loadWithRetry } from "../lib/retryLevels.js";
import LevelPickerModal from "../components/LevelPickerModal.jsx";
import { loadCustomRushes, saveCustomRushes, addCustomRush, removeCustomRush } from "../lib/customRushes.js";

const GRID_SIZES = { S: 160, M: 320, L: 500, XL: 720, XXL: 900 };
const LS_SIZE_KEY = "runtimer_grid_size";
const MANUAL_MAX = 121;
const OUT_ROW_H = 27;   // fixed result-row height so the Segment + Level Order columns line up

export default function RunTimer({ showMedals, setShowMedals }) {
  const [rushName, setRushName]     = useState(RUSHES[0].name);
  const [mode, setMode]             = useState("standard"); // standard | seed | manual | custom
  const [seed, setSeed]             = useState("");
  const [rows, setRows]             = useState([]);         // [{name, time}]
  const [result, setResult]         = useState(null);
  const [error, setError]           = useState(null);
  const [loading, setLoading]       = useState(false);
  const [loadingNames, setLoadingNames] = useState(false);
  const [gridSize, setGridSize]     = useState(
    () => localStorage.getItem(LS_SIZE_KEY) || "M"
  );

  // Manual mode: user-set number of free-text rows (no longer pinned to rush size).
  const [manualCount, setManualCount] = useState(8);

  // How the entered/pasted times are interpreted, + bulk-paste-into-column.
  const [timeType, setTimeType]     = useState("cumulative"); // cumulative | segment
  const [pasteOpen, setPasteOpen]   = useState(false);
  const [pasteText, setPasteText]   = useState("");

  // Custom mode: pick stages from the catalog, in a chosen play order.
  const [levels, setLevels]         = useState([]);   // [{display, ...}]
  const [chapters, setChapters]     = useState([]);   // [{name, levels}]
  const [pickerOpen, setPickerOpen] = useState(false);
  const [savedRushes, setSavedRushes] = useState([]);
  const [selectedSaved, setSelectedSaved] = useState("");
  const [customToast, setCustomToast] = useState("");
  const dragIdx = useRef(null);

  function handleSizeChange(size) {
    setGridSize(size);
    localStorage.setItem(LS_SIZE_KEY, size);
  }

  // Catalog for validating saved-rush level names (drop stages that no longer exist).
  const validNames = useMemo(() => new Set(levels.map(l => l.display)), [levels]);

  // Load the level/chapter catalog once (for the custom-mode picker). Static
  // bridge data, but wrapped in loadWithRetry to survive the first-boot race.
  useEffect(() => {
    const cancelLevels   = loadWithRetry(getLevels,   { onData: setLevels });
    const cancelChapters = loadWithRetry(getChapters, { onData: setChapters });
    loadCustomRushes().then(setSavedRushes);
    return () => { cancelLevels?.(); cancelChapters?.(); };
  }, []);

  // Rebuild rows on rush/mode change for standard/seed/custom. Manual sizing is
  // handled by its own effect so it stays decoupled from the rush selector.
  useEffect(() => {
    setResult(null);
    setError(null);
    if (mode === "standard") {
      setLoadingNames(true);
      getStandardOrder(rushName)
        .then(res => { if (res.ok) setRows(res.lines.map(name => ({ name, time: "" }))); })
        .finally(() => setLoadingNames(false));
    } else if (mode === "seed") {
      const count = RUSHES.find(r => r.name === rushName)?.count ?? 96;
      setRows(Array.from({ length: count }, () => ({ name: "", time: "" })));
    } else if (mode === "custom") {
      setRows([]);
      setSelectedSaved("");
      setCustomToast("");
    }
  }, [rushName, mode]);

  // Manual mode: resize the free-text rows to manualCount, preserving entered data.
  useEffect(() => {
    if (mode !== "manual") return;
    setRows(prev => {
      const next = prev.slice(0, manualCount);
      while (next.length < manualCount) next.push({ name: "", time: "" });
      return next;
    });
  }, [manualCount, mode]);

  async function handleLoadSeed() {
    if (!seed.trim()) return;
    setLoadingNames(true);
    setError(null);
    setResult(null);
    const res = await loadTimerSeed(rushName, seed);
    if (res.ok) {
      setRows(prev => res.lines.map((name, i) => ({ name, time: prev[i]?.time ?? "" })));
    } else {
      setError(res.error);
    }
    setLoadingNames(false);
  }

  function updateTime(i, val) {
    setRows(prev => prev.map((r, j) => j === i ? { ...r, time: val } : r));
  }

  function updateName(i, val) {
    setRows(prev => prev.map((r, j) => j === i ? { ...r, name: val } : r));
  }

  // ── Custom mode helpers ──────────────────────────────────────────────────

  // Picker hands back the selected set in catalog order. Keep existing rows whose
  // stage is still selected (preserving play order + entered times); append the
  // newly-selected stages at the end with empty times.
  function reconcileCustomRows(names) {
    setCustomToast("");
    setResult(null);
    setRows(prev => {
      const want = new Set(names);
      const kept = prev.filter(r => want.has(r.name));
      const have = new Set(kept.map(r => r.name));
      const added = names.filter(n => !have.has(n)).map(n => ({ name: n, time: "" }));
      return [...kept, ...added];
    });
  }

  function onDragStart(i) { dragIdx.current = i; }
  function onDrop(i) {
    const from = dragIdx.current;
    dragIdx.current = null;
    if (from === null || from === i) return;
    setResult(null);
    setRows(prev => {
      const next = prev.slice();
      const [moved] = next.splice(from, 1);
      next.splice(i, 0, moved);
      return next;
    });
  }

  function loadSavedRush(name) {
    setSelectedSaved(name);
    if (!name) return;
    const rush = savedRushes.find(r => r.name === name);
    if (!rush) return;
    const known = rush.levels.filter(n => validNames.has(n));
    const dropped = rush.levels.length - known.length;
    setRows(known.map(n => ({ name: n, time: "" })));
    setResult(null);
    setCustomToast(dropped > 0
      ? `${dropped} stage${dropped === 1 ? "" : "s"} in "${name}" no longer exist and were dropped.`
      : "");
  }

  async function handleSaveRush() {
    const names = rows.map(r => r.name).filter(Boolean);
    const name = window.prompt(`Save these ${names.length} stages as a custom rush.\n\nName:`);
    if (name === null) return;
    const res = addCustomRush(savedRushes, name, names);
    if (res.error) { setCustomToast(res.error); return; }
    setSavedRushes(res.list);
    await saveCustomRushes(res.list);
    setSelectedSaved(res.list[0].name);
    setCustomToast("");
  }

  async function handleDeleteRush() {
    if (!selectedSaved) return;
    if (!window.confirm(`Delete custom rush "${selectedSaved}"?`)) return;
    const next = removeCustomRush(savedRushes, selectedSaved);
    setSavedRushes(next);
    await saveCustomRushes(next);
    setSelectedSaved("");
  }

  // Bulk paste: distribute one time per line into the rows' time column, in order.
  // Times only (no names) — names come from the established level order.
  function applyPaste() {
    const lines = pasteText.split("\n").map(s => s.trim()).filter(Boolean);
    setRows(prev => prev.map((r, i) => i < lines.length ? { ...r, time: lines[i] } : r));
    setResult(null);
    setPasteOpen(false);
    setPasteText("");
  }

  async function handleCalculate() {
    setError(null);
    setLoading(true);
    setResult(null);
    const splitsText = rows.map(r => `${r.name || "Level"} ${r.time}`).join("\n");
    try {
      const res = await calculateTimer(rushName, seed, splitsText, timeType === "cumulative");
      if (res.ok) setResult(res);
      else setError(res.error);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }

  function copyTimes() {
    if (!result) return;
    navigator.clipboard.writeText(
      result.rows.map(r => r.segment_fmt).join("\n")
    ).catch(() => {});
  }

  function copySplits() {
    if (!result) return;
    navigator.clipboard.writeText(
      result.rows.map(r => `${r.name}: ${r.segment_fmt}`).join("\n")
    ).catch(() => {});
  }

  function copyMedals() {
    if (!result) return;
    navigator.clipboard.writeText(
      result.rows.map(r => `${r.name}: ${r.segment_fmt}${r.medal ? " " + r.medal : ""}`).join("\n")
    ).catch(() => {});
  }

  function copyNames() {
    if (!result) return;
    navigator.clipboard.writeText(result.rows.map(r => r.name).join("\n")).catch(() => {});
  }

  const isLocked = mode !== "manual";     // names editable only in manual mode
  const isCustom = mode === "custom";

  const rowStyle = (i) => ({
    display: "grid",
    gridTemplateColumns: "22px 1fr 100px",
    gap: 4,
    padding: "2px 6px",
    alignItems: "center",
    background: i % 2 === 0 ? "transparent" : "rgba(255,255,255,0.025)",
  });

  const cellInput = (locked) => ({
    padding: "4px 6px",
    fontSize: 11,
    fontFamily: "var(--ui-font)",
    background: locked ? "transparent" : "var(--surface-2)",
    border: locked ? "1px solid transparent" : "1px solid var(--border)",
    color: locked ? "var(--text-2)" : "var(--text)",
    cursor: locked ? "default" : "text",
    borderRadius: 2,
    width: "100%",
    outline: "none",
  });

  return (
    <>
      <PageHead
        crumb="Rush Tools › Run Timer"
        title="RUN"
        accentWord="TIMER"
        actions={result && <MedalToggle value={showMedals} onChange={setShowMedals} />}
      />
      <div className="body">
        {/* ── Left: form ── */}
        <div className="panel-left">
          <div className="form">
            <Field label="Rush name">
              <RushSelect value={rushName} onChange={v => { setRushName(v); }} />
            </Field>
            <Field label="Level order">
              <Seg options={["standard", "seed", "manual", "custom"]} value={mode} onChange={setMode} />
            </Field>
            {mode === "seed" && (
              <Field label="Seed number">
                <div style={{ display: "flex", gap: 8 }}>
                  <input
                    className="input"
                    value={seed}
                    onChange={e => setSeed(e.target.value)}
                    placeholder="e.g. 1834729104"
                    style={{ flex: 1 }}
                  />
                  <Btn onClick={handleLoadSeed} disabled={loadingNames || !seed.trim()}>
                    {loadingNames ? "…" : "Load"}
                  </Btn>
                </div>
              </Field>
            )}

            {mode === "manual" && (
              <Field label="Number of stages">
                <input
                  className="input"
                  type="number"
                  min={1}
                  max={MANUAL_MAX}
                  value={manualCount}
                  onChange={e => {
                    const n = parseInt(e.target.value, 10);
                    if (Number.isNaN(n)) return;
                    setManualCount(Math.max(1, Math.min(MANUAL_MAX, n)));
                  }}
                  style={{ width: 120 }}
                />
              </Field>
            )}

            {isCustom && (
              <Field label="Build rush" hint={
                <span style={{ fontSize: 10, color: "var(--text-3)" }}>
                  Pick any stages, then drag to set play order. Medals shown where data exists.
                </span>
              }>
                <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                  <div style={{ display: "flex", gap: 8 }}>
                    <Btn onClick={() => setPickerOpen(true)}>
                      {rows.length ? `${rows.length} stage${rows.length === 1 ? "" : "s"} — edit…` : "Pick stages…"}
                    </Btn>
                    {rows.length > 0 && (
                      <Btn kind="ghost" onClick={() => { setRows([]); setResult(null); setSelectedSaved(""); }}>
                        Clear
                      </Btn>
                    )}
                  </div>
                  <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                    <select
                      className="input"
                      value={selectedSaved}
                      onChange={e => loadSavedRush(e.target.value)}
                      style={{ flex: 1 }}
                    >
                      <option value="">Saved rushes…</option>
                      {savedRushes.map(r => (
                        <option key={r.name} value={r.name}>{r.name} ({r.levels.length})</option>
                      ))}
                    </select>
                    <Btn kind="ghost" size="sm" disabled={rows.length === 0} onClick={handleSaveRush}>Save…</Btn>
                    <Btn kind="ghost" size="sm" disabled={!selectedSaved} onClick={handleDeleteRush}>Delete</Btn>
                  </div>
                  {customToast && (
                    <div style={{ fontSize: 11, color: "var(--text-2)", background: "var(--surface-2)",
                                  border: "1px solid var(--border)", borderRadius: 4, padding: "6px 8px" }}>
                      {customToast}
                    </div>
                  )}
                </div>
              </Field>
            )}

            <Field label={`${timeType === "cumulative" ? "Cumulative" : "Segment"} split times`} hint={
              <div style={{ display: "flex", alignItems: "center", gap: 6, marginTop: 2, flexWrap: "wrap" }}>
                <span style={{ fontSize: 10, color: "var(--text-3)" }}>Input window size</span>
                {Object.keys(GRID_SIZES).map(s => (
                  <span key={s}
                    onClick={() => handleSizeChange(s)}
                    style={{
                      padding: "1px 7px", fontSize: 10, borderRadius: 2, cursor: "pointer",
                      border: "1px solid var(--border)",
                      background: gridSize === s ? "var(--accent)" : "var(--surface)",
                      color: gridSize === s ? "#042b1f" : "var(--text-2)",
                      fontWeight: gridSize === s ? 600 : 400,
                    }}>
                    {s}
                  </span>
                ))}
              </div>
            }>
              {/* Times-are toggle + bulk paste */}
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8, flexWrap: "wrap" }}>
                <span style={{ fontSize: 10, color: "var(--text-3)" }}>Times are</span>
                <Seg options={["cumulative", "segment"]} value={timeType} onChange={setTimeType} />
                <Btn kind="ghost" size="sm"
                     disabled={rows.length === 0}
                     onClick={() => setPasteOpen(o => !o)}>
                  {pasteOpen ? "Cancel paste" : "Paste times…"}
                </Btn>
              </div>
              {pasteOpen && (
                <div style={{ marginBottom: 8 }}>
                  <textarea
                    className="input"
                    rows={6}
                    value={pasteText}
                    onChange={e => setPasteText(e.target.value)}
                    placeholder={`One ${timeType} time per line, in level order:\n0:42.13\n1:08.91\n0:55.47\n…`}
                    autoFocus
                  />
                  <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 6 }}>
                    <Btn kind="primary" size="sm" disabled={!pasteText.trim()} onClick={applyPaste}>
                      Fill {rows.length} time{rows.length === 1 ? "" : "s"}
                    </Btn>
                    <span style={{ fontSize: 10, color: "var(--text-3)" }}>
                      Times only — mapped top-to-bottom onto the level order.
                    </span>
                  </div>
                </div>
              )}
              <div style={{
                maxHeight: GRID_SIZES[gridSize], overflowY: "auto",
                border: "1px solid var(--border)", borderRadius: 2,
                background: "var(--bg)",
              }}>
                {/* Sticky header */}
                <div style={{
                  display: "grid", gridTemplateColumns: "22px 1fr 100px",
                  gap: 4, padding: "4px 6px",
                  borderBottom: "1px solid var(--border)",
                  position: "sticky", top: 0,
                  background: "var(--surface)", zIndex: 1,
                }}>
                  <span />
                  <span style={{ fontSize: 9, color: "var(--text-3)", textTransform: "uppercase", letterSpacing: 0.8 }}>
                    Level Name
                  </span>
                  <span style={{ fontSize: 9, color: "var(--text-3)", textTransform: "uppercase", letterSpacing: 0.8 }}>
                    Split Time
                  </span>
                </div>

                {loadingNames ? (
                  <div style={{ padding: "16px 12px", color: "var(--text-3)", fontSize: 11 }}>
                    Loading…
                  </div>
                ) : isCustom && rows.length === 0 ? (
                  <div style={{ padding: "16px 12px", color: "var(--text-3)", fontSize: 11 }}>
                    Pick stages to build your rush.
                  </div>
                ) : rows.map((row, i) => (
                  <div key={i} style={rowStyle(i)}
                       onDragOver={isCustom ? (e => e.preventDefault()) : undefined}
                       onDrop={isCustom ? (() => onDrop(i)) : undefined}>
                    <span
                      draggable={isCustom}
                      onDragStart={isCustom ? (() => onDragStart(i)) : undefined}
                      title={isCustom ? "Drag to reorder" : undefined}
                      style={{ fontSize: 10, color: "var(--text-3)", textAlign: "right",
                               cursor: isCustom ? "grab" : "default", userSelect: "none" }}>
                      {isCustom ? "⠿" : String(i + 1).padStart(2, "0")}
                    </span>
                    <input
                      style={cellInput(isLocked)}
                      value={row.name}
                      readOnly={isLocked}
                      onChange={e => updateName(i, e.target.value)}
                      placeholder={isLocked ? "" : "Level name"}
                    />
                    <input
                      style={{ ...cellInput(false), color: "var(--accent)", fontFamily: "var(--data-font)" }}
                      value={row.time}
                      onChange={e => updateTime(i, e.target.value)}
                      placeholder="0:00.000"
                    />
                  </div>
                ))}
              </div>
            </Field>

            <ErrorBanner message={error} />
            <Btn kind="primary" size="lg" onClick={handleCalculate} disabled={loading || rows.length === 0}>
              {loading ? "Calculating…" : "Calculate Segments"}
            </Btn>
          </div>
        </div>

        {/* ── Right: output ── */}
        <div className="panel-right" style={{ padding: 24, overflow: "auto", display: "flex", flexDirection: "column", gap: 16 }}>
          {result ? (
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, alignItems: "start" }}>

              {/* Segment Times */}
              <div style={{ display: "flex", flexDirection: "column" }}>
                <div style={{
                  display: "flex", alignItems: "center", padding: "7px 12px",
                  background: "var(--surface)", border: "1px solid var(--border)",
                  borderBottom: "none", borderRadius: "2px 2px 0 0",
                }}>
                  <span style={{ fontSize: 10, color: "var(--text-3)", textTransform: "uppercase", letterSpacing: 0.8, flex: 1 }}>
                    Segment Times
                  </span>
                  <div style={{ display: "flex", gap: 6 }}>
                    <Btn kind="ghost" size="sm" icn="copy" onClick={copyTimes}>Times</Btn>
                    <Btn kind="ghost" size="sm" icn="copy" onClick={copySplits}>Splits</Btn>
                    <Btn kind="ghost" size="sm" icn="copy" onClick={copyMedals}>Medals</Btn>
                  </div>
                </div>
                <div style={{ border: "1px solid var(--border)", borderRadius: "0 0 2px 2px" }}>
                  {result.rows.map((r, i) => (
                    <div key={i} style={{
                      display: "flex", alignItems: "center", gap: 8,
                      height: OUT_ROW_H, boxSizing: "border-box", padding: "0 12px",
                      background: i % 2 === 0 ? "transparent" : "rgba(255,255,255,0.025)",
                    }}>
                      <span style={{ fontSize: 10, color: "var(--text-3)", width: 20 }}>
                        {String(i + 1).padStart(2, "0")}
                      </span>
                      <span className="data" style={{ fontSize: 12, width: 72 }}>
                        {r.segment_fmt}
                      </span>
                      {showMedals && <MedalBadge medal={r.medal} />}
                    </div>
                  ))}
                </div>
              </div>

              {/* Level Order */}
              <div style={{ display: "flex", flexDirection: "column" }}>
                <div style={{
                  display: "flex", alignItems: "center", padding: "7px 12px",
                  background: "var(--surface)", border: "1px solid var(--border)",
                  borderBottom: "none", borderRadius: "2px 2px 0 0",
                }}>
                  <span style={{ fontSize: 10, color: "var(--text-3)", textTransform: "uppercase", letterSpacing: 0.8, flex: 1 }}>
                    Level Order
                  </span>
                  <Btn kind="ghost" size="sm" icn="copy" onClick={copyNames}>Names</Btn>
                </div>
                <div style={{ border: "1px solid var(--border)", borderRadius: "0 0 2px 2px" }}>
                  {result.rows.map((r, i) => (
                    <div key={i} style={{
                      display: "flex", alignItems: "center",
                      height: OUT_ROW_H, boxSizing: "border-box", padding: "0 12px",
                      background: i % 2 === 0 ? "transparent" : "rgba(255,255,255,0.025)",
                      fontSize: 12,
                    }}>
                      {r.name}
                    </div>
                  ))}
                </div>
              </div>

            </div>
          ) : (
            <div className="muted" style={{ padding: 32, fontSize: 12, textAlign: "center" }}>
              Enter split times and press Calculate Segments.
            </div>
          )}
        </div>
      </div>

      <LevelPickerModal
        open={pickerOpen}
        onClose={() => setPickerOpen(false)}
        value={rows.map(r => r.name)}
        onChange={reconcileCustomRows}
        levels={levels}
        chapters={chapters}
      />
    </>
  );
}
