import React, { useState, useEffect } from "react";
import { PageHead, Field, Seg, Btn } from "../shared.jsx";
import { getLevels, getGhosts, getResourcesStatus, openExternalUrl } from "../api.js";

const TH = { padding: "4px 8px", fontWeight: 600, fontSize: 10, borderBottom: "1px solid var(--border)", textAlign: "left" };
const TD = { padding: "3px 8px", fontSize: 11 };

const MEDALS = ["Emerald", "Amethyst", "Sapphire"];

export default function Ghosts() {
  const [levels, setLevels]   = useState([]);
  const [level, setLevel]     = useState("");
  const [medal, setMedal]     = useState("Sapphire");
  const [rows, setRows]       = useState([]);
  const [status, setStatus]   = useState({ ghosts_loaded: false, videos_loaded: false, error: null });
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    getLevels().then(ls => {
      setLevels(ls);
      if (ls.length) setLevel(ls[0].display);
    });
    getResourcesStatus().then(setStatus).catch(() => {});
  }, []);

  useEffect(() => {
    if (!level) return;
    setLoading(true);
    getGhosts(level, medal)
      .then(r => setRows(Array.isArray(r) ? r : []))
      .finally(() => setLoading(false));
  }, [level, medal]);

  function handleOpen(url) { openExternalUrl(url).catch(() => {}); }

  const headerNote = !status.ghosts_loaded
    ? (status.error ? "Could not reach Ghosts sheet — check connection." : "Loading resources…")
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
              <Seg options={MEDALS} value={medal} onChange={setMedal} />
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
