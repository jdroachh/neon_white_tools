import React, { useState, useEffect, useRef } from "react";
import { startFinder, stopFinder } from "../api.js";
import { PageHead, Field, Seg, Btn, RushSelect, ErrorBanner, RUSHES } from "../shared.jsx";

const TOTAL_SEEDS = 2_147_483_647;

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

function SeedCard({ result, targetNames }) {
  const [open, setOpen] = useState(false);
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
              background: lvl.is_target ? "rgba(180,255,100,0.08)" : "transparent",
              border: `1px solid ${lvl.is_target ? "var(--accent)" : "var(--border)"}`,
              borderRadius: 2,
            }}>
              <span className="data muted" style={{ fontSize: 10, width: 20 }}>
                {String(i + 1).padStart(2, "0")}
              </span>
              <span className="data" style={{
                fontSize: 11, flex: 1,
                color: lvl.is_target ? "var(--accent)" : "var(--fg)",
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
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function SeedFinder() {
  const [rushName, setRushName]     = useState(RUSHES[0].name);
  const [levelsStr, setLevelsStr]   = useState("");
  const [depth, setDepth]           = useState("10");
  const [mode, setMode]             = useState("first");
  const [maxSeeds, setMaxSeeds]     = useState("5");
  const [hellRush, setHellRush]     = useState(false);
  const [hellRushMin, setHellRushMin] = useState("70");
  const [running, setRunning]       = useState(false);
  const [status, setStatus]         = useState("");
  const [pct, setPct]               = useState(0);
  const [results, setResults]       = useState([]);
  const [error, setError]           = useState(null);
  const [expected, setExpected]     = useState(null);

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
      setHellRush(false);
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

  async function handleStart() {
    setError(null);
    setResults([]);
    setPct(0);
    setStatus("Starting…");
    setExpected(null);

    const res = await startFinder(rushName, levelsStr, depth, mode, maxSeeds, hellRush, hellRushMin);
    if (!res.ok) {
      setError(res.error);
      setStatus("");
      return;
    }
    setRunning(true);
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
            <Field label="Rush name">
              <RushSelect value={rushName} onChange={handleRushChange} />
            </Field>
            <Field label="Desired starting levels" hint="Comma-separated, partial names ok">
              <input
                className="input"
                value={levelsStr}
                onChange={e => handleLevelsChange(e.target.value)}
                placeholder="e.g. The Third Temple, Absolution"
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
              {results.map((r, i) => (
                <SeedCard key={i} result={r} />
              ))}
            </div>
          ) : !running && !status ? (
            <div className="muted" style={{ padding: 32, fontSize: 12, textAlign: "center" }}>
              Enter desired levels and press Find Seed.
            </div>
          ) : null}
        </div>
      </div>
    </>
  );
}
