import React, { useState, useEffect, useMemo } from "react";
import { PageHead, Field, Seg, Btn, MedalBadge } from "../shared.jsx";
import { getLevels, getRushBoards, findRank } from "../api.js";
import { loadWithRetry, loadLevelsWithRetry } from "../lib/retryLevels.js";

const LEVEL_MAX_SECS = 900; // 15:00.000

// Mirror of bridge.py _format_secs: MM:SS.mmm, dropping the minutes field under 60s.
function fmtMs(ms) {
  const secs = ms / 1000;
  const mins = Math.floor(secs / 60);
  const rem = secs - mins * 60;
  return mins > 0 ? `${mins}:${rem.toFixed(3).padStart(6, "0")}` : rem.toFixed(3);
}

// A signed/unsigned delta in ms -> "0.234s".
function fmtGap(deltaMs) {
  return `${(deltaMs / 1000).toFixed(3)}s`;
}

function NeighborRow({ arrow, rank, time, gap, gapColor, gapTitle }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "4px 8px" }}>
      <span style={{ width: 16, color: "var(--text-3)" }}>{arrow}</span>
      <span style={{ flex: 1, textAlign: "left", color: "var(--text-2)" }}>
        #{rank.toLocaleString()}
      </span>
      <span style={{ color: "var(--text-2)" }}>{time}</span>
      <span style={{ width: 70, textAlign: "right", color: gapColor, fontSize: "0.86em" }} title={gapTitle}>
        {gap}
      </span>
    </div>
  );
}

