import React, { useState, useEffect } from "react";
import { PageHead, Field, Seg, Btn } from "../shared.jsx";
import { getLevels, getGhosts, getResourcesStatus, openExternalUrl, getMedalTimes } from "../api.js";
import { loadLevelsWithRetry } from "../lib/retryLevels.js";

const TH = { padding: "4px 8px", fontWeight: 600, fontSize: 10, borderBottom: "1px solid var(--border)", textAlign: "left" };
const TD = { padding: "3px 8px", fontSize: 11 };

const MEDALS = ["Emerald", "Amethyst", "Sapphire"];
const MEDAL_COLOR = { Emerald: "#54d09a", Amethyst: "#b886ff", Sapphire: "#5db1ff" };

function formatSeconds(secs) {
  if (secs == null || isNaN(secs)) return "—";
  if (secs < 60) return `${secs.toFixed(3)}s`;
  const m = Math.floor(secs / 60);
  const s = secs - m * 60;
  return `${m}:${s.toFixed(3).padStart(6, "0")}`;
}

export default function Ghosts() {
  const [levels, setLevels]       = useState([]);
  const [level, setLevel]         = useState("");
  const [medal, setMedal]         = useState("Sapphire");
  const [rows, setRows]           = useState([]);
  const [status, setStatus]       = useState({ ghosts_loaded: false, videos_loaded: false, error: null });
  const [loading, setLoading]     = useState(false);
  const [medalTimes, setMedalTimes] = useState({});

  useEffect(() => {
    const cancelLevels = loadLevelsWithRetry(getLevels, {
      onLevels: ls => { setLevels(ls); setLevel(ls[0].display); }
    });
    getResourcesStatus().then(setStatus).catch(() => {});
    return cancelLevels;
  }, []);

  useEffect(() => {
    if (!level || !status.ghosts_loaded) return;
    setLoading(true);
    getGhosts(level, medal)
      .then(r => setRows(Array.isArray(r) ? r : []))
      .finally(() => setLoading(false));
  }, [level, medal, status.ghosts_loaded]);

  // Self-rearming poll until ghosts are loaded. Re-fetch happens via the
  // [level, medal, status.ghosts_loaded] effect above when status flips.
  useEffect(() => {
    let cancelled = false;
    function poll() {
      if (cancelled) return;
      getResourcesStatus().then(s => {
        if (cancelled) return;
        setStatus(s);
        if (s.ghosts_loaded || s.errors?.ghosts) return;
        setTimeout(poll, 1000);
      }).catch(() => { if (!cancelled) setTimeout(poll, 1000); });
    }
    if (!status.ghosts_loaded && !status.errors?.ghosts) poll();
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    if (!level) { setMedalTimes({}); return; }
    getMedalTimes(level).then(t => setMedalTimes(t || {})).catch(() => setMedalTimes({}));
  }, [level]);

  function handleOpen(url) { openExternalUrl(url).catch(() => {}); }

  const targetSecs = medalTimes[medal.toLowerCase()];
  const displayTarget = targetSecs != null ? targetSecs - 0.001 : targetSecs;

  const headerNote = !status.ghosts_loaded
    ? (status.errors?.ghosts ? "Could not reach Ghosts sheet — check connection." : "Loading resources…")
    : null;

  return (
    <>
      <PageHead crumb="Resources" title="GHOSTS" accentWord="" />
      <div className="body">
        <div className="panel-left">
          <div className="form">
            <Field label="Stage">
              <select className="input" value={level} onChange={e => setLevel(e.target.value)}>
                {levels.map(l => (
                  <option key={l.internal} value={l.display}>{l.display}</option>
                ))}
              </select>
            </Field>
            <Field label="Medal">
              <div className="medal-seg">
                <Seg options={MEDALS} value={medal} onChange={setMedal} />
              </div>
            </Field>
            <Field label={`${medal} target time`}>
              <div style={{
                display: "inline-flex", alignItems: "center", gap: 8,
                padding: "6px 12px",
                border: `1px solid ${MEDAL_COLOR[medal]}`,
                borderRadius: 4,
                color: MEDAL_COLOR[medal],
                fontFamily: "var(--mono-font)",
                fontSize: 13,
                fontWeight: 600,
              }}>
                <span style={{
                  width: 8, height: 8, borderRadius: "50%",
                  background: MEDAL_COLOR[medal],
                }} />
                {formatSeconds(displayTarget)}
              </div>
            </Field>
            {headerNote && <div className="muted" style={{ fontSize: 11 }}>{headerNote}</div>}
          </div>
        </div>
        <div className="panel-right" style={{ overflow: "auto" }}>
          {rows.length > 0 ? (
            <table style={{ width: "100%", borderCollapse: "collapse" }}>
              <thead style={{ position: "sticky", top: 0, background: "var(--bg-2)" }}>
                <tr>
                  <th style={{ ...TH, width: "100%" }}>Player</th>
                  <th style={{ ...TH, whiteSpace: "nowrap" }}>Time</th>
                  <th style={{ ...TH, whiteSpace: "nowrap", textAlign: "right" }}></th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r, i) => (
                  <tr key={i} style={{ borderBottom: "1px solid var(--border)" }}>
                    <td style={{ ...TD, width: "100%" }}>{r.player}</td>
                    <td style={{ ...TD, whiteSpace: "nowrap" }}>{r.time}</td>
                    <td style={{ ...TD, whiteSpace: "nowrap", textAlign: "right" }}>
                      <Btn kind="ghost" size="sm" onClick={() => handleOpen(r.drive_url)}>
                        Open in browser
                      </Btn>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div className="muted" style={{ padding: 32, fontSize: 12, textAlign: "center" }}>
              {loading ? "Loading…"
                : status.ghosts_loaded
                  ? `No ${medal} ghosts indexed for ${level || "this stage"} yet.`
                  : "Resources not loaded."}
            </div>
          )}
        </div>
      </div>
    </>
  );
}
