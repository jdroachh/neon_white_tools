import React, { useState, useEffect } from "react";
import { PageHead, Field, Seg, Btn, Icon } from "../shared.jsx";
import { getLevels, getWorldRecord, getResourcesStatus, openExternalUrl } from "../api.js";

const GOLD = "#ffd700";

const TH = { padding: "4px 8px", fontSize: 9, fontWeight: 700, letterSpacing: 0.8, color: "var(--text-3)", textTransform: "uppercase", textAlign: "left", borderBottom: "1px solid var(--border)", whiteSpace: "nowrap" };
const TD = { padding: "3px 8px", fontSize: 11 };

const PLATFORMS = ["PC", "Switch", "PlayStation"];
const PLATFORM_KEY = { "PC": "pc", "Switch": "switch", "PlayStation": "playstation" };

function extractYouTubeId(url) {
  const m = (url || "").match(/(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/)([A-Za-z0-9_-]{11})/);
  return m ? m[1] : null;
}

export default function WorldRecordVods() {
  const [levels, setLevels]     = useState([]);
  const [level, setLevel]       = useState("");
  const [platform, setPlatform] = useState("PC");
  const [wr, setWr]             = useState(null);
  const [status, setStatus]     = useState({ wrs_loaded: false, error: null });
  const [loading, setLoading]   = useState(false);
  const [videoError, setVideoError] = useState(false);

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
    setVideoError(false);
    getWorldRecord(level, PLATFORM_KEY[platform])
      .then(r => {
        setWr(r || null);
        return getResourcesStatus();
      })
      .then(setStatus)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [level, platform]);

  // Poll while resources aren't loaded yet; re-fetch WR the moment they become ready
  useEffect(() => {
    if (status.wrs_loaded || status.error || !level) return;
    const id = setTimeout(() => {
      getResourcesStatus().then(s => {
        setStatus(s);
        if (s.wrs_loaded) {
          setLoading(true);
          setVideoError(false);
          getWorldRecord(level, PLATFORM_KEY[platform])
            .then(r => setWr(r || null))
            .catch(() => {})
            .finally(() => setLoading(false));
        }
      }).catch(() => {});
    }, 1000);
    return () => clearTimeout(id);
  }, [status.wrs_loaded, status.error, level, platform]);

  // Reset video error when WR changes
  useEffect(() => { setVideoError(false); }, [wr]);

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

  const videoId = wr ? extractYouTubeId(wr.youtube_url) : null;

  const headerNote = !status.wrs_loaded
    ? (status.error ? "Could not reach WR sheet — check connection." : "Loading resources…")
    : null;

  return (
    <>
      <PageHead crumb="Resources" title="WORLD RECORD VODs" accentWord="" />
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
            <Field label="Platform">
              <Seg options={PLATFORMS} value={platform} onChange={setPlatform} />
            </Field>
            {wr && (
              <Field label="World Record time">
                <div style={{
                  display: "inline-flex", alignItems: "center", gap: 8,
                  padding: "6px 12px",
                  border: `1px solid ${GOLD}`,
                  borderRadius: 4,
                  color: GOLD,
                  fontFamily: "var(--mono-font)",
                  fontSize: 13,
                  fontWeight: 600,
                }}>
                  <Icon name="trophy" size={14} />
                  {wr.time_formatted}
                </div>
              </Field>
            )}
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
                  <Btn kind="ghost" size="sm" onClick={() => handleOpen(wr.youtube_url)}>
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
                  title={wr.title || "World Record"}
                />
              )}
            </div>
          ) : (
            <div className="muted" style={{
              padding: 32, fontSize: 12, textAlign: "center",
              borderBottom: "1px solid var(--border)",
            }}>
              {loading ? "Loading…"
                : status.wrs_loaded
                  ? `No WR video listed for ${level || "this stage"} on ${platform} yet.`
                  : "Resources not loaded."}
            </div>
          )}
          {wr && (
            <table style={{ width: "100%", borderCollapse: "collapse", borderBottom: "1px solid var(--border)", background: "var(--bg-1)" }}>
              <thead style={{ background: "var(--bg-2)" }}>
                <tr>
                  <th style={TH}>Runner</th>
                  <th style={TH}>Time</th>
                  <th style={TH}>Date (YYYY-MM-DD)</th>
                  <th style={{ ...TH, width: "100%" }}>Title</th>
                  <th style={TH} />
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td style={{ ...TD, fontWeight: 600, whiteSpace: "nowrap" }}>{wr.player}</td>
                  <td style={{ ...TD, fontFamily: "var(--mono-font)", whiteSpace: "nowrap" }}>{wr.time_formatted}</td>
                  <td style={{ ...TD, color: "var(--muted)", whiteSpace: "nowrap" }}>{wr.date}</td>
                  <td style={{ ...TD, color: "var(--muted)", fontSize: 10, maxWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {wr.title}
                  </td>
                  <td style={{ ...TD, textAlign: "right", whiteSpace: "nowrap" }}>
                    <Btn kind="ghost" size="sm" onClick={() => handleOpen(wr.youtube_url)}>Open in YouTube</Btn>
                  </td>
                </tr>
              </tbody>
            </table>
          )}
        </div>
      </div>
    </>
  );
}
