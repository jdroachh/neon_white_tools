import React, { useState, useEffect } from "react";
import { PageHead, Btn } from "../shared.jsx";
import { getHelpfulLinks, openExternalUrl, getResourcesStatus } from "../api.js";

export default function HelpfulLinks() {
  const [links, setLinks]       = useState([]);
  const [loaded, setLoaded]     = useState(false);
  const [linksLoaded, setLinksLoaded] = useState(false);

  useEffect(() => {
    getHelpfulLinks()
      .then(r => {
        setLinks(Array.isArray(r?.links) ? r.links : []);
        setLinksLoaded(!!r?.loaded);
      })
      .catch(() => {})
      .finally(() => setLoaded(true));
  }, []);

  // Self-rearming poll until helpful_links_loaded flips, then re-fetch.
  useEffect(() => {
    if (!loaded || linksLoaded) return;
    let cancelled = false;
    function poll() {
      if (cancelled) return;
      getResourcesStatus().then(s => {
        if (cancelled) return;
        if (s.helpful_links_loaded) {
          getHelpfulLinks()
            .then(r => {
              if (cancelled) return;
              setLinks(Array.isArray(r?.links) ? r.links : []);
              setLinksLoaded(true);
            })
            .catch(() => {});
          return;
        }
        if (s.errors?.helpful_links) return;
        setTimeout(poll, 1000);
      }).catch(() => { if (!cancelled) setTimeout(poll, 1000); });
    }
    poll();
    return () => { cancelled = true; };
  }, [loaded, linksLoaded]);

  async function handleOpen(url) {
    const r = await openExternalUrl(url);
    if (!r?.ok) {
      // eslint-disable-next-line no-console
      console.warn("Failed to open URL:", url, r);
    }
  }

  return (
    <>
      <PageHead crumb="Resources › Helpful Links" title="HELPFUL LINKS" />
      <div className="body">
        <div className="panel-left" style={{ flex: 1 }}>
          {!loaded ? (
            <div className="muted" style={{ fontSize: 12, padding: 12 }}>Loading…</div>
          ) : !linksLoaded ? (
            <div className="muted" style={{ fontSize: 12, padding: 12 }}>Loading resources…</div>
          ) : links.length === 0 ? (
            <div className="muted" style={{ fontSize: 12, padding: 12 }}>
              Couldn't load helpful links. Check your connection or try restarting the app.
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
              {links.map((row, i) => (
                <div key={i} style={{
                  display: "flex", alignItems: "center", gap: 12,
                  padding: "8px 12px",
                  borderBottom: "1px solid var(--border)",
                }}>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 13, fontWeight: 500 }}>{row.label}</div>
                    <div className="muted" style={{
                      fontSize: 10, marginTop: 2,
                      whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis",
                    }}>
                      {row.url}
                    </div>
                  </div>
                  <Btn kind="ghost" size="sm" onClick={() => handleOpen(row.url)}>Open</Btn>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </>
  );
}
