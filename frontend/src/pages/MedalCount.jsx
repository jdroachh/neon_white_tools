import React, { useState, useEffect, useRef } from "react";
import { PageHead, Field, Seg, Cb, Btn, ErrorBanner, MedalBadge } from "../shared.jsx";
import {
  getLevels, getChapters, getMedalDataReady, countMedalsScope, stopCountMedals, saveTextFile,
} from "../api.js";
import { loadLevelsWithRetry, loadWithRetry } from "../lib/retryLevels.js";
import LevelPickerModal from "../components/LevelPickerModal.jsx";
import { loadLastSelection, saveLastSelection } from "../lib/customLevels.js";

// Hardest → easiest, matching bridge.py _EXTENDED_TIERS. Every stage carries all
// five, so there's no per-level availability to worry about — only whether the
// community medal data has finished loading.
const TIERS = ["BLOOD DIAMOND", "TOPAZ", "SAPPHIRE", "AMETHYST", "EMERALD"];

// Scope label ↔ backend mode (see bridge._resolve_levels_for_mode).
const SCOPES = { Level: "level", Chapter: "chapter", Game: "game", Custom: "custom" };
const SCOPE_DESC = {
  Level: "One level.",
  Chapter: "Every stage in a chapter.",
  Game: "All 121 story + sidequest levels — a long scan.",
  Custom: "Hand-pick any set of stages.",
};

