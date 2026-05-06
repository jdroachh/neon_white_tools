import React, { useState } from "react";
import { parseSeed } from "../api.js";
import { PageHead, Field, Btn, RushSelect, ErrorBanner, RUSHES } from "../shared.jsx";

export default function SeedParser() {
  const [rushName, setRushName] = useState(RUSHES[0].name);
  const [seed, setSeed]         = useState("");
  const [result, setResult]     = useState(null);   // {seed, rush_name, level_order}
  const [error, setError]       = useState(null);
  const [loading, setLoading]   = useState(false);

  async function handleParse() {
    setError(null);
    setLoading(true);
    try {
      const res = await parseSeed(rushName, seed);
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
            <Btn kind="primary" size="lg" icn="play" onClick={handleParse} disabled={loading}>
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
              <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "6px 10px" }}>
                {result.level_order.map((name, i) => (
                  <div key={i} style={{
                    display: "flex", alignItems: "center", gap: 10,
                    padding: "7px 10px",
                    background: "var(--surface)",
                    border: "1px solid var(--border)",
                    borderRadius: 2,
                  }}>
                    <span className="data muted" style={{ fontSize: 11, width: 22 }}>
                      {String(i + 1).padStart(2, "0")}
                    </span>
                    <span className="data" style={{ fontSize: 12, flex: 1 }}>{name}</span>
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
