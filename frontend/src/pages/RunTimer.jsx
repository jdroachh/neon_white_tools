import React, { useState, useEffect } from "react";
import { getStandardOrder, loadTimerSeed, calculateTimer } from "../api.js";
import { PageHead, Field, Seg, Btn, RushSelect, ErrorBanner, MedalBadge, MedalToggle, RUSHES } from "../shared.jsx";

export default function RunTimer({ showMedals, setShowMedals }) {
  const [rushName, setRushName]     = useState(RUSHES[0].name);
  const [mode, setMode]             = useState("standard"); // standard | seed | manual
  const [seed, setSeed]             = useState("");
  const [rows, setRows]             = useState([]);         // [{name, time}]
  const [result, setResult]         = useState(null);
  const [error, setError]           = useState(null);
  const [loading, setLoading]       = useState(false);
  const [loadingNames, setLoadingNames] = useState(false);

  // Reload level names when rush or mode changes.
  useEffect(() => {
    const count = RUSHES.find(r => r.name === rushName)?.count ?? 96;
    setResult(null);
    setError(null);
    if (mode === "standard") {
      setLoadingNames(true);
      getStandardOrder(rushName)
        .then(res => { if (res.ok) setRows(res.lines.map(name => ({ name, time: "" }))); })
        .finally(() => setLoadingNames(false));
    } else {
      setRows(Array.from({ length: count }, () => ({ name: "", time: "" })));
    }
  }, [rushName, mode]);

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

  async function handleCalculate() {
    setError(null);
    setLoading(true);
    setResult(null);
    const splitsText = rows.map(r => `${r.name || "Level"} ${r.time}`).join("\n");
    try {
      const res = await calculateTimer(rushName, seed, splitsText);
      if (res.ok) setResult(res);
      else setError(res.error);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }

  function copySegments() {
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

  const isLocked = mode !== "manual";

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
              <Seg options={["standard", "seed", "manual"]} value={mode} onChange={setMode} />
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

            <Field label="Cumulative split times">
              <div style={{
                maxHeight: 320, overflowY: "auto",
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
                ) : rows.map((row, i) => (
                  <div key={i} style={rowStyle(i)}>
                    <span style={{ fontSize: 10, color: "var(--text-3)", textAlign: "right" }}>
                      {String(i + 1).padStart(2, "0")}
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
            <Btn kind="primary" size="lg" onClick={handleCalculate} disabled={loading}>
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
                    <Btn kind="ghost" size="sm" icn="copy" onClick={copySegments}>Segments</Btn>
                    <Btn kind="ghost" size="sm" icn="copy" onClick={copyMedals}>Medals</Btn>
                  </div>
                </div>
                <div style={{ border: "1px solid var(--border)", borderRadius: "0 0 2px 2px" }}>
                  {result.rows.map((r, i) => (
                    <div key={i} style={{
                      display: "flex", alignItems: "center", gap: 8,
                      padding: "5px 12px",
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
                      padding: "5px 12px",
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
    </>
  );
}