export default function MedalCount() {
  const [levels, setLevels]       = useState([]);
  const [chapters, setChapters]   = useState([]);
  const [dataReady, setDataReady] = useState(false);

  const [scope, setScope]         = useState("Level");
  const [levelName, setLevel]     = useState("");
  const [chapterName, setChapter] = useState("");
  const [customLevels, setCustomLevels] = useState([]);
  const [pickerOpen, setPickerOpen]     = useState(false);
  const customHydrated = useRef(false);

  // Tier multi-select — keep TIERS order regardless of click order.
  const [sel, setSel] = useState({ TOPAZ: true });

  const [running, setRunning] = useState(false);
  const [status, setStatus]   = useState("");
  const [progress, setProgress] = useState(null);   // {scanned, total, level}
  const [error, setError]     = useState("");
  const [result, setResult]   = useState(null);

  useEffect(() => {
    const cancelLevels = loadLevelsWithRetry(getLevels, {
      onLevels: ls => { setLevels(ls); if (!levelName) setLevel(ls[0].display); },
    });
    const cancelChapters = loadWithRetry(getChapters, {
      onData: cs => { setChapters(cs); if (!chapterName && cs.length) setChapter(cs[0].name); },
    });
    window._nwMedalCountEvent = (ev) => {
      if (ev.type === "status") {
        setStatus(ev.message);
      } else if (ev.type === "progress") {
        setProgress(ev);
      } else if (ev.type === "done") {
        setResult(ev);
        setStatus(ev.message);
        setRunning(false);
        setProgress(null);
      } else if (ev.type === "error") {
        setError(ev.message);
        setRunning(false);
        setProgress(null);
      }
    };
    return () => { cancelLevels(); cancelChapters(); window._nwMedalCountEvent = null; };
  }, []);

  // The community medal tables load in a background thread at bridge import, so
  // poll until the backend reports them ready before enabling the tier picker —
  // otherwise a fast boot would count against not-yet-loaded Topaz/BD data. Same
  // resilient poll the shipped single-tier page used.
  useEffect(() => {
    let cancelled = false;
    let attempts = 0;
    function poll() {
      if (cancelled) return;
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

  // Hydrate the last-used custom selection the first time the user picks Custom.
  useEffect(() => {
    if (scope === "Custom" && !customHydrated.current) {
      customHydrated.current = true;
      loadLastSelection("medal").then(s => { if (s.length) setCustomLevels(s); });
    }
  }, [scope]);

  function toggleTier(t) {
    setSel(s => { const n = { ...s }; n[t] ? delete n[t] : (n[t] = true); return n; });
    setResult(null);
  }

  function handleCustomLevelsChange(next) {
    setCustomLevels(next);
    saveLastSelection("medal", next).catch(() => {});
    setResult(null);
  }

  const selectedTiers = TIERS.filter(t => sel[t]);

  function targetForScope() {
    if (scope === "Level")   return levelName;
    if (scope === "Chapter") return chapterName;
    if (scope === "Custom")  return JSON.stringify(customLevels);
    return "";   // Game
  }

  const scopeReady =
    scope === "Level"   ? !!levelName :
    scope === "Chapter" ? !!chapterName :
    scope === "Custom"  ? customLevels.length > 0 :
    true;

  const canRun = !running && dataReady && scopeReady && selectedTiers.length > 0;

  async function handleRun() {
    setError(""); setStatus(""); setResult(null); setProgress(null);
    setRunning(true);
    try {
      const r = await countMedalsScope(
        SCOPES[scope], targetForScope(), JSON.stringify(selectedTiers));
      if (!r.ok) { setError(r.error); setRunning(false); }
    } catch {
      setError("Run failed."); setRunning(false);
    }
  }

  async function handleStop() {
    await stopCountMedals();
    setStatus("Stopping...");
  }

  const progressPct = progress && progress.total
    ? Math.round((progress.scanned / progress.total) * 100) : 0;

  return (
    <>
      <PageHead crumb="Leaderboard Tools" title="MEDAL" accentWord="COUNT" />
      <div className="body">
        <div className="panel-left">
          <div className="form">
            <Field label="Scope">
              <Seg options={Object.keys(SCOPES)} value={scope}
                   onChange={v => { setScope(v); setResult(null); }} />
              <div className="muted" style={{ fontSize: 10, marginTop: 4 }}>
                {SCOPE_DESC[scope]}
              </div>
            </Field>

            {scope === "Level" && (
              <Field label="Level">
                <select className="input" value={levelName}
                        onChange={e => { setLevel(e.target.value); setResult(null); }}
                        disabled={running}>
                  {levels.map(l => (
                    <option key={l.internal} value={l.display}>{l.display}</option>
                  ))}
                </select>
              </Field>
            )}

            {scope === "Chapter" && (
              <Field label="Chapter">
                <select className="input" value={chapterName}
                        onChange={e => { setChapter(e.target.value); setResult(null); }}
                        disabled={running}>
                  {chapters.map(c => (
                    <option key={c.name} value={c.name}>{c.name}</option>
                  ))}
                </select>
              </Field>
            )}

            {scope === "Custom" && (
              <Field label="Custom stages">
                <div style={{ display: "flex", gap: 8 }}>
                  <Btn kind="ghost" size="sm" onClick={() => setPickerOpen(true)} disabled={running}>
                    {customLevels.length ? `${customLevels.length} stages selected` : "Pick stages…"}
                  </Btn>
                  {customLevels.length > 0 && (
                    <Btn kind="ghost" size="sm" disabled={running}
                         onClick={() => handleCustomLevelsChange([])}>Clear</Btn>
                  )}
                </div>
              </Field>
            )}

            <Field label="Medal tiers">
              <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
                {TIERS.map(t => (
                  <Cb key={t} on={!!sel[t]} onChange={() => toggleTier(t)}
                      label={t} />
                ))}
              </div>
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

        <div className="panel-right" style={{ overflowY: "auto" }}>
          {running ? (
            <div className="muted" style={{ padding: 32, fontSize: 12, textAlign: "center", margin: "auto" }}>
              <div>{status || "Scanning…"}</div>
              {progress && progress.total > 1 && (
                <div style={{ marginTop: 12 }}>
                  <div style={{ height: 4, width: 200, margin: "0 auto", background: "var(--surface-2)",
                                borderRadius: 2, overflow: "hidden" }}>
                    <div style={{ height: "100%", width: `${progressPct}%`,
                                  background: "var(--accent)", transition: "width 0.2s" }} />
                  </div>
                  <div style={{ marginTop: 6 }}>
                    {progress.scanned}/{progress.total} levels ({progressPct}%)
                  </div>
                </div>
              )}
            </div>
          ) : result && !result.stopped ? (
            <MedalResult result={result} />
          ) : result && result.stopped ? (
            <div className="muted" style={{ padding: 32, fontSize: 12, textAlign: "center", margin: "auto" }}>
              Stopped — partial results discarded.
            </div>
          ) : (
            <div className="muted" style={{ padding: 32, fontSize: 12, textAlign: "center", margin: "auto" }}>
              Pick a scope and one or more tiers, then press Count.
            </div>
          )}
        </div>
      </div>

      <LevelPickerModal
        open={pickerOpen}
        onClose={() => setPickerOpen(false)}
        value={customLevels}
        onChange={handleCustomLevelsChange}
        levels={levels}
        chapters={chapters}
      />
    </>
  );
}

// Match the shared table idiom (AvgRankings / LevelSearch). Sticky header keeps
// zIndex:2 so the gradient MedalBadge (translateZ layer) can't paint over it.
const TH = { padding: "4px 8px", fontWeight: 600, fontSize: "0.91em", borderBottom: "1px solid var(--border)", textAlign: "left" };
const TD = { padding: "3px 8px", fontSize: "1em" };

function csvCell(v) {
  const s = String(v ?? "");
  return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

// Rows-of-cells for copy/export: Level + (exactly, at-least) pair per selected
// tier, plus a Totals row. Error/absent cells come through blank.
function buildTable(result) {
  const tiers = result.tiers || [];
  const rows = result.rows || [];
  const grand = result.grand || {};
  const header = ["Level"];
  tiers.forEach(t => header.push(`${t} exactly`, `${t} at least`));
  const body = rows.map(r => {
    const line = [r.level];
    tiers.forEach(t => {
      const c = r.tiers && r.tiers[t];
      line.push(c ? c.exactly : "", c ? c.at_least : "");
    });
    return line;
  });
  const totals = ["Total"];
  tiers.forEach(t => { const g = grand[t] || {}; totals.push(g.exactly ?? 0, g.at_least ?? 0); });
  return [header, ...body, totals];
}

// Per-tier extremes across the scanned levels (multi-level highlights block).
// Ranks by both "at least" (medal earned, incl. faster tiers) and "exactly".
// Levels where a tier doesn't chart are skipped for that tier; ties resolve to
// the first level in scan order.
function computeExtremes(result) {
  const tiers = result.tiers || [];
  const rows = (result.rows || []).filter(r => r.tiers);
  return tiers.map(t => {
    const pts = rows
      .filter(r => r.tiers[t])
      .map(r => ({ level: r.level, al: r.tiers[t].at_least, ex: r.tiers[t].exactly }));
    if (!pts.length) return { tier: t, empty: true };
    const pick = (key, dir) => pts.reduce((best, p) =>
      (dir === "max" ? p[key] > best[key] : p[key] < best[key]) ? p : best, pts[0]);
    return {
      tier: t,
      mostAl: pick("al", "max"), leastAl: pick("al", "min"),
      mostEx: pick("ex", "max"), leastEx: pick("ex", "min"),
    };
  });
}

// ── Results: grand-total tier cards + per-stage table ────────────────────────
function MedalResult({ result }) {
  const tiers = result.tiers || [];
  const rows = result.rows || [];
  const grand = result.grand || {};
  const multi = (result.level_count || rows.length) > 1;
  const [flash, setFlash] = useState("");

  function ping(msg) { setFlash(msg); setTimeout(() => setFlash(""), 1500); }

  function handleCopy() {
    const tsv = buildTable(result).map(r => r.join("\t")).join("\n");
    try { navigator.clipboard.writeText(tsv); ping("Copied"); }
    catch { ping("Copy failed"); }
  }

  async function handleExport() {
    const csv = buildTable(result).map(r => r.map(csvCell).join(",")).join("\n");
    try {
      const res = await saveTextFile("medal-count.csv", csv);
      if (res && res.ok) ping("Saved");
      else if (res && res.cancelled) { /* user dismissed the dialog */ }
      else ping("Export failed");
    } catch { ping("Export failed"); }
  }

  return (
    <div style={{ width: "100%", padding: "12px 4px" }}>
      <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, alignItems: "center", marginBottom: 6, paddingRight: 14 }}>
        {flash && <span className="muted" style={{ fontSize: 11 }}>{flash}</span>}
        <Btn kind="ghost" size="sm" onClick={handleCopy}>Copy</Btn>
        <Btn kind="ghost" size="sm" onClick={handleExport}>Export CSV</Btn>
      </div>
      <div className="muted" style={{ fontSize: 12, textAlign: "center", marginBottom: 16 }}>
        {result.scope || "Level"}
        {multi && ` · ${result.level_count} levels`}
        {result.failed_levels > 0 && ` · ${result.failed_levels} board(s) unavailable`}
      </div>

      {/* Per-tier grand totals */}
      <div style={{ display: "flex", gap: 16, justifyContent: "center", flexWrap: "wrap", marginBottom: 8 }}>
        {tiers.map(t => {
          const g = grand[t] || { exactly: 0, at_least: 0 };
          return (
            <div key={t} style={{
              minWidth: 132, textAlign: "center",
              padding: "14px 18px", borderRadius: 2,
              background: "rgba(255,255,255,0.05)",
              border: "1px solid rgba(255,255,255,0.15)",
            }}>
              <div style={{ fontSize: "1.25em", lineHeight: 1, marginBottom: 10 }}>
                <MedalBadge medal={t} plain />
              </div>
              <div style={{
                fontSize: "2.7em", fontWeight: 700, lineHeight: 1,
                fontFamily: "var(--display-font)", color: "var(--accent)",
              }}>
                {g.exactly.toLocaleString()}
              </div>
              <div style={{ fontSize: 11, color: "var(--text-3)", marginTop: 6 }}>
                exactly this tier
              </div>
              <div style={{ fontSize: 11, color: "var(--text-3)", marginTop: 2 }}>
                at least this tier: {g.at_least.toLocaleString()}
              </div>
            </div>
          );
        })}
      </div>

      <div className="muted" style={{ fontSize: 11, textAlign: "center", marginBottom: 6 }}>
        {result.grand_total.toLocaleString()} player runs land in {tiers.length === 1 ? "this tier" : "one of the selected tiers"}
        {" "}across {multi ? "the scope" : "this level"}.
      </div>
      <div style={{ fontSize: 10, color: "var(--text-3)", textAlign: "center",
                    maxWidth: 460, margin: "0 auto", marginBottom: multi ? 18 : 4 }}>
        Only players on the community cheaterlist are excluded. A cheater who isn't on
        that list yet still counts toward these totals.
      </div>

      {/* Per-stage breakdown */}
      {multi && (
        <div style={{ overflowX: "auto" }}>
          <table className="nwt-hover-rows" style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead style={{ position: "sticky", top: 0, background: "var(--bg-2)", zIndex: 2 }}>
              <tr>
                <th style={TH}>Level</th>
                {tiers.map(t => (
                  <th key={t} style={{ ...TH, textAlign: "right", whiteSpace: "nowrap" }}>
                    <MedalBadge medal={t} plain />
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => (
                <tr key={i} style={{ borderBottom: "1px solid var(--border)" }}>
                  <td style={TD}>
                    {r.level}
                    {r.error && <span style={{ color: "var(--bad)", marginLeft: 6 }}>· {r.error}</span>}
                  </td>
                  {tiers.map(t => {
                    const cell = r.tiers && r.tiers[t];
                    return (
                      <td key={t} style={{ ...TD, textAlign: "right", whiteSpace: "nowrap" }}>
                        {cell
                          ? <><strong>{cell.exactly.toLocaleString()}</strong>
                              <span style={{ color: "var(--text-3)" }}> / {cell.at_least.toLocaleString()}≥</span></>
                          : <span style={{ color: "var(--text-3)" }}>—</span>}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr style={{ borderTop: "2px solid var(--border)", fontWeight: 700 }}>
                <td style={TD}>Total</td>
                {tiers.map(t => {
                  const g = grand[t] || { exactly: 0, at_least: 0 };
                  return (
                    <td key={t} style={{ ...TD, textAlign: "right", whiteSpace: "nowrap" }}>
                      {g.exactly.toLocaleString()}
                      <span style={{ color: "var(--text-3)", fontWeight: 400 }}> / {g.at_least.toLocaleString()}≥</span>
                    </td>
                  );
                })}
              </tr>
            </tfoot>
          </table>
          <div className="muted" style={{ fontSize: 10, marginTop: 8, textAlign: "center" }}>
            Cell = <strong>exactly</strong> / at-least this tier. Cheater-filtered.
          </div>
        </div>
      )}

      {/* Per-level highlights — most/fewest per tier across the scope */}
      {multi && (() => {
        const ext = computeExtremes(result).filter(e => !e.empty);
        if (!ext.length) return null;
        const cell = (p, key) => (
          <>{p.level} <span style={{ color: "var(--text-3)" }}>· {p[key].toLocaleString()}</span></>
        );
        return (
          <div style={{ marginTop: 22 }}>
            <div className="muted" style={{ fontSize: 10, textTransform: "uppercase",
                                            letterSpacing: 0.5, textAlign: "center", marginBottom: 8 }}>
              Per-level highlights
            </div>
            <div style={{ overflowX: "auto" }}>
              <table className="nwt-hover-rows" style={{ width: "100%", borderCollapse: "collapse" }}>
                <thead style={{ position: "sticky", top: 0, background: "var(--bg-2)", zIndex: 2 }}>
                  <tr>
                    <th style={TH}>Tier</th>
                    <th style={{ ...TH, whiteSpace: "nowrap" }}>Most earned (≥)</th>
                    <th style={{ ...TH, whiteSpace: "nowrap" }}>Fewest earned (≥)</th>
                    <th style={{ ...TH, whiteSpace: "nowrap" }}>Most (exactly)</th>
                    <th style={{ ...TH, whiteSpace: "nowrap" }}>Fewest (exactly)</th>
                  </tr>
                </thead>
                <tbody>
                  {ext.map(e => (
                    <tr key={e.tier} style={{ borderBottom: "1px solid var(--border)" }}>
                      <td style={{ ...TD, whiteSpace: "nowrap" }}><MedalBadge medal={e.tier} plain /></td>
                      <td style={{ ...TD, whiteSpace: "nowrap" }}>{cell(e.mostAl, "al")}</td>
                      <td style={{ ...TD, whiteSpace: "nowrap" }}>{cell(e.leastAl, "al")}</td>
                      <td style={{ ...TD, whiteSpace: "nowrap" }}>{cell(e.mostEx, "ex")}</td>
                      <td style={{ ...TD, whiteSpace: "nowrap" }}>{cell(e.leastEx, "ex")}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        );
      })()}
    </div>
  );
}
