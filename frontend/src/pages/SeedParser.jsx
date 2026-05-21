import React, { useState, useEffect } from "react";
import { parseSeed } from "../api.js";
import { PageHead, Field, Btn, RushSelect, ErrorBanner, RUSHES } from "../shared.jsx";
import { loadSeeds } from "../lib/savedSeeds.js";

export default function SeedParser({ visible = false }) {
  const [rushName, setRushName] = useState(RUSHES[0].name);
  const [seed, setSeed]         = useState("");
  const [result, setResult]     = useState(null);   // {seed, rush_name, level_order}
  const [error, setError]       = useState(null);
  const [loading, setLoading]   = useState(false);
  const [savedSeeds, setSavedSeeds] = useState([]);
  const [savedOpen, setSavedOpen]   = useState(false);

  useEffect(() => { loadSeeds().then(setSavedSeeds); }, []);
  useEffect(() => { if (visible) loadSeeds().then(setSavedSeeds); }, [visible]);

  async function handleParse(overrideRush, overrideSeed) {
    const r = overrideRush ?? rushName;
    const s = overrideSeed ?? seed;
    setError(null);
    setLoading(true);
    try {
      const res = await parseSeed(r, s);
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

  function handlePickSaved(s) {
    setRushName(s.rush);
    setSeed(String(s.seed));
    setSavedOpen(false);
    handleParse(s.rush, String(s.seed));
  }

  function handleCopy() {
    if (!result) return;
    const text = result.level_order.map((name, i) => `${i + 1}. ${name}`).join("\n");
    navigator.clipboard.writeText(text).catch(() => {});
  }

  function handleKeyDown(e) {
    if (e.key === "Enter") handleParse();
  }

  return (
    <>
      <PageHead
        crumb="Rush Tools › Seed Parser"
        title="SEED"
        accentWord="PARSER"
        actions={
          result && <Btn kind="ghost" size="sm" icn="copy" onClick={handleCopy}>Copy order</Btn>
        }
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
                      No saved seeds yet. Save one from the Seed Finder page.
                    </div>
                  ) : savedSeeds.map((s, i) => (
                    <div key={s.seed}
                      onClick={() => handlePickSaved(s)}
                      style={{
                        padding: "6px 10px",
                        borderBottom: i < savedSeeds.length - 1 ? "1px solid var(--border)" : "none",
                        display: "flex", alignItems: "baseline", gap: 8,
                        cursor: "pointer",
                      }}
                      onMouseEnter={e => e.currentTarget.style.background = "rgba(255,255,255,0.04)"}
                      onMouseLeave={e => e.currentTarget.style.background = "transparent"}
                    >
                      <span style={{ fontWeight: 600, fontSize: 11 }}>{s.nickname}</span>
                      <span className="muted" style={{ fontSize: 10 }}>{s.seed} · {s.rush}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
            <Field label="Rush name">
              <RushSelect value={rushName} onChange={setRushName} />
            </Field>
            <Field label="Seed number" hint="1 to 2,147,483,647">
              <input
                className="input"
                value={seed}
                onChange={e => setSeed(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="e.g. 1834729104"
              />
            </Field>
            <ErrorBanner message={error} />
            <Btn kind="primary" size="lg" icn="play" onClick={() => handleParse()} disabled={loading}>
              {loading ? "Parsing…" : "Parse"}
            </Btn>
            <div className="muted" style={{ fontSize: 11, lineHeight: 1.5 }}>
              Generates the full level order for this seed without running a search.
            </div>
          </div>
        </div>

        <div className="panel-right" style={{ padding: 24, overflow: "auto" }}>
          {result ? (
            <>
              <div style={{ display: "flex", alignItems: "baseline", gap: 14, marginBottom: 18 }}>
                <span className="display" style={{ fontSize: 38 }}>{result.seed}</span>
                <span className="muted" style={{ fontSize: 11, letterSpacing: 0.12, textTransform: "uppercase" }}>
                  {result.rush_name} · {result.level_count} levels · seed parsed
                </span>
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                {result.level_order.map((name, i) => (
                  <div key={i} style={{
                    display: "flex", alignItems: "center", gap: 8,
                    padding: "5px 8px",
                    border: "1px solid var(--border)",
                    borderRadius: 2,
                  }}>
                    <span className="data muted" style={{ fontSize: 10, width: 20 }}>
                      {String(i + 1).padStart(2, "0")}
                    </span>
                    <span className="data" style={{ fontSize: 11, flex: 1 }}>{name}</span>
                  </div>
                ))}
              </div>
            </>
          ) : (
            <div className="muted" style={{ padding: 32, fontSize: 12, textAlign: "center" }}>
              Enter a seed and press Parse to see the level order.
            </div>
          )}
        </div>
      </div>
    </>
  );
}
