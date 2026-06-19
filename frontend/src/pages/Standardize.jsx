import React, { useState, useEffect } from "react";
import { standardizeSplits, getStandardOrder } from "../api.js";
import { PageHead, Field, Btn, RushSelect, OutputPanel, ErrorBanner, MedalBadge, MedalToggle, Icon, RUSHES } from "../shared.jsx";

function SplitsOutputPanel({ title, times, medals, showMedals, onCopy }) {
  if (!times || times.length === 0) return null;
  return (
    <div style={{ display: "flex", flexDirection: "column" }}>
      <div style={{
        display: "flex", alignItems: "center", padding: "7px 12px",
        background: "var(--surface)", border: "1px solid var(--border)",
        borderBottom: "none", borderRadius: "2px 2px 0 0",
      }}>
        <span style={{ fontSize: 10, color: "var(--text-3)", textTransform: "uppercase", letterSpacing: 0.8, flex: 1 }}>
          {title}
        </span>
        <Btn kind="ghost" size="sm" icn="copy" onClick={onCopy}>Copy</Btn>
      </div>
      <div style={{ border: "1px solid var(--border)", borderRadius: "0 0 2px 2px" }}>
        {times.map((t, i) => (
          <div key={i} style={{
            display: "flex", alignItems: "center", gap: 8,
            padding: "5px 12px",
            background: i % 2 === 0 ? "transparent" : "rgba(255,255,255,0.025)",
          }}>
            <span style={{ fontSize: 10, color: "var(--text-3)", width: 20 }}>
              {String(i + 1).padStart(2, "0")}
            </span>
            <span className="data" style={{ fontSize: 12, flex: 1 }}>{t}</span>
            {showMedals && <MedalBadge medal={medals?.[i]} />}
          </div>
        ))}
      </div>
    </div>
  );
}

export default function Standardize({ showMedals, setShowMedals }) {
  const [rushName, setRushName] = useState(RUSHES[0].name);
  const [seed, setSeed]         = useState("");
  const [gold, setGold]         = useState("");
  const [segments, setSegments] = useState("");
  const [result, setResult]     = useState(null);
  const [error, setError]       = useState(null);
  const [loading, setLoading]   = useState(false);
  const [levels, setLevels]     = useState([]);

  // Standard level order is fixed per rush (independent of seed/splits), so we
  // can show the copyable list as soon as a rush is picked — no Standardize run.
  useEffect(() => {
    let cancelled = false;
    getStandardOrder(rushName)
      .then(res => { if (!cancelled && res.ok) setLevels(res.lines); })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [rushName]);

  async function handleStandardize() {
    setError(null);
    setLoading(true);
    try {
      const res = await standardizeSplits(rushName, seed, gold, segments);
      if (res.ok) setResult(res);
      else { setError(res.error); setResult(null); }
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }

  function copy(lines) {
    navigator.clipboard.writeText(lines.join("\n")).catch(() => {});
  }

  return (
    <>
      <PageHead
        crumb="Rush Tools › Standardize Splits"
        title="STANDARDIZE"
        accentWord="SPLITS"
        actions={result && <MedalToggle value={showMedals} onChange={setShowMedals} />}
      />
      <div className="body">
        <div className="panel-left">
          <div className="form">
            <Field label="Rush name">
              <RushSelect value={rushName} onChange={setRushName} />
            </Field>
            <Field label="Seed number" hint="The seed the run was played on">
              <input className="input" value={seed} onChange={e => setSeed(e.target.value)} placeholder="e.g. 1834729104" />
            </Field>
            <Field label="Gold splits" hint="Times in the order the seed played levels">
              <textarea className="input" rows={6} value={gold} onChange={e => setGold(e.target.value)} placeholder={"0:42.13\n0:55.47\n1:08.91\n…"} />
            </Field>
            <Field label="Segment splits" hint="Times in the order the seed played levels">
              <textarea className="input" rows={6} value={segments} onChange={e => setSegments(e.target.value)} placeholder={"0:42.13\n1:37.60\n2:46.51\n…"} />
            </Field>
            <ErrorBanner message={error} />
            <Btn kind="primary" size="lg" icn="play" onClick={handleStandardize} disabled={loading}>
              {loading ? "Standardizing…" : "Standardize"}
            </Btn>
            <Btn kind="ghost" icn="copy" onClick={() => copy(levels)} disabled={levels.length === 0}>
              Copy level order
            </Btn>
          </div>
        </div>

        <div className="panel-right" style={{ padding: 24, overflow: "auto", display: "flex", flexDirection: "column", gap: 16 }}>
          <div style={{
            padding: 14, background: "var(--surface-2)", border: "1px solid var(--border)",
            borderRadius: 2, display: "flex", alignItems: "center", gap: 12,
          }}>
            <span style={{ color: "var(--accent)" }}><Icon name="sw" size={18} /></span>
            <div>
              <div style={{ fontSize: 11, letterSpacing: 0.12, textTransform: "uppercase", color: "var(--text-2)", fontWeight: 600 }}>
                Inverse of Splits Updater
              </div>
              <div className="muted" style={{ fontSize: 11, marginTop: 2 }}>
                Converts seed-order splits back to standard level index order — ready to merge into your splits file.
              </div>
            </div>
          </div>

          {result ? (
            <>
              <SplitsOutputPanel
                title="Gold splits — standard order"
                times={result.gold}
                medals={result.gold_medals}
                showMedals={showMedals}
                onCopy={() => copy(result.gold)}
              />
              <SplitsOutputPanel
                title="Segment splits — standard order"
                times={result.segments}
                medals={result.segment_medals}
                showMedals={showMedals}
                onCopy={() => copy(result.segments)}
              />
            </>
          ) : (
            <div className="muted" style={{ padding: 32, fontSize: 12, textAlign: "center" }}>
              Paste your seed-order splits and press Standardize.
            </div>
          )}

          {levels.length > 0 && (
            <SplitsOutputPanel
              title="Level order — standard"
              times={levels}
              showMedals={false}
              onCopy={() => copy(levels)}
            />
          )}
        </div>
      </div>
    </>
  );
}