export default function ProjectedRank() {
  const [mode, setMode] = useState("Level");

  // Level mode
  const [levels, setLevels] = useState([]);
  const [levelName, setLevelName] = useState("");

  // Rush mode
  const [boards, setBoards] = useState([]);
  const [rushKey, setRushKey] = useState("");
  const [difficulty, setDiff] = useState("heaven");
  const selectedBoard = useMemo(() => boards.find(b => b.key === rushKey) || null, [boards, rushKey]);
  const diffAvailable = selectedBoard ? selectedBoard[`${difficulty}_available`] : false;

  // Time input
  const [timeStr, setTimeStr] = useState("");

  // Result / loading / error
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    const cancelLevels = loadLevelsWithRetry(getLevels, {
      onLevels: ls => { setLevels(ls); setLevelName(ls[0]?.display || ""); },
    });
    const cancelBoards = loadWithRetry(getRushBoards, {
      onData: bs => {
        setBoards(bs);
        const first = bs.find(b => b.heaven_available || b.hell_available);
        if (first) setRushKey(first.key);
      },
    });
    return () => { cancelLevels(); cancelBoards(); };
  }, []);

  function handleModeChange(v) {
    setMode(v);
    setResult(null);
    setError("");
  }

  async function handleSubmit() {
    setError("");
    setResult(null);
    const kind = mode.toLowerCase();

    if (kind === "level") {
      const m = timeStr.match(/^(\d+):(\d{1,2})(?:\.(\d+))?$/);
      const parsedSecs = m
        ? parseInt(m[1]) * 60 + parseInt(m[2]) + (m[3] ? parseFloat("0." + m[3]) : 0)
        : null;
      if (parsedSecs !== null && parsedSecs > LEVEL_MAX_SECS) {
        setError("Max time for levels is 15:00.000.");
        return;
      }
    }

    const key = kind === "level" ? levelName : `${rushKey}:${difficulty}`;
    setLoading(true);
    try {
      const r = await findRank(kind, key, timeStr);
      if (r.error) {
        setError(r.error);
      } else {
        setResult(r);
      }
    } catch {
      setError("Unexpected error.");
    } finally {
      setLoading(false);
    }
  }

  const canSubmit = !loading && timeStr.trim() &&
    (mode === "Level" ? !!levelName : (!!rushKey && diffAvailable));

  return (
    <>
      <PageHead crumb="Leaderboard Tools" title="PROJECTED" accentWord="RANK" />
      <div className="body">
        <div className="panel-left">
          <div className="form">
            <Field label="Board Type">
              <Seg options={["Level", "Rush"]} value={mode} onChange={handleModeChange} />
            </Field>

            {mode === "Level" && (
              <Field label="Level">
                <select className="input" value={levelName}
                        onChange={e => { setLevelName(e.target.value); setResult(null); }}
                        disabled={loading}>
                  {levels.map(l => (
                    <option key={l.internal} value={l.display}>{l.display}</option>
                  ))}
                </select>
              </Field>
            )}

            {mode === "Rush" && (
              <>
                <Field label="Rush">
                  <select className="input" value={rushKey}
                          onChange={e => { setRushKey(e.target.value); setResult(null); }}
                          disabled={loading}>
                    {boards.map(b => (
                      <option key={b.key} value={b.key}>{b.label}</option>
                    ))}
                  </select>
                </Field>
                <Field label="Difficulty">
                  <Seg options={["heaven", "hell"]} value={difficulty}
                       onChange={v => { setDiff(v); setResult(null); }} />
                  {rushKey && !diffAvailable && (
                    <div className="field-hint" style={{ color: "var(--text-3)" }}>
                      Board not available
                    </div>
                  )}
                </Field>
              </>
            )}

            <Field label="Time"
                   hint={mode === "Level" ? "Format: MM:SS.mmm — max 15:00.000" : "Format: MM:SS.mmm — e.g. 0:45.123"}>
              <input className="input" value={timeStr}
                     onChange={e => setTimeStr(e.target.value)}
                     onKeyDown={e => e.key === "Enter" && canSubmit && handleSubmit()}
                     placeholder="0:45.123"
                     disabled={loading} />
            </Field>

            <Btn kind="primary" size="lg" onClick={handleSubmit} disabled={!canSubmit}>
              {loading ? "Searching…" : "Find Rank"}
            </Btn>

            {error && (
              <div className="field-hint" style={{ color: "var(--accent-red, #ff5555)", marginTop: 8 }}>
                {error}
              </div>
            )}
          </div>
        </div>

        <div className="panel-right" style={{ display: "flex", flexDirection: "column", alignItems: "center" }}>
          {result && (
            <div style={{ textAlign: "center", width: "100%", maxWidth: 360, margin: "auto 0" }}>
              <div style={{
                fontSize: "3em", fontWeight: 700,
                fontFamily: "var(--display-font)",
                color: "var(--accent)", lineHeight: 1,
              }}>
                #{result.rank.toLocaleString()}
              </div>
              <div style={{ fontSize: "1em", color: "var(--text-3)", marginTop: 6 }}>
                of {result.total.toLocaleString()} entries
                {result.rank > result.total && result.total > 0 && (
                  <span style={{ marginLeft: 6, opacity: 0.7 }}>(below last)</span>
                )}
              </div>

              {result.medal && (
                <div style={{ marginTop: 16, display: "flex", justifyContent: "center" }}>
                  <div style={{
                    padding: "10px 24px", borderRadius: 2,
                    background: "rgba(255,255,255,0.06)",
                    border: "1px solid rgba(255,255,255,0.20)",
                    fontSize: "1.8em", lineHeight: 1,
                  }}>
                    <MedalBadge medal={result.medal} plain />
                  </div>
                </div>
              )}
              {result.board_kind === "level" && !result.medal && result.total > 0 && (
                <div style={{ marginTop: 10, fontSize: "0.82em", color: "var(--text-3)" }}>
                  No medal at this time
                </div>
              )}

              {result.next_medal && (
                <div style={{ marginTop: 12, fontSize: "0.86em", color: "var(--text-2)" }}>
                  <span style={{ color: "var(--accent)", fontWeight: 700 }}>
                    {fmtGap(result.next_medal.gap_secs * 1000)}
                  </span>{" "}
                  from{" "}
                  <MedalBadge medal={result.next_medal.name} plain />
                </div>
              )}

              {(result.above || result.below) && (
                <div style={{
                  marginTop: 20, paddingTop: 16,
                  borderTop: "1px solid var(--border)",
                  display: "flex", flexDirection: "column", gap: 6,
                  fontVariantNumeric: "tabular-nums",
                }}>
                  {result.above && (
                    <NeighborRow
                      arrow="▲" rank={result.rank - 1}
                      time={fmtMs(result.above.score_ms)}
                      gap={`+${fmtGap(result.target_ms - result.above.score_ms)}`}
                      gapColor="var(--text-3)" gapTitle="to climb a spot" />
                  )}
                  <div style={{
                    display: "flex", alignItems: "center", gap: 10,
                    padding: "4px 8px", borderRadius: 2,
                    background: "var(--accent-soft, rgba(255,255,255,0.05))",
                    border: "1px solid var(--accent)",
                  }}>
                    <span style={{ width: 16, color: "var(--accent)" }}>●</span>
                    <span style={{ flex: 1, textAlign: "left", color: "var(--accent)", fontWeight: 700 }}>
                      #{result.rank.toLocaleString()} · you
                    </span>
                    <span style={{ color: "var(--text-1)", fontWeight: 600 }}>
                      {fmtMs(result.target_ms)}
                    </span>
                  </div>
                  {result.below && (
                    <NeighborRow
                      arrow="▼" rank={result.rank + 1}
                      time={fmtMs(result.below.score_ms)}
                      gap={fmtGap(result.below.score_ms - result.target_ms)}
                      gapColor="var(--accent-green, #6ee7a8)" gapTitle="cushion below you" />
                  )}
                </div>
              )}
            </div>
          )}
          {!result && !loading && (
            <div className="muted" style={{ padding: 32, fontSize: 12, textAlign: "center" }}>
              Pick a board and enter a time to see where you'd rank.
            </div>
          )}
          {loading && (
            <div className="muted" style={{ padding: 32, fontSize: 12, textAlign: "center" }}>Searching…</div>
          )}
        </div>
      </div>
    </>
  );
}
