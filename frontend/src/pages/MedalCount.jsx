import React, { useState, useEffect } from "react";
import { PageHead, Field, Btn, ErrorBanner, MedalBadge } from "../shared.jsx";
import { getLevels, getMedalDataReady, countMedals, stopCountMedals } from "../api.js";
import { loadLevelsWithRetry } from "../lib/retryLevels.js";

// Hardest → easiest, matching bridge.py _EXTENDED_TIERS. Every stage carries all
// five, so there's no per-level availability to worry about — only whether the
// community medal data has finished loading.
const TIERS = ["BLOOD DIAMOND", "TOPAZ", "SAPPHIRE", "AMETHYST", "EMERALD"];

export default function MedalCount() {
  const [levels, setLevels]     = useState([]);
  const [levelName, setLevel]   = useState("");
  const [dataReady, setDataReady] = useState(false);
  const [tier, setTier]         = useState("TOPAZ");
  const [running, setRunning]   = useState(false);
  const [status, setStatus]     = useState("");
  const [scanned, setScanned]   = useState(0);
  const [error, setError]       = useState("");
  const [result, setResult]     = useState(null);

  useEffect(() => {
    const cancelLevels = loadLevelsWithRetry(getLevels, {
      onLevels: ls => { setLevels(ls); setLevel(ls[0].display); },
    });
    window._nwMedalCountEvent = (ev) => {
      if (ev.type === "status") {
        setStatus(ev.message);
      } else if (ev.type === "progress") {
        setScanned(ev.scanned);
      } else if (ev.type === "done") {
        setResult(ev);
        setStatus(ev.message);
        setRunning(false);
      } else if (ev.type === "error") {
        setError(ev.message);
        setRunning(false);
      }
    };
    return () => { cancelLevels(); window._nwMedalCountEvent = null; };
  }, []);

  // The community medal tables load in a background thread at bridge import, so
  // poll until the backend reports them ready before enabling the tier picker —
  // otherwise a fast boot would try to count against not-yet-loaded Topaz/BD data.
  useEffect(() => {
    let cancelled = false;
    let attempts = 0;
    function poll() {
      if (cancelled) return;
      // Advance on BOTH resolve and reject — a swallowed rejection here (bridge
      // not ready on the first tick, or a transient) must not kill the loop and
      // leave the page stuck on "Loading medal data…". Force-ready after ~12s so
      // the picker never hangs even if the readiness call keeps failing.
      getMedalDataReady()
        .then(ready => !!ready)
        .catch(() => false)
        .then(ready => {
          if (cancelled) return;
          if (ready || ++attempts >= 40) setDataReady(true);
          else setTimeout(poll, 300);
        });
    }
    poll();
    return () => { cancelled = true; };
  }, []);

  async function handleRun() {
    setError(""); setStatus(""); setResult(null); setScanned(0);
    setRunning(true);
    try {
      const r = await countMedals(levelName, tier);
      if (!r.ok) { setError(r.error); setRunning(false); }
    } catch {
      setError("Run failed."); setRunning(false);
    }
  }

  async function handleStop() {
    await stopCountMedals();
    setStatus("Stopping...");
  }

  const canRun = !running && !!levelName && dataReady;

  return (
    <>
      <PageHead crumb="Leaderboard Tools" title="MEDAL" accentWord="COUNT" />
      <div className="body">
        <div className="panel-left">
          <div className="form">
            <Field label="Level">
              <select className="input" value={levelName}
                      onChange={e => { setLevel(e.target.value); setResult(null); }}
                      disabled={running}>
                {levels.map(l => (
                  <option key={l.internal} value={l.display}>{l.display}</option>
                ))}
              </select>
            </Field>

            <Field label="Medal tier"
                   hint="Community tiers only — Bronze covers the whole board.">
              <select className="input" value={tier}
                      onChange={e => { setTier(e.target.value); setResult(null); }}
                      disabled={running || !dataReady}>
                {TIERS.map(t => (
                  <option key={t} value={t}>{t}</option>
                ))}
              </select>
              {!dataReady && (
                <div className="field-hint" style={{ color: "var(--text-3)" }}>
                  Loading medal data…
                </div>
              )}
            </Field>

            <ErrorBanner message={error} />

            <div style={{ display: "flex", gap: 8 }}>
              {running
                ? <Btn kind="danger" size="lg" onClick={handleStop}>Stop</Btn>
                : <Btn kind="primary" size="lg" icn="medal" onClick={handleRun} disabled={!canRun}>Count</Btn>}
            </div>
            {status && <div className="muted" style={{ fontSize: 11 }}>{status}</div>}
          </div>
        </div>

        <div className="panel-right" style={{ display: "flex", flexDirection: "column", alignItems: "center" }}>
          {result && !result.stopped ? (
            <div style={{ textAlign: "center", width: "100%", maxWidth: 440, margin: "auto 0" }}>
              <div style={{ marginBottom: 12, display: "flex", justifyContent: "center" }}>
                <div style={{
                  padding: "10px 24px", borderRadius: 2,
                  background: "rgba(255,255,255,0.06)",
                  border: "1px solid rgba(255,255,255,0.20)",
                  fontSize: "1.7em", lineHeight: 1,
                }}>
                  <MedalBadge medal={result.tier} plain />
                </div>
              </div>
              <div className="muted" style={{ fontSize: 14, marginBottom: 22 }}>
                on {result.level} · cutoff ≤ {result.cutoff_time}
              </div>

              <div style={{ display: "flex", gap: 32, justifyContent: "center", flexWrap: "wrap" }}>
                <div style={{ minWidth: 150 }}>
                  <div style={{
                    fontSize: "3.8em", fontWeight: 700, lineHeight: 1,
                    fontFamily: "var(--display-font)", color: "var(--accent)",
                  }}>
                    {result.at_least.toLocaleString()}
                  </div>
                  <div style={{ fontSize: "0.98em", color: "var(--text-3)", marginTop: 8 }}>
                    have <strong style={{ color: "var(--text-2)" }}>at least</strong> this tier
                  </div>
                </div>
                <div style={{ minWidth: 150 }}>
                  <div style={{
                    fontSize: "3.8em", fontWeight: 700, lineHeight: 1,
                    fontFamily: "var(--display-font)", color: "var(--text-1)",
                  }}>
                    {result.exactly.toLocaleString()}
                  </div>
                  <div style={{ fontSize: "0.98em", color: "var(--text-3)", marginTop: 8 }}>
                    have <strong style={{ color: "var(--text-2)" }}>exactly</strong> this tier
                  </div>
                </div>
              </div>

              <div style={{ fontSize: "0.92em", color: "var(--text-3)", marginTop: 26 }}>
                scanned {result.total_scanned.toLocaleString()} entries
                {result.failed_pages > 0 && " · a page failed, result may be incomplete"}
              </div>
            </div>
          ) : (
            <div className="muted" style={{ padding: 32, fontSize: 12, textAlign: "center" }}>
              {running
                ? (scanned > 0 ? `Scanning… ${scanned.toLocaleString()} entries` : "Scanning…")
                : "Pick a level and tier, then press Count."}
            </div>
          )}
        </div>
      </div>
    </>
  );
}
