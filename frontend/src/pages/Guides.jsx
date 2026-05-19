import React, { useState, useEffect } from "react";
import { PageHead, Btn } from "../shared.jsx";
import { getGuides, openExternalUrl, getConfig, saveConfigFields, getResourcesStatus } from "../api.js";

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

  return (
    <div style={{ paddingTop: 8 }}>
      <Btn kind="ghost" size="sm" onClick={onOpenExternal}>Open link</Btn>
    </div>
  );
}

// Three-state cycle icon: null → "watchlist" → "watched" → null
function WatchCycleBtn({ state, onClick }) {
  if (state === "watchlist") {
    return (
      <span title="In watchlist — click to mark watched" onClick={onClick}
        style={{ cursor: "pointer", fontSize: 14, userSelect: "none", flexShrink: 0, color: "var(--accent)", lineHeight: 1 }}>
        ✓
      </span>
    );
  }
  if (state === "watched") {
    return (
      <span title="Watched — click to clear" onClick={onClick}
        style={{ cursor: "pointer", fontSize: 14, userSelect: "none", flexShrink: 0, color: "#f87171", lineHeight: 1 }}>
        ✗
      </span>
    );
  }
  return (
    <span title="Add to watchlist" onClick={onClick}
      style={{ cursor: "pointer", fontSize: 14, userSelect: "none", flexShrink: 0, color: "var(--text-3)", opacity: 0.35, lineHeight: 1 }}>
      ○
    </span>
  );
}

