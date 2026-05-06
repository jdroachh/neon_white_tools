import React, { useState } from "react";
import { loadTimerSeed, calculateTimer } from "../api.js";
import { PageHead, Field, Btn, RushSelect, OutputPanel, ErrorBanner, RUSHES } from "../shared.jsx";

const MEDAL_COLORS = {
  "DEV":          "#ff4e88",
  "ACE":          "#b4ff64",
  "GOLD":         "#ffd700",
  "SILVER":       "#c0c0c0",
  "BRONZE":       "#cd7f32",
  "BLOOD DIAMOND":"#e0f0ff",
  "TOPAZ":        "#ffd36e",
  "SAPPHIRE":     "#6ab0ff",
  "AMETHYST":     "#c77dff",
  "EMERALD":      "#3ddc84",
};

function MedalBadge({ medal }) {
  if (!medal) return null;
  return (
    <span style={{
      fontSize: 9, fontWeight: 700, letterSpacing: 0.5,
      padding: "2px 5px", borderRadius: 1,
      background: `${MEDAL_COLORS[medal] || "var(--fg2)"}22`,
      color: MEDAL_COLORS[medal] || "var(--fg2)",
      border: `1px solid ${MEDAL_COLORS[medal] || "var(--border)"}55`,
      whiteSpace: "nowrap",
    }}>
      {medal}
    </span>
  );
}

export default function RunTimer() {
  const [rushName, setRushName]   = useState(RUSHES[0].name);
  const [seed, setSeed]           = useState("");
  const [splitsText, setSplitsText] = useState("");
  const [rows, setRows]           = useState(null);
  const [error, setError]         = useState(null);
  const [loading, setLoading]     = useState(false);
  const [loadingSeeds, setLoadingSeeds] = useState(false);

  async function handleLoadSeed() {
    if (!seed.trim()) return;
    setLoadingSeeds(true);
    setError(null);
    try {
      const res = await loadTimerSeed(rushName, seed);
      if (res.ok) {
        setSplitsText(res.lines.map(n => `${n} `).join("\n"));
      } else {
        setError(res.error);
      }
    } catch (e) {
      setError(String(e));
    } finally {
      setLoadingSeeds(false);
    }
  }

  async function handleCalculate() {
    setError(null);
    setLoading(true);
    setRows(null);
    try {
      const res = await calculateTimer(rushName, seed, splitsText);
      if (res.ok) {
        setRows(res.rows);
      } else {
        setError(res.error);
      }
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }

  function handleCopySegments() {
    if (!rows) return;
    const text = rows.map(r => `${r.name}\t${r.segment_fmt}${r.medal ? "\t" + r.medal : ""}`).join("\n");
    navigator.clipboard.writeText(text).catch(() => {});
  }

  const segmentsBody = rows ? (
    <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
      {rows.map((r, i) => (
        <div key={i} style={{
          display: "flex", alignItems: "center", gap: 8,
          padding: "5px 8px",
          background: i % 2 === 0 ? "transparent" : "rgba(255,255,255,0.02)",
        }}>
          <span className="data muted" style={{ fontSize: 10, width: 20 }}>
            {String(i + 1).padStart(2, "0")}
          </span>
          <span className="data" style={{ fontSize: 12, width: 70, textAlign: "right" }}>
            {r.segment_fmt}
          </span>
          <MedalBadge medal={r.medal} />
        </div>
      ))}
    </div>
  ) : (
    <span className="muted" style={{ fontSize: 11 }}>No data yet.</span>
  );

  const namesBody = rows ? (
    <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
      {rows.map((r, i) => (
        <div key={i} style={{
          padding: "5px 8px",
          background: i % 2 === 0 ? "transparent" : "rgba(255,255,255,0.02)",
        }}>
          <span className="data" style={{ fontSize: 12 }}>{r.name}</span>
          <span className="muted" style={{ fontSize: 10, marginLeft: 8 }}>
            cum {r.cumulative}
          </span>
        </div>
      ))}
    </div>
  ) : (
    <span className="muted" style={{ fontSize: 11 }}>No data yet.</span>
  );

  return (
    <>
      <PageHead
        crumb="Rush Tools › Run Timer"
        title="RUN"
        accentWord="TIMER"
        actions={rows && <Btn kind="ghost" size="sm" icn="copy" onClick={handleCopySegments}>Copy segments</Btn>}
      />
      <div className="body">
        <div className="panel-left">
          <div className="form">
            <Field label="Rush name">
              <RushSelect value={rushName} onChange={setRushName} />
            </Field>
            <Field label="Seed number" hint="Optional — use Load to pre-fill level names">
              <div style={{ display: "flex", gap: 8 }}>
                <input
                  className="input"
                  value={seed}
                  onChange={e => setSeed(e.target.value)}
                  placeholder="e.g. 1834729104"
                  style={{ flex: 1 }}
                />
                <Btn kind="" size="" onClick={handleLoadSeed} disabled={loadingSeeds || !seed.trim()}>
                  {loadingSeeds ? "…" : "Load"}
                </Btn>
              </div>
            </Field>
            <Field
              label="Cumulative split times"
              hint='One per line: "Level Name 1:23.456" or just "38.28"'
            >
              <textarea
                className="input"
                value={splitsText}
                onChange={e => setSplitsText(e.target.value)}
                rows={10}
                style={{ resize: "vertical", fontFamily: "var(--mono-font)", fontSize: 12 }}
                placeholder={"Movement 17.442\nPummel 38.284\nGunner 1:02.100\n…"}
              />
            </Field>
            <ErrorBanner message={error} />
            <Btn kind="primary" size="lg" icn="timer" onClick={handleCalculate} disabled={loading}>
              {loading ? "Calculating…" : "Calculate Segments"}
            </Btn>
          </div>
        </div>

        <div className="panel-right" style={{ padding: 24, overflow: "auto", display: "flex", flexDirection: "column", gap: 16 }}>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, alignItems: "start" }}>
            <OutputPanel title="Segment Times" body={segmentsBody} onCopy={rows ? handleCopySegments : null} />
            <OutputPanel title="Level Order" body={namesBody} />
          </div>
        </div>
      </div>
    </>
  );
}
