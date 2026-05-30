import React, { useState, useEffect, useMemo } from "react";
import { Btn } from "../shared.jsx";
import { loadPresets, savePresets, addPreset, removePreset } from "../lib/customLevels.js";

// Tri-state box glyphs for chapter headers.
const BOX = { all: "☑", partial: "▣", none: "☐" };

export default function LevelPickerModal({ open, onClose, value, onChange, levels, chapters }) {
  const [query, setQuery]       = useState("");
  const [collapsed, setCollapsed] = useState({});   // {chapterName: true} = collapsed
  const [presets, setPresets]   = useState([]);
  const [toast, setToast]       = useState("");

  useEffect(() => {
    if (open) {
      loadPresets().then(setPresets);
      setQuery(""); setToast("");
    }
  }, [open]);

  // name(lowercased) -> catalog index, for stable ordering + membership.
  const catalogOrder = useMemo(() => {
    const m = new Map();
    levels.forEach((l, i) => m.set(l.display, i));
    return m;
  }, [levels]);

  const selected = useMemo(() => new Set(value), [value]);

  // Always hand selections back in canonical catalog order.
  const orderByCatalog = (names) =>
    [...new Set(names)].sort((a, b) =>
      (catalogOrder.get(a) ?? 1e9) - (catalogOrder.get(b) ?? 1e9));

  const emit = (names) => onChange(orderByCatalog(names));

  if (!open) return null;

  const q = query.trim().toLowerCase();
  const matchesLevel = (name) => !q || name.toLowerCase().includes(q);

  // Per-chapter level lists, filtered by search. A chapter whose *name* matches
  // the query shows all its levels.
  const sections = chapters.map(c => {
    const chapterMatches = q && c.name.toLowerCase().includes(q);
    const visible = chapterMatches ? c.levels : c.levels.filter(matchesLevel);
    return { name: c.name, all: c.levels, visible };
  }).filter(s => s.visible.length > 0);

  const chapterState = (chapterLevels) => {
    const n = chapterLevels.filter(l => selected.has(l)).length;
    return n === 0 ? "none" : n === chapterLevels.length ? "all" : "partial";
  };

  function toggleLevel(name) {
    const next = new Set(value);
    next.has(name) ? next.delete(name) : next.add(name);
    emit([...next]);
  }

  function toggleChapter(chapterLevels) {
    const next = new Set(value);
    if (chapterState(chapterLevels) === "all") {
      chapterLevels.forEach(l => next.delete(l));
    } else {
      chapterLevels.forEach(l => next.add(l));
    }
    emit([...next]);
  }

  function applyPreset(p) {
    const known = p.levels.filter(n => catalogOrder.has(n));
    const dropped = p.levels.length - known.length;
    emit(known);
    setToast(dropped > 0
      ? `${dropped} level${dropped === 1 ? "" : "s"} in "${p.name}" no longer exist and were dropped.`
      : "");
  }

  async function handleSavePreset() {
    const name = window.prompt(`Save these ${value.length} levels as a preset.\n\nName:`);
    if (name === null) return;
    const result = addPreset(presets, name, value);
    if (result.error) { setToast(result.error); return; }
    setPresets(result.list);
    await savePresets(result.list);
    setToast("");
  }

  async function handleDeletePreset(name) {
    if (!window.confirm(`Delete preset "${name}"?`)) return;
    const next = removePreset(presets, name);
    setPresets(next);
    await savePresets(next);
  }

  const TriBox = ({ state }) => (
    <span style={{ fontSize: 15, color: state === "none" ? "var(--text-3)" : "var(--accent)", width: 16, display: "inline-block" }}>
      {BOX[state]}
    </span>
  );

  return (
    <div className="lpm-overlay" onMouseDown={onClose}>
      <div className="lpm-modal" onMouseDown={e => e.stopPropagation()}>
        {/* Header */}
        <div className="lpm-row" style={{ borderBottom: "1px solid var(--border)", paddingBottom: 10 }}>
          <strong style={{ fontSize: 14 }}>Pick levels</strong>
          <span style={{ color: "var(--text-2)", fontSize: 12, marginLeft: "auto" }}>
            {value.length} / {levels.length} selected
          </span>
          <button className="lpm-x" onClick={onClose} title="Close">✕</button>
        </div>

        {/* Toolbar */}
        <div className="lpm-row" style={{ paddingTop: 10 }}>
          <input className="input" style={{ flex: 1 }} placeholder="Search levels…"
                 value={query} onChange={e => setQuery(e.target.value)} autoFocus />
          <Btn kind="ghost" size="sm" onClick={() => emit([])}>Clear all</Btn>
          <Btn kind="ghost" size="sm" onClick={() => emit(levels.map(l => l.display))}>Select all</Btn>
        </div>

        {toast && (
          <div style={{ fontSize: 11, color: "var(--text-2)", background: "var(--surface-2)",
                        border: "1px solid var(--border)", borderRadius: 4, padding: "6px 8px", marginTop: 8 }}>
            {toast}
          </div>
        )}

        {/* Body — chapter sections */}
        <div className="lpm-body">
          {sections.length === 0 && (
            <div className="muted" style={{ padding: 20, textAlign: "center", fontSize: 12 }}>
              No levels match “{query}”.
            </div>
          )}
          {sections.map(s => {
            const isCollapsed = collapsed[s.name];
            return (
              <div key={s.name} style={{ marginBottom: 6 }}>
                <div className="lpm-chapter">
                  <span style={{ cursor: "pointer", userSelect: "none", color: "var(--text-3)", width: 14 }}
                        onClick={() => setCollapsed(c => ({ ...c, [s.name]: !c[s.name] }))}>
                    {isCollapsed ? "▸" : "▾"}
                  </span>
                  <span style={{ flex: 1, fontWeight: 600, fontSize: 12 }}>{s.name}</span>
                  <span style={{ fontSize: 11, color: "var(--text-3)" }}>
                    {s.all.filter(l => selected.has(l)).length}/{s.all.length}
                  </span>
                  <span className="lpm-item" style={{ padding: "2px 6px" }}
                        onClick={() => toggleChapter(s.all)} title="Toggle all in chapter">
                    <TriBox state={chapterState(s.all)} />
                  </span>
                </div>
                {!isCollapsed && s.visible.map(name => (
                  <div key={name} className="lpm-item" onClick={() => toggleLevel(name)}>
                    <span style={{ width: 16, color: selected.has(name) ? "var(--accent)" : "var(--text-3)", fontSize: 14 }}>
                      {selected.has(name) ? "☑" : "☐"}
                    </span>
                    <span style={{ fontSize: 12 }}>{name}</span>
                  </div>
                ))}
              </div>
            );
          })}
        </div>

        {/* Presets */}
        <div style={{ borderTop: "1px solid var(--border)", paddingTop: 10, marginTop: 4 }}>
          <div style={{ fontSize: 10, textTransform: "uppercase", letterSpacing: 0.5, color: "var(--text-3)", marginBottom: 6 }}>
            Presets
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 6, alignItems: "center" }}>
            {presets.map(p => (
              <span key={p.name} className="lpm-preset">
                <span onClick={() => applyPreset(p)} title={`Load ${p.levels.length} levels`}>
                  {p.name}
                </span>
                <span className="lpm-preset-x" onClick={() => handleDeletePreset(p.name)} title="Delete preset">×</span>
              </span>
            ))}
            <Btn kind="ghost" size="sm" disabled={value.length === 0} onClick={handleSavePreset}>+ Save as…</Btn>
          </div>
        </div>

        {/* Footer */}
        <div className="lpm-row" style={{ justifyContent: "flex-end", paddingTop: 12 }}>
          <Btn kind="primary" size="sm" onClick={onClose}>Done</Btn>
        </div>
      </div>
    </div>
  );
}
