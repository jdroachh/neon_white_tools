import React, { useState } from "react";
import { standardizeSplits } from "../api.js";
import { PageHead, Field, Btn, RushSelect, OutputPanel, ErrorBanner, Icon, RUSHES } from "../shared.jsx";

export default function Standardize() {
  const [rushName, setRushName] = useState(RUSHES[0].name);
  const [seed, setSeed]         = useState("");
  const [gold, setGold]         = useState("");
  const [segments, setSegments] = useState("");
  const [result, setResult]     = useState(null);   // {gold, segments}
  const [error, setError]       = useState(null);
  const [loading, setLoading]   = useState(false);

  async function handleStandardize() {
    setError(null);
    setLoading(true);
    try {
      const res = await standardizeSplits(rushName, seed, gold, segments);
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
        crumb="Rush Tools › Standardize Splits"
        title="STANDARDIZE"
        accentWord="SPLITS"
      />
      <div className="body">
        <div className="panel-left">
          <div className="form">
            <Field label="Rush name">
              <RushSelect value={rushName} onChange={setRushName} />
            </Field>
            <Field label="Seed number" hint="The seed the run was played on">
              <input
                className="input"
                value={seed}
                onChange={e => setSeed(e.target.value)}
                placeholder="e.g. 1834729104"
              />
            </Field>
            <Field label="Gold splits" hint="Times in the order the seed played levels">
              <textarea
                className="input"
                rows={6}
                value={gold}
                onChange={e => setGold(e.target.value)}
                placeholder={"0:42.13\n0:55.47\n1:08.91\n…"}
              />
            </Field>
            <Field label="Segment splits" hint="Times in the order the seed played levels">
              <textarea
                className="input"
                rows={6}
                value={segments}
                onChange={e => setSegments(e.target.value)}
                placeholder={"0:42.13\n1:37.60\n2:46.51\n…"}
              />
            </Field>
            <ErrorBanner message={error} />
            <Btn kind="primary" size="lg" icn="play" onClick={handleStandardize} disabled={loading}>
              {loading ? "Standardizing…" : "Standardize"}
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
              {result.gold.length > 0 && (
                <OutputPanel
                  title="Gold splits — standard order"
                  body={result.gold.join("\n")}
                  onCopy={() => copy(result.gold)}
                />
              )}
              {result.segments.length > 0 && (
                <OutputPanel
                  title="Segment splits — standard order"
                  body={result.segments.join("\n")}
                  onCopy={() => copy(result.segments)}
                />
              )}
            </>
          ) : (
            <div className="muted" style={{ padding: 32, fontSize: 12, textAlign: "center" }}>
              Paste your seed-order splits and press Standardize.
            </div>
          )}
        </div>
      </div>
    </>
  );
}
