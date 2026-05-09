import React, { useState, useEffect } from "react";
import { PageHead, Btn } from "../shared.jsx";
import { getGuides, openExternalUrl } from "../api.js";

const ALL_CATS = ["route", "technical", "playlist"];
const CAT_LABELS = { route: "Route guides", technical: "Technical guides", playlist: "Medal playlists" };
const CAT_COLORS = { route: "#00e09a", technical: "#5db1ff", playlist: "#b886ff" };
const TIER_COLORS = { Emerald: "#3ddc84", Amethyst: "#c77dff", Sapphire: "#6ab0ff" };

function extractYouTubeId(url) {
  const m = (url || "").match(/(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/)([A-Za-z0-9_-]{11})/);
  return m ? m[1] : null;
}

function VideoEmbed({ url, onOpenExternal }) {
  const [videoError, setVideoError] = useState(false);
  const ytId = extractYouTubeId(url);

  useEffect(() => {
    setVideoError(false);
    if (!ytId) return;
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
  }, [ytId]);

  if (!url) {
    return (
      <div className="muted" style={{ padding: "10px 0", fontSize: 11 }}>
        No video link available for this guide.
      </div>
    );
  }

  if (ytId) {
    return (
      <div style={{ position: "relative", width: "100%", paddingTop: "56.25%", background: "#000", borderRadius: 2, overflow: "hidden", marginTop: 8 }}>
        {videoError ? (
          <div style={{
            position: "absolute", top: 0, left: 0, width: "100%", height: "100%",
            display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center",
            gap: 10, color: "var(--muted)", fontSize: 12,
          }}>
            <span>Could not load video in app.</span>
            <Btn kind="ghost" size="sm" onClick={onOpenExternal}>Open in YouTube</Btn>
          </div>
        ) : (
          <iframe
            key={ytId}
            src={`https://www.youtube.com/embed/${ytId}?rel=0&modestbranding=1&playsinline=1&enablejsapi=1&origin=${encodeURIComponent(window.location.origin)}`}
            style={{ position: "absolute", top: 0, left: 0, width: "100%", height: "100%", border: 0 }}
            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
            allowFullScreen
            referrerPolicy="strict-origin-when-cross-origin"
            title="guide video"
          />
        )}
      </div>
    );
  }

  // Non-YouTube URL — just offer an open button.
  return (
    <div style={{ paddingTop: 8 }}>
      <Btn kind="ghost" size="sm" onClick={onOpenExternal}>Open link</Btn>
    </div>
  );
}

