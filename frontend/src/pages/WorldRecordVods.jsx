import React, { useState, useEffect } from "react";
import { PageHead, Field, Seg, Btn, Icon } from "../shared.jsx";
import { getLevels, getWorldRecord, getResourcesStatus, openExternalUrl } from "../api.js";
import { loadLevelsWithRetry } from "../lib/retryLevels.js";

const GOLD = "#ffd700";

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
    const cancelLevels = loadLevelsWithRetry(getLevels, {
      onLevels: ls => { setLevels(ls); setLevel(ls[0].display); }
    });
    getResourcesStatus().then(setStatus).catch(() => {});
    return cancelLevels;
  }, []);

  useEffect(() => {
    if (!level || !status.wrs_loaded) return;
    setLoading(true);
    setVideoError(false);
    getWorldRecord(level, PLATFORM_KEY[platform])
      .then(r => setWr(r || null))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [level, platform, status.wrs_loaded]);

  // Self-rearming poll until WRs are loaded. Data re-fetch happens via the
  // [level, platform, status.wrs_loaded] effect above when status flips.
  useEffect(() => {
    let cancelled = false;
    function poll() {
      if (cancelled) return;
      getResourcesStatus().then(s => {
        if (cancelled) return;
        setStatus(s);
        if (s.wrs_loaded || s.errors?.wrs) return;
        setTimeout(poll, 1000);
      }).catch(() => { if (!cancelled) setTimeout(poll, 1000); });
    }
    if (!status.wrs_loaded && !status.errors?.wrs) poll();
    return () => { cancelled = true; };
  }, []);

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
    ? (status.errors?.wrs ? "Could not reach WR sheet — check connection." : "Loading resources…")
    : null;

  return (
    <>
      <PageHead crumb="Resources" title={<>WORLD <span className="accent">RECORD</span> VODs</>} />
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
              <>
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
                <Field label="Runner">
                  <div style={{ fontSize: 12, fontWeight: 600 }}>{wr.player}</div>
                </Field>
                {wr.date && (
                  <Field label="Date">
                    <div style={{ fontSize: 12, color: "var(--muted)", fontFamily: "var(--mono-font)" }}>{wr.date}</div>
                  </Field>
                )}
                {wr.title && (
                  <Field label="Title">
                    <div style={{ fontSize: 11, color: "var(--muted)", wordBreak: "break-word" }}>{wr.title}</div>
                  </Field>
                )}
                <div style={{ marginTop: 4 }}>
                  <Btn kind="ghost" size="sm" onClick={() => handleOpen(wr.youtube_url)}>Open in YouTube</Btn>
                </div>
              </>
            )}
            {headerNote && <div className="muted" style={{ fontSize: 11 }}>{headerNote}</div>}
          </div>
        </div>
        <div className="panel-right" style={{ display: "flex", flexDirection: "column", overflow: "hidden" }}>
          {videoId ? (
            <div style={{
              position: "relative", width: "100%", paddingTop: "56.25%",
              background: "#000",
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
            <div className="muted" style={{ padding: 32, fontSize: 12, textAlign: "center" }}>
              {loading ? "Loading…"
                : status.wrs_loaded
                  ? `No WR video listed for ${level || "this stage"} on ${platform} yet.`
                  : "Resources not loaded."}
            </div>
          )}
        </div>
      </div>
    </>
  );
}
