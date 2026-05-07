import React, { useState, useEffect } from "react";
import { PageHead, Field, Seg, Btn } from "../shared.jsx";
import { getLevels, getVideos, getResourcesStatus, openExternalUrl, getMedalTimes } from "../api.js";

const TH = { padding: "4px 8px", fontWeight: 600, fontSize: 10, borderBottom: "1px solid var(--border)", textAlign: "left" };
const TD = { padding: "3px 8px", fontSize: 11 };

const MEDALS = ["Emerald", "Amethyst", "Sapphire"];
const MEDAL_COLOR = { Emerald: "#54d09a", Amethyst: "#b886ff", Sapphire: "#5db1ff" };

function extractYouTubeId(url) {
  const m = (url || "").match(/(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/)([A-Za-z0-9_-]{11})/);
  return m ? m[1] : null;
}

function formatSeconds(secs) {
  if (secs == null || isNaN(secs)) return "—";
  if (secs < 60) return `${secs.toFixed(3)}s`;
  const m = Math.floor(secs / 60);
  const s = secs - m * 60;
  return `${m}:${s.toFixed(3).padStart(6, "0")}`;
}

export default function RouteVideos() {
  const [levels, setLevels]       = useState([]);
  const [level, setLevel]         = useState("");
  const [medal, setMedal]         = useState("Sapphire");
  const [rows, setRows]           = useState([]);
  const [status, setStatus]       = useState({ ghosts_loaded: false, videos_loaded: false, error: null });
  const [loading, setLoading]     = useState(false);
  const [selectedIdx, setSelectedIdx] = useState(0);
  const [medalTimes, setMedalTimes]   = useState({});
  const [videoError, setVideoError]   = useState(false);

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
    setSelectedIdx(0);
    getVideos(level, medal)
      .then(r => setRows(Array.isArray(r) ? r : []))
      .finally(() => setLoading(false));
  }, [level, medal]);

  useEffect(() => {
    if (!level) { setMedalTimes({}); return; }
    getMedalTimes(level).then(t => setMedalTimes(t || {})).catch(() => setMedalTimes({}));
  }, [level]);

  // Reset error state when the selected video changes
  useEffect(() => { setVideoError(false); }, [selectedIdx]);

  // Listen for YouTube iframe API error messages
  useEffect(() => {
    function onMessage(e) {
      if (e.origin !== "https://www.youtube.com") return;
      try {
        const data = typeof e.data === "string" ? JSON.parse(e.data) : e.data;
        if (data?.event === "infoDelivery" && data?.info?.error) setVideoError(true);
        if (data?.event === "onError") setVideoError(true);
      } catch {}
    }
    window.addEventListener("message", onMessage);
    return () => window.removeEventListener("message", onMessage);
  }, []);

  function handleOpen(url) { openExternalUrl(url).catch(() => {}); }

  const selected   = rows[selectedIdx];
  const videoId    = selected ? extractYouTubeId(selected.youtube_url) : null;
  const targetSecs = medalTimes[medal.toLowerCase()];
  const displayTarget = targetSecs != null ? targetSecs - 0.001 : targetSecs;

  const headerNote = !status.videos_loaded
    ? (status.error ? "Could not reach Videos sheet — check connection." : "Loading resources…")
    : null;

  return (
    <>
      <PageHead crumb="Resources" title="ROUTE" accentWord="VIDEOS" />
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
        <div className="panel-right" style={{ display: "flex", flexDirection: "column", overflow: "hidden" }}>
          {videoId ? (
            <div style={{
              position: "relative", width: "100%", paddingTop: "56.25%",
              background: "#000", borderBottom: "1px solid var(--border)",
            }}>
              {videoError ? (
                <div style={{
                  position: "absolute", top: 0, left: 0, width: "100%", height: "100%",
                  display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center",
                  gap: 12, color: "var(--muted)", fontSize: 12,
                }}>
                  <span>Could not load video in app.</span>
                  <Btn kind="ghost" size="sm" onClick={() => handleOpen(selected.youtube_url)}>
                    Open in YouTube
                  </Btn>
                </div>
              ) : (
                <iframe
                  key={videoId}
                  src={`https://www.youtube.com/embed/${videoId}?rel=0&modestbranding=1&playsinline=1&enablejsapi=1&origin=${encodeURIComponent(window.location.origin)}`}
                  style={{ position: "absolute", top: 0, left: 0, width: "100%", height: "100%", border: 0 }}
                  allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
                  allowFullScreen
                  referrerPolicy="strict-origin-when-cross-origin"
                  title={selected ? selected.title : "video"}
                />
              )}
            </div>
          ) : (
            <div className="muted" style={{
              padding: 32, fontSize: 12, textAlign: "center",
              borderBottom: "1px solid var(--border)",
            }}>
              {loading ? "Loading…"
                : status.videos_loaded
                  ? `No ${medal} videos indexed for ${level || "this stage"} yet.`
                  : "Resources not loaded."}
            </div>
          )}
          <div style={{ flex: 1, overflow: "auto" }}>
            {rows.length > 0 && (
              <table style={{ width: "100%", borderCollapse: "collapse" }}>
                <thead style={{ position: "sticky", top: 0, background: "var(--bg-2)" }}>
                  <tr>
                    <th style={{ ...TH, width: "100%" }}>Route</th>
                    <th style={{ ...TH, whiteSpace: "nowrap", textAlign: "right" }}></th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r, i) => {
                    const isActive = i === selectedIdx;
                    return (
                      <tr key={i}
                          onClick={() => setSelectedIdx(i)}
                          style={{
                            borderBottom: "1px solid var(--border)",
                            cursor: "pointer",
                            background: isActive ? "var(--bg-2)" : "transparent",
                          }}>
                        <td style={{ ...TD, width: "100%",
                                     color: isActive ? "var(--accent)" : undefined,
                                     fontWeight: isActive ? 600 : undefined }}>
                          {isActive ? "▶ " : ""}{r.title || "(untitled)"}
                        </td>
                        <td style={{ ...TD, whiteSpace: "nowrap", textAlign: "right" }}
                            onClick={e => e.stopPropagation()}>
                          <Btn kind="ghost" size="sm" onClick={() => handleOpen(r.youtube_url)}>
                            Open in YouTube
                          </Btn>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </div>
        </div>
      </div>
    </>
  );
}