export default function Guides() {
  const [guides, setGuides]        = useState([]);
  const [loaded, setLoaded]        = useState(false);
  const [query, setQuery]          = useState("");
  const [activeCat, setActiveCat]  = useState("route");
  const [level, setLevel]          = useState("");
  const [expandedIdx, setExpanded] = useState(null);

  // Watch state keyed by YouTube video ID — hydrated from config.
  // Combined into one object so functional setState always sees the latest of both.
  const [watchState, setWatchState] = useState({ watchlist: new Set(), watched: new Set() });
  const { watchlist, watched } = watchState;
  const [guidesLoaded, setGuidesLoaded] = useState(false);

  const [hideWatched, setHideWatched]     = useState(false);
  const [watchlistOnly, setWatchlistOnly] = useState(false);

  useEffect(() => {
    getConfig().then(cfg => {
      setWatchState({
        watchlist: new Set(Array.isArray(cfg.guide_watchlist) ? cfg.guide_watchlist : []),
        watched:   new Set(Array.isArray(cfg.guide_watched)   ? cfg.guide_watched   : []),
      });
      setHideWatched(!!cfg.guide_hide_watched);
      setWatchlistOnly(!!cfg.guide_watchlist_only);
    }).catch(() => {});
  }, []);

  useEffect(() => {
    getGuides()
      .then(r => {
        setGuides(Array.isArray(r?.guides) ? r.guides : []);
        setGuidesLoaded(!!r?.loaded);
      })
      .catch(() => {})
      .finally(() => setLoaded(true));
  }, []);

  // Self-rearming poll until guides_loaded flips, then re-fetch.
  useEffect(() => {
    if (!loaded || guidesLoaded) return;
    let cancelled = false;
    function poll() {
      if (cancelled) return;
      getResourcesStatus().then(s => {
        if (cancelled) return;
        if (s.guides_loaded) {
          getGuides()
            .then(r => {
              if (cancelled) return;
              setGuides(Array.isArray(r?.guides) ? r.guides : []);
              setGuidesLoaded(true);
            })
            .catch(() => {});
          return;
        }
        if (s.error) return;
        setTimeout(poll, 1000);
      }).catch(() => { if (!cancelled) setTimeout(poll, 1000); });
    }
    poll();
    return () => { cancelled = true; };
  }, [loaded, guidesLoaded]);

  useEffect(() => { setExpanded(null); }, [query, activeCat, level]);

  // Cycle: null → watchlist → watched → null.
  // Uses functional setState so rapid clicks never read stale closure state.
  function handleCycle(ytId, e) {
    e.stopPropagation();
    setWatchState(prev => {
      const inWL = prev.watchlist.has(ytId);
      const inW  = prev.watched.has(ytId);
      const nextWL = new Set(prev.watchlist);
      const nextW  = new Set(prev.watched);

      if (!inWL && !inW) {
        nextWL.add(ytId);
      } else if (inWL) {
        nextWL.delete(ytId);
        nextW.add(ytId);
      } else {
        nextW.delete(ytId);
      }

      // Single atomic write — both keys updated together.
      saveConfigFields({ guide_watchlist: [...nextWL], guide_watched: [...nextW] }).catch(() => {});

      return { watchlist: nextWL, watched: nextW };
    });
  }

  const levelOptions = [...new Set(
    guides.filter(g => g.category === "route" && g.level).map(g => g.level)
  )].sort();

  const filtered = guides.filter(g => {
    if (g.category !== activeCat) return false;
    if (g.category === "route" && level && g.level !== level) return false;
    const ytId = extractYouTubeId(g.url);
    if (hideWatched && ytId && watched.has(ytId)) return false;
    if (watchlistOnly && !(ytId && watchlist.has(ytId))) return false;
    const q = query.toLowerCase();
    if (!q) return true;
    return `${g.title} ${g.author} ${g.level || ""}`.toLowerCase().includes(q);
  });

  const fetchFailed = loaded && guidesLoaded && guides.length === 0;

  return (
    <>
      <PageHead crumb="Resources" title="COMMUNITY" accentWord="GUIDES" />
      <div style={{ borderBottom: "1px solid var(--border)", display: "flex", gap: 0, padding: "0 16px" }}>
        {ALL_CATS.map(cat => {
          const isActive = activeCat === cat;
          return (
            <div key={cat}
              onClick={() => setActiveCat(cat)}
              style={{
                padding: "10px 14px",
                cursor: "pointer",
                fontSize: 12,
                fontWeight: isActive ? 600 : 500,
                color: isActive ? "var(--accent)" : "var(--text-2)",
                borderBottom: `2px solid ${isActive ? "var(--accent)" : "transparent"}`,
                marginBottom: -1,
                userSelect: "none",
              }}>
              {CAT_LABELS[cat]}
            </div>
          );
        })}
      </div>
      <div style={{ padding: "10px 16px", borderBottom: "1px solid var(--border)", display: "flex", flexDirection: "column", gap: 8 }}>
        <input
          className="input"
          placeholder={`Search ${CAT_LABELS[activeCat].toLowerCase()} by title, author${activeCat === "route" ? ", or level" : ""}`}
          value={query}
          onChange={e => setQuery(e.target.value)}
          style={{ width: "100%", boxSizing: "border-box" }}
        />
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap", alignItems: "center" }}>
          {activeCat === "route" && levelOptions.length > 0 && (
            <select className="input" value={level} onChange={e => setLevel(e.target.value)}>
              <option value="">All levels</option>
              {levelOptions.map(l => <option key={l} value={l}>{l}</option>)}
            </select>
          )}
          <span
            className={"seg-btn " + (hideWatched ? "on" : "")}
            onClick={() => setHideWatched(v => {
              saveConfigFields({ guide_hide_watched: !v }).catch(() => {});
              return !v;
            })}
            style={{ cursor: "pointer" }}>
            Hide watched
          </span>
          <span
            className={"seg-btn " + (watchlistOnly ? "on" : "")}
            onClick={() => setWatchlistOnly(v => {
              saveConfigFields({ guide_watchlist_only: !v }).catch(() => {});
              return !v;
            })}
            style={{ cursor: "pointer" }}>
            Watchlist only
          </span>
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
              const ytId = extractYouTubeId(g.url);
              const watchState = ytId
                ? (watchlist.has(ytId) ? "watchlist" : watched.has(ytId) ? "watched" : null)
                : null;
              return (
                <li key={i} style={{
                  border: `1px solid ${isOpen ? "var(--accent)" : "var(--border)"}`,
                  borderRadius: 3,
                  overflow: "hidden",
                  transition: "border-color 0.1s",
                }}>
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
                    <span style={{
                      fontSize: 9, color: isOpen ? "var(--accent)" : "var(--text-3)",
                      transition: "transform 0.15s, color 0.1s",
                      display: "inline-block",
                      transform: isOpen ? "rotate(90deg)" : "rotate(0deg)",
                      flexShrink: 0,
                    }}>▶</span>

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

                    {ytId && (
                      <WatchCycleBtn
                        state={watchState}
                        onClick={e => handleCycle(ytId, e)}
                      />
                    )}
                  </div>

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
