import React, { useState, useEffect, useRef } from "react";
import { startFinder, stopFinder } from "../api.js";
import { PageHead, Field, Seg, Btn, RushSelect, ErrorBanner, RUSHES } from "../shared.jsx";
import { loadSeeds, saveSeeds, addSeed, removeSeed, MAX as MAX_SEEDS } from "../lib/savedSeeds.js";

const TOTAL_SEEDS = 2_147_483_647;

const DESIRED_PLACEHOLDERS = {
  "White / Mikey": "e.g. The Third Temple, Absolution",
  "Violet":        "e.g. Doghouse, Razor",
  "Red":           "e.g. Stomp Traversal, Fireball Traversal",
  "Yellow":        "e.g. Balloon Mountain, Arena",
};

function ProgressBar({ pct }) {
  return (
    <div style={{
      height: 4, background: "var(--border)", borderRadius: 2, overflow: "hidden",
    }}>
      <div style={{
        height: "100%", width: `${pct}%`,
        background: "var(--accent)", borderRadius: 2,
        transition: "width 0.3s ease",
      }} />
    </div>
  );
}

function SeedCard({ result, onSave, defaultOpen = false }) {
  const [open, setOpen] = useState(defaultOpen);
  const [copied, setCopied] = useState(false);

  function handleCopy(e) {
    e.stopPropagation();
    navigator.clipboard.writeText(String(result.seed)).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    });
  }

  function handleSaveClick(e) {
    e.stopPropagation();
    if (onSave) onSave(result);
  }

  return (
    <div style={{
      background: "var(--surface)", border: "1px solid var(--border)",
      borderRadius: 2, overflow: "hidden", marginBottom: 6,
    }}>
      <div
        onClick={() => setOpen(o => !o)}
        style={{
          padding: "10px 14px", cursor: "pointer",
          display: "flex", alignItems: "center", gap: 12,
        }}
      >
        <span className="accent" style={{ fontFamily: "var(--display-font)", fontSize: 20, minWidth: 100 }}>
          {result.seed}
        </span>
        {result.score != null && (
          <span className="accent" style={{
            fontSize: 11, fontWeight: 700,
            padding: "2px 6px",
            background: "rgba(180,255,100,0.10)",
            border: "1px solid var(--accent)",
            borderRadius: 2,
          }}>
            score {result.score}
          </span>
        )}
        <span className="muted" style={{ fontSize: 11, flex: 1 }}>{result.summary}</span>
        {onSave && (
          <button
            onClick={handleSaveClick}
            title="Save this seed to favorites"
            style={{
              background: "none", border: "1px solid var(--border)",
              borderRadius: 2, cursor: "pointer",
              color: "var(--muted)",
              fontSize: 12, padding: "2px 6px",
              lineHeight: 1.2, transition: "color 0.15s",
            }}
          >
            ★
          </button>
        )}
        <button
          onClick={handleCopy}
          title="Copy seed number"
          style={{
            background: "none", border: "1px solid var(--border)",
            borderRadius: 2, cursor: "pointer",
            color: copied ? "var(--accent)" : "var(--muted)",
            fontSize: 10, padding: "2px 6px",
            lineHeight: 1.4, transition: "color 0.15s",
          }}
        >
          {copied ? "✓" : "copy"}
        </button>
        <span className="muted" style={{ fontSize: 10 }}>{open ? "▲" : "▼"}</span>
      </div>
      {open && (
        <div style={{
          borderTop: "1px solid var(--border)",
          padding: "10px 14px",
          display: "flex",
          flexDirection: "column",
          gap: 4,
        }}>
          {result.level_order.map((lvl, i) => (
            <div key={i} style={{
              display: "flex", alignItems: "center", gap: 8,
              padding: "5px 8px",
              background: lvl.is_target ? "rgba(180,255,100,0.08)" : lvl.is_forced ? "rgba(100,200,255,0.07)" : lvl.is_excluded ? "rgba(255,180,60,0.08)" : "transparent",
              border: `1px solid ${lvl.is_target ? "var(--accent)" : lvl.is_forced ? "rgba(100,200,255,0.4)" : lvl.is_excluded ? "rgba(255,180,60,0.45)" : "var(--border)"}`,
              borderRadius: 2,
            }}>
              <span className="data muted" style={{ fontSize: 10, width: 20 }}>
                {String(i + 1).padStart(2, "0")}
              </span>
              <span className="data" style={{
                fontSize: 11, flex: 1,
                color: lvl.is_target ? "var(--accent)" : lvl.is_forced ? "rgb(100,200,255)" : lvl.is_excluded ? "rgb(255,180,60)" : "var(--fg)",
                display: "flex", alignItems: "center", gap: 5,
              }}>
                {lvl.name}
                {lvl.is_healthpack && (
                  <span style={{ fontSize: 12, color: "#e05070", lineHeight: 1 }}>♥</span>
                )}
              </span>
              {lvl.is_target && (
                <span style={{ fontSize: 9, color: "var(--accent)", fontWeight: 700 }}>◀</span>
              )}
              {lvl.is_forced && !lvl.is_target && (
                <span style={{ fontSize: 9, color: "rgb(100,200,255)", fontWeight: 700 }}>★</span>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function SeedFinder({ visible = false }) {
  const [rushName, setRushName]     = useState(RUSHES[0].name);
  const [levelsStr, setLevelsStr]   = useState("");
  const [depth, setDepth]           = useState("10");
  const [mode, setMode]             = useState("first");
  const [maxSeeds, setMaxSeeds]     = useState("5");
  const [orderMatters, setOrderMatters] = useState(false);
  const [hellRush, setHellRush]     = useState(false);
  const [hellRushMin, setHellRushMin] = useState("70");
  const [forceFirst, setForceFirst] = useState(false);
  const [forceFirstStr, setForceFirstStr] = useState("");
  const [excludedOn, setExcludedOn] = useState(false);
  const [excludedLevels, setExcludedLevels] = useState("");
  const [excludedWindow, setExcludedWindow] = useState("10");
  const [running, setRunning]       = useState(false);
  const [status, setStatus]         = useState("");
  const [pct, setPct]               = useState(0);
  const [results, setResults]       = useState([]);
  const [error, setError]           = useState(null);
  const [expected, setExpected]     = useState(null);

  const [savedSeeds, setSavedSeeds]       = useState([]);
  const [savedOpen, setSavedOpen]         = useState(false);
  const [savePrompt, setSavePrompt]       = useState(null); // { result } | null
  const [saveNickname, setSaveNickname]   = useState("");
  const [saveError, setSaveError]         = useState("");
  const [viewedSeed, setViewedSeed]       = useState(null); // saved-seed object or null

  useEffect(() => { loadSeeds().then(setSavedSeeds); }, []);
  useEffect(() => { if (visible) loadSeeds().then(setSavedSeeds); }, [visible]);

  const hellRushRef = useRef(hellRush);
  useEffect(() => { hellRushRef.current = hellRush; }, [hellRush]);

  // Register the global event handler once.
  useEffect(() => {
    window._nwFinderEvent = (data) => {
      if (data.type === "progress") {
        setPct(data.pct);
        setStatus(
          `Searching… ${data.seeds_checked.toLocaleString()} / ${TOTAL_SEEDS.toLocaleString()} checked, ${data.found_count} found`
        );
      } else if (data.type === "result") {
        setResults(prev => [...prev, data]);
        setStatus(prev => `Found ${data.seed} — still searching…`);
      } else if (data.type === "done") {
        if (data.stopped) {
          setStatus("Search stopped.");
        } else {
          setPct(100);
          setStatus(data.message);
        }
        if (hellRushRef.current) {
          setResults(prev => [...prev].sort((a, b) => (b.score ?? 0) - (a.score ?? 0)));
        }
        setRunning(false);
      } else if (data.type === "error") {
        setError(data.message);
        setRunning(false);
      }
    };
    return () => { window._nwFinderEvent = null; };
  }, []);

  // Auto-set depth when rush changes (non-White: cap at 8)
  function handleRushChange(name) {
    setRushName(name);
    if (name !== "White / Mikey") {
      setDepth("8");
    } else {
      setOrderMatters(false);
      setHellRush(false);
      setForceFirst(false);
      setExcludedOn(false);
    }
  }

  // Auto-increase depth as levels are typed
  function handleLevelsChange(val) {
    setLevelsStr(val);
    const count = val.split(",").filter(s => s.trim()).length;
    if (count > 0) {
      const rush = RUSHES.find(r => r.name === rushName);
      const maxDepth = rush ? rush.count : 96;
      setDepth(d => String(Math.max(Number(d), Math.min(count, maxDepth))));
    }
  }

  function handleSaveOpen(result) {
    setSaveError("");
    setSaveNickname(`Seed ${result.seed}`);
    setSavePrompt({ result });
  }

  async function handleSaveConfirm() {
    if (!savePrompt) return;
    const r = savePrompt.result;
    const seedObj = {
      nickname: saveNickname,
      seed: r.seed,
      rush: rushName,
      summary: r.summary,
      level_order: r.level_order,
      score: r.score ?? null,
      search_params: {
        levels_str: levelsStr,
        depth, mode, max_seeds: maxSeeds,
        order_matters: orderMatters,
        hell_rush: hellRush, hell_rush_min: hellRushMin,
        force_first: forceFirst, force_first_str: forceFirstStr,
        excluded_on: excludedOn, excluded_levels: excludedLevels, excluded_window: excludedWindow,
      },
    };
    const { error: err, list } = addSeed(savedSeeds, seedObj);
    if (err) { setSaveError(err); return; }
    setSavedSeeds(list);
    await saveSeeds(list);
    setSavePrompt(null);
    setSaveNickname("");
  }

  function handleSaveCancel() {
    setSavePrompt(null);
    setSaveNickname("");
    setSaveError("");
  }

  function handleView(seedObj) {
    setViewedSeed(seedObj);
    setSavedOpen(false);
  }

  function handleUseAsSearch(seedObj) {
    const p = seedObj.search_params || {};
    setRushName(seedObj.rush);
    setLevelsStr(p.levels_str ?? "");
    setDepth(p.depth ?? "10");
    setMode(p.mode ?? "first");
    setMaxSeeds(p.max_seeds ?? "5");
    setOrderMatters(!!p.order_matters);
    setHellRush(!!p.hell_rush);
    setHellRushMin(p.hell_rush_min ?? "70");
    setForceFirst(!!p.force_first);
    setForceFirstStr(p.force_first_str ?? "");
    setExcludedOn(!!p.excluded_on);
    setExcludedLevels(p.excluded_levels ?? "");
    setExcludedWindow(p.excluded_window ?? "10");
    setSavedOpen(false);
    setViewedSeed(null);
  }

  async function handleDeleteSaved(idx) {
    const name = savedSeeds[idx]?.nickname ?? "this seed";
    if (!window.confirm(`Delete saved seed "${name}"?`)) return;
    const list = removeSeed(savedSeeds, idx);
    setSavedSeeds(list);
    await saveSeeds(list);
  }

  async function handleStart() {
    setError(null);
    setResults([]);
    setPct(0);
    setStatus("Starting…");
    setExpected(null);
    setViewedSeed(null);

    if (forceFirst && !forceFirstStr.trim()) {
      setError("Force First Level is enabled but query is empty.");
      setStatus("");
      return;
    }

    if (excludedOn && !excludedLevels.trim()) {
      setError("Excluded Levels is enabled but no levels were entered.");
      setStatus("");
      return;
    }

    // Set running before the await (after the synchronous validations above) so
    // a double-click can't start two searches interleaving into one table.
    setRunning(true);
    let res;
    try {
      res = await startFinder(
        rushName, levelsStr, depth, mode, maxSeeds,
        hellRush, hellRushMin,
        forceFirst ? forceFirstStr : "",
        excludedOn ? excludedLevels : "",
        excludedOn ? excludedWindow : "",
        orderMatters,
      );
    } catch (err) {
      setError("Search failed."); setStatus(""); setRunning(false);
      return;
    }
    if (!res.ok) {
      setError(res.error);
      setStatus("");
      setRunning(false);
      return;
    }
    if (res.expected !== undefined) {
      setExpected(res.expected);
    }
  }

  async function handleStop() {
    await stopFinder();
    setRunning(false);
    setStatus("Search stopped.");
  }

  const rushCount = RUSHES.find(r => r.name === rushName)?.count ?? 96;
  const isWhiteMikey = rushName === "White / Mikey";

  return (
    <>
      <PageHead
        crumb="Rush Tools › Seed Finder"
        title="SEED"
        accentWord="FINDER"
      />
      <div className="body">
        <div className="panel-left">
          <div className="form">
            <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
              <Btn kind="ghost" size="sm" onClick={() => setSavedOpen(o => !o)}>
                ★ Saved seeds ({savedSeeds.length}) {savedOpen ? "▲" : "▼"}
              </Btn>
              {savedOpen && (
                <div style={{
                  border: "1px solid var(--border)", borderRadius: 2,
                  maxHeight: 240, overflow: "auto",
                  background: "var(--surface)",
                }}>
                  {savedSeeds.length === 0 ? (
                    <div className="muted" style={{ fontSize: 11, padding: "10px 12px" }}>
                      No saved seeds yet. Click ★ on a result to save one.
                    </div>
                  ) : savedSeeds.map((s, i) => (
                    <div key={s.seed} style={{
                      padding: "6px 10px",
                      borderBottom: i < savedSeeds.length - 1 ? "1px solid var(--border)" : "none",
                      display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap",
                    }}>
                      <div style={{ flex: "1 1 100%", display: "flex", alignItems: "baseline", gap: 8 }}>
                        <span style={{ fontWeight: 600, fontSize: 11 }}>{s.nickname}</span>
                        <span className="muted" style={{ fontSize: 10 }}>{s.seed} · {s.rush}</span>
                      </div>
                      <Btn kind="ghost" size="sm" onClick={() => handleView(s)}>View</Btn>
                      <Btn kind="ghost" size="sm" onClick={() => handleUseAsSearch(s)}>Use as search</Btn>
                      <Btn kind="danger" size="sm" onClick={() => handleDeleteSaved(i)}>✕</Btn>
                    </div>
                  ))}
                </div>
              )}
            </div>
            {savePrompt && (
              <div style={{
                border: "1px solid var(--accent)", borderRadius: 2,
                padding: 10, background: "rgba(180,255,100,0.06)",
                display: "flex", flexDirection: "column", gap: 6,
              }}>
                <div style={{ fontSize: 11, fontWeight: 600 }}>
                  Save seed {savePrompt.result.seed}
                </div>
                <input
                  className="input"
                  value={saveNickname}
                  onChange={e => { setSaveNickname(e.target.value); setSaveError(""); }}
                  onKeyDown={e => { if (e.key === "Enter") handleSaveConfirm(); if (e.key === "Escape") handleSaveCancel(); }}
                  placeholder="Nickname"
                  autoFocus
                />
                {saveError && (
                  <div style={{ fontSize: 11, color: "var(--bad, #f87171)" }}>{saveError}</div>
                )}
                <div style={{ display: "flex", gap: 6 }}>
                  <Btn kind="primary" size="sm" onClick={handleSaveConfirm}>Save</Btn>
                  <Btn kind="ghost" size="sm" onClick={handleSaveCancel}>Cancel</Btn>
                </div>
              </div>
            )}
            <Field label="Rush name">
              <RushSelect value={rushName} onChange={handleRushChange} />
            </Field>
            <Field label="Desired starting levels" hint="Comma-separated, partial names ok">
              <input
                className="input"
                value={levelsStr}
                onChange={e => handleLevelsChange(e.target.value)}
                placeholder={DESIRED_PLACEHOLDERS[rushName] ?? "e.g. The Third Temple, Absolution"}
                disabled={running}
              />
            </Field>
            <Field label={`Search depth (1–${rushCount})`} hint="Target levels must appear within this many positions">
              <input
                className="input"
                value={depth}
                onChange={e => setDepth(e.target.value)}
                style={{ width: 80 }}
                disabled={running}
              />
            </Field>
            <Field label="Result mode">
              <Seg
                options={["first", "multi"]}
                value={mode}
                onChange={v => { if (!running) setMode(v); }}
              />
            </Field>
            {mode === "multi" && (
              <Field label="Max seeds to find">
                <input
                  className="input"
                  value={maxSeeds}
                  onChange={e => setMaxSeeds(e.target.value)}
                  style={{ width: 80 }}
                  disabled={running}
                />
              </Field>
            )}
            {!isWhiteMikey && (
              <Field label="Order Matters?">
                <Seg
                  options={["No - Any Order", "Yes - Exact Order"]}
                  value={orderMatters ? "Yes - Exact Order" : "No - Any Order"}
                  onChange={v => { if (!running) setOrderMatters(v === "Yes - Exact Order"); }}
                />
              </Field>
            )}
            {isWhiteMikey && (
              <Field label="Hell Rush Mode">
                <Seg
                  options={["off", "on"]}
                  value={hellRush ? "on" : "off"}
                  onChange={v => { if (!running) setHellRush(v === "on"); }}
                />
              </Field>
            )}
            {isWhiteMikey && hellRush && (
              <Field label="Min spacing score (0–100)">
                <input
                  className="input"
                  value={hellRushMin}
                  onChange={e => setHellRushMin(e.target.value)}
                  style={{ width: 80 }}
                  disabled={running}
                />
              </Field>
            )}
            {isWhiteMikey && (
              <Field label="Force first level">
                <Seg
                  options={["off", "on"]}
                  value={forceFirst ? "on" : "off"}
                  onChange={v => { if (!running) setForceFirst(v === "on"); }}
                />
              </Field>
            )}
            {isWhiteMikey && forceFirst && (
              <Field label="Level name" hint="Must be exactly one level">
                <input
                  className="input"
                  value={forceFirstStr}
                  onChange={e => setForceFirstStr(e.target.value)}
                  placeholder="e.g. Movement"
                  disabled={running}
                />
              </Field>
            )}
            {isWhiteMikey && (
              <Field label="Excluded Levels">
                <Seg
                  options={["off", "on"]}
                  value={excludedOn ? "on" : "off"}
                  onChange={v => { if (!running) setExcludedOn(v === "on"); }}
                />
              </Field>
            )}
            {isWhiteMikey && excludedOn && (
              <Field label={`Exclusion window (1–${rushCount - 1})`} hint="Excluded levels must not appear within this many positions from the start">
                <input
                  className="input"
                  value={excludedWindow}
                  onChange={e => setExcludedWindow(e.target.value)}
                  style={{ width: 80 }}
                  disabled={running}
                />
              </Field>
            )}
            {isWhiteMikey && excludedOn && (
              <Field label="Excluded levels" hint="Comma-separated, partial names ok">
                <input
                  className="input"
                  value={excludedLevels}
                  onChange={e => setExcludedLevels(e.target.value)}
                  placeholder="e.g. Godspeed, Pummel"
                  disabled={running}
                />
              </Field>
            )}
            {expected !== null && expected < 10 && !running && (
              <div style={{
                padding: "8px 12px",
                background: "rgba(255,200,50,0.08)",
                border: "1px solid rgba(255,200,50,0.3)",
                borderRadius: 2, fontSize: 11,
                color: "var(--fg2)",
              }}>
                Expected matches across 2.1B seeds: ~{expected}. This search may find nothing —
                increase depth or reduce target levels.
              </div>
            )}
            <ErrorBanner message={error} />
            <div style={{ display: "flex", gap: 8 }}>
              <Btn kind="primary" size="lg" icn="play" onClick={handleStart} disabled={running}>
                {running ? "Searching…" : "Find Seed"}
              </Btn>
              {running && (
                <Btn kind="" size="lg" onClick={handleStop}>Stop</Btn>
              )}
            </div>
          </div>
        </div>

        <div className="panel-right" style={{ padding: 24, overflow: "auto", display: "flex", flexDirection: "column", gap: 12 }}>
          {viewedSeed ? (
            <div>
              <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 8 }}>
                <Btn kind="ghost" size="sm" onClick={() => setViewedSeed(null)}>← Back to search results</Btn>
                <span className="muted" style={{ fontSize: 11 }}>
                  Viewing saved seed: <strong>{viewedSeed.nickname}</strong> · {viewedSeed.rush}
                </span>
              </div>
              <SeedCard result={viewedSeed} defaultOpen />
            </div>
          ) : (
            <>
              {(status || pct > 0) && (
                <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                  <ProgressBar pct={pct} />
                  <span className="muted" style={{ fontSize: 11 }}>{status}</span>
                </div>
              )}
              {results.length > 0 ? (
                <div>
                  <div className="muted" style={{ fontSize: 10, textTransform: "uppercase", letterSpacing: 0.12, marginBottom: 8 }}>
                    {results.length} seed{results.length !== 1 ? "s" : ""} found — click to expand level order
                  </div>
                  {results.map((r) => (
                    <SeedCard key={r.seed} result={r} onSave={handleSaveOpen} />
                  ))}
                </div>
              ) : !running && !status ? (
                <div className="muted" style={{ padding: 32, fontSize: 12, textAlign: "center" }}>
                  Enter desired levels and press Find Seed.
                </div>
              ) : null}
            </>
          )}
        </div>
      </div>
    </>
  );
}
