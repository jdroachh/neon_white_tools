import React, { useState } from "react";
import { reorderSplits } from "../api.js";
import { PageHead, Field, Btn, RushSelect, OutputPanel, ErrorBanner, RUSHES } from "../shared.jsx";

export default function SplitsUpdater() {
  const [rushName, setRushName] = useState(RUSHES[0].name);
  const [seed, setSeed]         = useState("");
  const [gold, setGold]         = useState("");
  const [segments, setSegments] = useState("");
  const [result, setResult]     = useState(null);   // {level_order, gold, segments}
  const [error, setError]       = useState(null);
  const [loading, setLoading]   = useState(false);

  async function handleGenerate() {
    setError(null);
    setLoading(true);
    try {
      const res = await reorderSplits(rushName, seed, gold, segments);
      if (res.ok) {
        setResult(res);
      } else {
        setError(res.error);
        setResult(null);
      }
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
            <Field label="Seed number">
              <input
                className="input"
                value={seed}
                onChange={e => setSeed(e.target.value)}
                placeholder="e.g. 1834729104"
              />
            </Field>
            <Field label="Gold splits" hint="Best individual times, one per line, standard order">
              <textarea
                className="input"
                rows={6}
                value={gold}
                onChange={e => setGold(e.target.value)}
                placeholder={"0:42.13\n1:08.91\n0:55.47\n…"}
              />
            </Field>
            <Field label="Segment splits" hint="Cumulative or per-segment times, standard order">
              <textarea
                className="input"
                rows={6}
                value={segments}
                onChange={e => setSegments(e.target.value)}
                placeholder={"0:42.13\n1:51.04\n2:46.51\n…"}
              />
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
              {result.gold.length > 0 && (
                <OutputPanel
                  title="Gold splits — seed order"
                  body={result.gold.join("\n")}
                  onCopy={() => copy(result.gold)}
                />
              )}
              {result.segments.length > 0 && (
                <OutputPanel
                  title="Segment splits — seed order"
                  body={result.segments.join("\n")}
                  onCopy={() => copy(result.segments)}
                />
              )}
              <OutputPanel
                title="Level order"
                body={result.level_order.join("\n")}
                onCopy={() => copy(result.level_order)}
              />
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
