import React, { useState, useEffect } from "react";
import { PageHead, Field, Seg, Btn } from "../shared.jsx";
import { getGuides, openExternalUrl, getConfig, saveConfigFields, getResourcesStatus, getLevels } from "../api.js";

const CAT_OPTIONS = ["Route Guides", "Technical Guides", "Medal Playlists"];
const CAT_BY_LABEL = { "Route Guides": "route", "Technical Guides": "technical", "Medal Playlists": "playlist" };
const TIER_COLORS = { Emerald: "#3ddc84", Amethyst: "#c77dff", Sapphire: "#6ab0ff" };

function extractYouTubeId(url) {
  const m = (url || "").match(/(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/)([A-Za-z0-9_-]{11})/);
  return m ? m[1] : null;
}

function WatchCycleBtn({ state, onClick }) {
  const cfg = state === "watchlist"
    ? { glyph: "★", color: "var(--accent)", title: "In watchlist — click to mark watched" }
    : state === "watched"
    ? { glyph: "✓", color: "#3ddc84",      title: "Watched — click to clear" }
    : { glyph: "☆", color: "var(--text-2)", title: "Add to watchlist" };
  return (
    <button type="button" className="watch-btn" title={cfg.title} onClick={onClick}
            aria-label={cfg.title}>
      <span key={state || "empty"} className="glyph" style={{ color: cfg.color }}>{cfg.glyph}</span>
    </button>
  );
}