export default function Guides() {
  const [guides, setGuides]       = useState([]);
  const [loaded, setLoaded]       = useState(false);
  const [query, setQuery]         = useState("");
  const [categories, setCats]     = useState(new Set(ALL_CATS));
  const [level, setLevel]         = useState("");
  const [expandedIdx, setExpanded] = useState(null);

  useEffect(() => {
    getGuides()
      .then(r => setGuides(Array.isArray(r?.guides) ? r.guides : []))
      .catch(() => {})
      .finally(() => setLoaded(true));
  }, []);

  // Collapse expansion when filters change (avoids stale index).
  useEffect(() => { setExpanded(null); }, [query, categories, level]);

  function toggleCat(cat) {
    setCats(prev => {
      const next = new Set(prev);
      if (next.has(cat)) next.delete(cat); else next.add(cat);
      return next;
    });
  }

  const levelOptions = [...new Set(
    guides.filter(g => g.category === "route" && g.level).map(g => g.level)
  )].sort();

  const filtered = guides.filter(g => {
    if (!categories.has(g.category)) return false;
    if (g.category === "route" && level && g.level !== level) return false;
    const q = query.toLowerCase();
    if (!q) return true;
    return `${g.title} ${g.author} ${g.level || ""}`.toLowerCase().includes(q);
  });

  const fetchFailed = loaded && guides.length === 0;

  return (
    <>
      <PageHead crumb="Resources" title="COMMUNITY" accentWord="GUIDES" />
      <div style={{ padding: "10px 16px", borderBottom: "1px solid var(--border)", display: "flex", flexDirection: "column", gap: 8 }}>
        <input
          className="input"
          placeholder="Search guides by title, author, or level"
          value={query}
          onChange={e => setQuery(e.target.value)}
          style={{ width: "100%", boxSizing: "border-box" }}
        />
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap", alignItems: "center" }}>
          {ALL_CATS.map(cat => (
            <span key={cat}
              className={"seg-btn " + (categories.has(cat) ? "on" : "")}
              onClick={() => toggleCat(cat)}
              style={{ cursor: "pointer" }}>
              {CAT_LABELS[cat]}
            </span>
          ))}
          {categories.has("route") && levelOptions.length > 0 && (
            <select className="input" value={level} onChange={e => setLevel(e.target.value)}
              style={{ marginLeft: 4 }}>
              <option value="">All levels</option>
              {levelOptions.map(l => <option key={l} value={l}>{l}</option>)}
            </select>
          )}
        </div>
      </div>
      <div style={{ flex: 1, overflow: "auto", padding: "8px 16px" }}>
        {!loaded ? (
          <div className="muted" style={{ padding: 24, fontSize: 12 }}>Loading guides…</div>
        ) : fetchFailed ? (
          <div className="muted" style={{ padding: 24, fontSize: 12 }}>
            Couldn't load the guide sheet. Check your connection and restart the app.
          </div>
        ) : filtered.length === 0 ? (
          <div className="muted" style={{ padding: 24, fontSize: 12 }}>No guides match these filters.</div>
        ) : (
          <ul style={{ listStyle: "none", padding: 0, margin: 0, display: "flex", flexDirection: "column", gap: 4 }}>
            {filtered.map((g, i) => {
              const isOpen = expandedIdx === i;
              return (
                <li key={i} style={{
                  border: `1px solid ${isOpen ? "var(--accent)" : "var(--border)"}`,
                  borderRadius: 3,
                  overflow: "hidden",
                  transition: "border-color 0.1s",
                }}>
                  {/* Row header — click to toggle */}
                  <div
                    onClick={() => setExpanded(isOpen ? null : i)}
                    style={{
                      padding: "8px 12px",
                      display: "flex", alignItems: "center", gap: 8,
                      cursor: "pointer",
                      background: isOpen ? "color-mix(in srgb, var(--accent) 6%, var(--bg-2))" : "transparent",
                      userSelect: "none",
                    }}
                  >
                    {/* Caret */}
                    <span style={{
                      fontSize: 9, color: isOpen ? "var(--accent)" : "var(--text-3)",
                      transition: "transform 0.15s, color 0.1s",
                      display: "inline-block",
                      transform: isOpen ? "rotate(90deg)" : "rotate(0deg)",
                      flexShrink: 0,
                    }}>▶</span>

                    {/* Title + author */}
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                        <span style={{
                          fontWeight: 600, fontSize: 12,
                          color: isOpen ? "var(--accent)" : "var(--text-1)",
                        }}>
                          {g.category === "route" ? (g.level || g.title || "(untitled)") : (g.title || "(untitled)")}
                        </span>
                        {g.author && (
                          <span style={{
                            fontSize: 10, padding: "1px 6px",
                            background: "var(--surface-2)", borderRadius: 2,
                            color: "var(--text-2)", flexShrink: 0,
                          }}>
                            {g.author}
                          </span>
                        )}
                      </div>
                      <div style={{ display: "flex", gap: 4, flexWrap: "wrap", marginTop: 3 }}>
                        <span style={{
                          fontSize: 9, fontWeight: 700, letterSpacing: 0.5,
                          padding: "1px 5px", borderRadius: 1,
                          background: CAT_COLORS[g.category] + "22",
                          color: CAT_COLORS[g.category],
                          border: `1px solid ${CAT_COLORS[g.category]}55`,
                        }}>
                          {g.category.toUpperCase()}
                        </span>
                        {g.category === "route" && g.tier && (() => {
                          const tierName = g.tier.replace(/ \d+$/, "");
                          const tc = TIER_COLORS[tierName];
                          return (
                            <span style={{
                              fontSize: 9, fontWeight: 700, letterSpacing: 0.5,
                              padding: "1px 5px", borderRadius: 1,
                              background: tc ? tc + "22" : "var(--surface-2)",
                              color: tc || "var(--text-2)",
                              border: `1px solid ${tc ? tc + "55" : "transparent"}`,
                            }}>
                              {tierName}
                            </span>
                          );
                        })()}
                      </div>
                    </div>
                  </div>

                  {/* Expanded panel */}
                  {isOpen && (
                    <div style={{ padding: "0 12px 12px" }}>
                      <VideoEmbed
                        url={g.url}
                        onOpenExternal={() => openExternalUrl(g.url).catch(() => {})}
                      />
                    </div>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </>
  );
}
