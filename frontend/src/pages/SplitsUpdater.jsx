import React, { useState } from "react";
import { reorderSplits } from "../api.js";
import { PageHead, Field, Btn, RushSelect, ErrorBanner, MedalBadge, MedalToggle, RUSHES } from "../shared.jsx";

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

export default function SplitsUpdater({ showMedals, setShowMedals }) {
  const [rushName, setRushName] = useState(RUSHES[0].name);
  const [seed, setSeed]         = useState("");
  const [gold, setGold]         = useState("");
  const [segments, setSegments] = useState("");
  const [result, setResult]     = useState(null);
  const [error, setError]       = useState(null);
  const [loading, setLoading]   = useState(false);

  async function handleGenerate() {
    setError(null);
    setLoading(true);
    try {
      const res = await reorderSplits(rushName, seed, gold, segments);
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
        crumb="Rush Tools › Splits Updater"
        title="SPLITS"
        accentWord="UPDATER"
        actions={<>
          {result && <MedalToggle value={showMedals} onChange={setShowMedals} />}
          <Btn kind="ghost" size="sm" onClick={() => {
            setGold(""); setSegments(""); setResult(null); setError(null); setSeed("");
          }}>Clear</Btn>
        </>}
      />
      <div className="body">
        <div className="panel-left">
          <div className="form">
            <Field label="Rush name">
              <RushSelect value={rushName} onChange={setRushName} />
            </Field>
            <Field label="Seed number" hint="The seed you want to adjust your splits to">
              <input className="input" value={seed} onChange={e => setSeed(e.target.value)} placeholder="e.g. 1834729104" />
            </Field>
            <Field label="Gold splits" hint="Best individual times, one per line, standard order">
              <textarea className="input" rows={6} value={gold} onChange={e => setGold(e.target.value)} placeholder={"0:42.13\n1:08.91\n0:55.47\n…"} />
            </Field>
            <Field label="Segment splits" hint="Per-segment times, standard order">
              <textarea className="input" rows={6} value={segments} onChange={e => setSegments(e.target.value)} placeholder={"0:42.13\n1:08.91\n0:55.47\n…"} />
            </Field>
            <ErrorBanner message={error} />
            <Btn kind="primary" size="lg" icn="play" onClick={handleGenerate} disabled={loading}>
              {loading ? "Generating…" : "Generate splits"}
            </Btn>
          </div>
        </div>

        <div className="panel-right" style={{ padding: 24, overflow: "auto", display: "flex", flexDirection: "column", gap: 16 }}>
          {result ? (
            <>
              <SplitsOutputPanel
                title="Gold splits — seed order"
                times={result.gold}
                medals={result.gold_medals}
                showMedals={showMedals}
                onCopy={() => copy(result.gold)}
              />
              <SplitsOutputPanel
                title="Segment splits — seed order"
                times={result.segments}
                medals={result.segment_medals}
                showMedals={showMedals}
                onCopy={() => copy(result.segments)}
              />
              {result.level_order?.length > 0 && (
                <div style={{ display: "flex", flexDirection: "column" }}>
                  <div style={{
                    display: "flex", alignItems: "center", padding: "7px 12px",
                    background: "var(--surface)", border: "1px solid var(--border)",
                    borderBottom: "none", borderRadius: "2px 2px 0 0",
                  }}>
                    <span style={{ fontSize: 10, color: "var(--text-3)", textTransform: "uppercase", letterSpacing: 0.8, flex: 1 }}>
                      Level order
                    </span>
                    <Btn kind="ghost" size="sm" icn="copy" onClick={() => copy(result.level_order)}>Copy</Btn>
                  </div>
                  <div style={{ border: "1px solid var(--border)", borderRadius: "0 0 2px 2px" }}>
                    {result.level_order.map((name, i) => (
                      <div key={i} style={{
                        padding: "5px 12px", fontSize: 12,
                        background: i % 2 === 0 ? "transparent" : "rgba(255,255,255,0.025)",
                      }}>{name}</div>
                    ))}
                  </div>
                </div>
              )}
            </>
          ) : (
            <div className="muted" style={{ padding: 32, fontSize: 12, textAlign: "center" }}>
              Paste your splits and press Generate to reorder them for a seed.
            </div>
          )}
        </div>
      </div>
    </>
  );
}