export default function Guides() {
  const [guides, setGuides]        = useState([]);
  const [loaded, setLoaded]        = useState(false);
  const [query, setQuery]          = useState("");
  const [activeCatLabel, setActiveCatLabel] = useState("Route Guides");
  const [level, setLevel]          = useState("");
  const [selectedIdx, setSelectedIdx] = useState(0);
  const [videoError, setVideoError]   = useState(false);

  const [watchState, setWatchState] = useState({ watchlist: new Set(), watched: new Set() });
  const { watchlist, watched } = watchState;
  const [guidesLoaded, setGuidesLoaded] = useState(false);

  const [hideWatched, setHideWatched]     = useState(false);
  const [watchlistOnly, setWatchlistOnly] = useState(false);
  // display name -> canonical catalog index, so the Level dropdown matches the
  // game order used by every other tab (route guides' g.level is a rush_data
  // LEVELS display name — see resources.py).
  const [levelOrder, setLevelOrder] = useState(null);

  const activeCat = CAT_BY_LABEL[activeCatLabel];

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
    getLevels()
      .then(ls => {
        if (!Array.isArray(ls)) return;
        setLevelOrder(new Map(ls.map((l, i) => [l.display, i])));
      })
      .catch(() => {});
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
        if (s.errors?.guides) return;
        setTimeout(poll, 1000);
      }).catch(() => { if (!cancelled) setTimeout(poll, 1000); });
    }
    poll();
    return () => { cancelled = true; };
  }, [loaded, guidesLoaded]);

  useEffect(() => { setSelectedIdx(0); }, [query, activeCatLabel, level, hideWatched, watchlistOnly]);
  useEffect(() => { setVideoError(false); }, [selectedIdx, activeCatLabel, level]);

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

      saveConfigFields({ guide_watchlist: [...nextWL], guide_watched: [...nextW] }).catch(() => {});
      return { watchlist: nextWL, watched: nextW };
    });
  }

  function handleOpen(url) { openExternalUrl(url).catch(() => {}); }

  const levelOptions = [...new Set(
    guides.filter(g => g.category === "route" && g.level).map(g => g.level)
  )].sort((a, b) => {
    const ia = levelOrder?.get(a), ib = levelOrder?.get(b);
    if (ia != null && ib != null) return ia - ib;   // both known → game order
    if (ia != null) return -1;                       // known levels before unknown
    if (ib != null) return 1;
    return a.localeCompare(b);                        // both unknown → alphabetical
  });

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
  const selected = filtered[selectedIdx];
  const videoId  = selected ? extractYouTubeId(selected.url) : null;

  const searchPlaceholder = activeCat === "route"
    ? "Search by title, author, or level"
    : "Search by title or author";

  return (
    <>
      <PageHead crumb="Resources" title="COMMUNITY" accentWord="GUIDES" />
      <div className="body">
        <div className="panel-left">
          <div className="form">
            <Field label="Type">
              <Seg options={CAT_OPTIONS} value={activeCatLabel} onChange={setActiveCatLabel} />
            </Field>

            <Field label="Search">
              <input
                className="input"
                placeholder={searchPlaceholder}
                value={query}
                onChange={e => setQuery(e.target.value)}
                style={{ width: "100%", boxSizing: "border-box" }}
              />
            </Field>

            <Field label="Watchlist">
              <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
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
            </Field>

            {activeCat === "route" && levelOptions.length > 0 && (
              <Field label="Level">
                <select className="input" value={level} onChange={e => setLevel(e.target.value)}>
                  <option value="">All levels</option>
                  {levelOptions.map(l => <option key={l} value={l}>{l}</option>)}
                </select>
              </Field>
            )}

            {filtered.length > 0 && (
              <Field label={`Guides (${filtered.length})`}>
                <div style={{
                  maxHeight: 320,
                  overflowY: "auto",
                  border: "1px solid var(--border)",
                  borderRadius: 4,
                }}>
                  {filtered.map((g, i) => {
                    const isActive = i === selectedIdx;
                    const ytId = extractYouTubeId(g.url);
                    const wState = ytId
                      ? (watchlist.has(ytId) ? "watchlist" : watched.has(ytId) ? "watched" : null)
                      : null;
                    const tierName = g.category === "route" && g.tier ? g.tier.replace(/ \d+$/, "") : null;
                    const tc = tierName ? TIER_COLORS[tierName] : null;
                    const levelFiltered = g.category === "route" && level;
                    const primaryText = g.category === "route"
                      ? (levelFiltered ? (g.author || "(unknown)") : (g.level || g.title || "(untitled)"))
                      : (g.title || "(untitled)");

                    return (
                      <div
                        key={i}
                        onClick={() => setSelectedIdx(i)}
                        style={{
                          padding: "6px 8px",
                          fontSize: 11,
                          borderBottom: i < filtered.length - 1 ? "1px solid var(--border)" : "none",
                          cursor: "pointer",
                          background: isActive ? "var(--bg-2)" : "transparent",
                          display: "flex",
                          alignItems: "center",
                          gap: 6,
                        }}
                      >
                        <div style={{ flex: 1, minWidth: 0 }}>
                          <div style={{
                            color: isActive ? "var(--accent)" : "var(--text-1)",
                            fontWeight: isActive ? 600 : 500,
                            whiteSpace: "nowrap",
                            overflow: "hidden",
                            textOverflow: "ellipsis",
                            display: "flex",
                            alignItems: "center",
                            gap: 6,
                          }}>
                            <span style={{ overflow: "hidden", textOverflow: "ellipsis" }}>
                              {isActive ? "▶ " : ""}{primaryText}
                            </span>
                            {levelFiltered && tierName && (
                              <span style={{
                                fontSize: 9, fontWeight: 700, letterSpacing: 0.5,
                                padding: "1px 5px", borderRadius: 1,
                                background: tc ? tc + "22" : "var(--surface-2)",
                                color: tc || "var(--text-2)",
                                border: `1px solid ${tc ? tc + "55" : "transparent"}`,
                                flexShrink: 0,
                              }}>
                                {tierName}
                              </span>
                            )}
                          </div>
                          {!levelFiltered && (
                            <div style={{ display: "flex", gap: 4, alignItems: "center", marginTop: 2, flexWrap: "wrap" }}>
                              {g.author && (
                                <span style={{
                                  fontSize: 9, padding: "1px 5px",
                                  background: "var(--surface-2)", borderRadius: 2,
                                  color: "var(--text-2)",
                                }}>
                                  {g.author}
                                </span>
                              )}
                              {tierName && (
                                <span style={{
                                  fontSize: 9, fontWeight: 700, letterSpacing: 0.5,
                                  padding: "1px 5px", borderRadius: 1,
                                  background: tc ? tc + "22" : "var(--surface-2)",
                                  color: tc || "var(--text-2)",
                                  border: `1px solid ${tc ? tc + "55" : "transparent"}`,
                                }}>
                                  {tierName}
                                </span>
                              )}
                            </div>
                          )}
                        </div>
                        {ytId && (
                          <WatchCycleBtn state={wState} onClick={e => handleCycle(ytId, e)} />
                        )}
                      </div>
                    );
                  })}
                </div>
                {selected && selected.url && (
                  <div style={{ marginTop: 6 }}>
                    <Btn kind="ghost" size="sm" onClick={() => handleOpen(selected.url)}>
                      Open in YouTube
                    </Btn>
                  </div>
                )}
              </Field>
            )}
          </div>
        </div>

        <div className="panel-right" style={{ display: "flex", flexDirection: "column", overflow: "hidden" }}>
          {!loaded ? (
            <div className="muted" style={{ padding: 32, fontSize: 12, textAlign: "center" }}>Loading guides…</div>
          ) : fetchFailed ? (
            <div className="muted" style={{ padding: 32, fontSize: 12, textAlign: "center" }}>
              Couldn't load the guide sheet. Check your connection and restart the app.
            </div>
          ) : filtered.length === 0 ? (
            <div className="muted" style={{ padding: 32, fontSize: 12, textAlign: "center" }}>
              No guides match these filters.
            </div>
          ) : videoId ? (
            <div style={{ position: "relative", width: "100%", paddingTop: "56.25%", background: "#000" }}>
              {videoError ? (
                <div style={{
                  position: "absolute", top: 0, left: 0, width: "100%", height: "100%",
                  display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center",
                  gap: 12, color: "var(--muted)", fontSize: 12,
                }}>
                  <span>Could not load video in app.</span>
                  <Btn kind="ghost" size="sm" onClick={() => handleOpen(selected.url)}>
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
                  title={selected ? selected.title : "guide video"}
                />
              )}
            </div>
          ) : selected ? (
            <div className="muted" style={{ padding: 32, fontSize: 12, textAlign: "center", display: "flex", flexDirection: "column", alignItems: "center", gap: 12 }}>
              <span>No embeddable video for this guide.</span>
              {selected.url && (
                <Btn kind="ghost" size="sm" onClick={() => handleOpen(selected.url)}>Open link</Btn>
              )}
            </div>
          ) : (
            <div className="muted" style={{ padding: 32, fontSize: 12, textAlign: "center" }}>
              Select a guide to watch.
            </div>
          )}
        </div>
      </div>
    </>
  );
}
