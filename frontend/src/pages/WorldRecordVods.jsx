import React, { useState, useEffect } from "react";
import { PageHead, Field, Seg, Btn } from "../shared.jsx";
import { getLevels, getWorldRecord, getResourcesStatus, openExternalUrl } from "../api.js";

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
            <div style={{ padding: "8px 12px", display: "flex", alignItems: "center", gap: 12, borderBottom: "1px solid var(--border)" }}>
              <span style={{ ...TD, fontWeight: 600, flexShrink: 0 }}>{wr.player}</span>
              <span style={{ ...TD, fontFamily: "var(--mono-font)", flexShrink: 0 }}>{wr.time_formatted}</span>
              <span style={{ ...TD, color: "var(--muted)", flexShrink: 0 }}>{wr.date}</span>
              {wr.title && (
                <span style={{ ...TD, color: "var(--muted)", fontSize: 10, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", flex: 1 }}>
                  {wr.title}
                </span>
              )}
              <Btn kind="ghost" size="sm" onClick={() => handleOpen(wr.youtube_url)} style={{ flexShrink: 0 }}>
                Open in YouTube
              </Btn>
            </div>
          )}
        </div>
      </div>
    </>
  );
}
