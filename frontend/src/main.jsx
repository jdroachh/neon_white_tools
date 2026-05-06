import React, { useState, useEffect } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";

import { Titlebar, Sidebar } from "./shared.jsx";
import { getSteamStatus } from "./api.js";
import SeedParser    from "./pages/SeedParser.jsx";
import SplitsUpdater from "./pages/SplitsUpdater.jsx";
import Standardize   from "./pages/Standardize.jsx";
import SeedFinder    from "./pages/SeedFinder.jsx";
import RunTimer      from "./pages/RunTimer.jsx";
import GlobalExport  from "./pages/GlobalExport.jsx";
import LevelSearch   from "./pages/LevelSearch.jsx";
import PlayerLookup  from "./pages/PlayerLookup.jsx";
import Settings      from "./pages/Settings.jsx";

const PAGE_TITLES = {
  parse:       "Seed Parser",
  splits:      "Splits Updater",
  std:         "Standardize Splits",
  find:        "Seed Finder",
  timer:       "Run Timer",
  global:      "Global Export",
  levelsearch: "Level Search",
  lookup:      "Player Lookup",
  settings:    "Settings",
};

// Pages that are fully implemented — kept permanently mounted so state survives tab switches.
// steamStatus / setSteamStatus are passed as extras to pages that need them.
const RUSH_PAGES = [
  { key: "parse",  Component: SeedParser    },
  { key: "splits", Component: SplitsUpdater },
  { key: "std",    Component: Standardize   },
  { key: "find",   Component: SeedFinder    },
  { key: "timer",  Component: RunTimer      },
];
const LB_PAGES = [
  { key: "global",      Component: GlobalExport },
  { key: "levelsearch", Component: LevelSearch  },
  { key: "lookup",      Component: PlayerLookup },
];
const WIRED_PAGES = [...RUSH_PAGES, ...LB_PAGES];
const WIRED_KEYS = new Set(WIRED_PAGES.map(p => p.key));

function Placeholder({ pageName }) {
  return (
    <div style={{ display: "flex", alignItems: "center", justifyContent: "center",
                  height: "100%", flexDirection: "column", gap: 12 }}>
      <span style={{ fontSize: 32, color: "var(--accent)", fontFamily: "var(--display-font)" }}>
        {pageName}
      </span>
      <span className="muted" style={{ fontSize: 12 }}>Coming in a future milestone.</span>
    </div>
  );
}

function App() {
  const [page, setPage]               = useState("parse");
  const [showMedals, setShowMedals]   = useState(true);
  const [steamStatus, setSteamStatus] = useState({ ready: false, playerName: "", steamId: 0 });

  useEffect(() => {
    getSteamStatus().then(s => {
      if (s.ready) setSteamStatus({ ready: true, playerName: s.player_name, steamId: s.steam_id });
    }).catch(() => {});
  }, []);

  return (
    <div className="hifi dark"
         style={{ width: "100vw", height: "100vh", display: "flex", flexDirection: "column", overflow: "hidden" }}>
      <Titlebar pageTitle={PAGE_TITLES[page] || page} />
      <div style={{ display: "flex", flex: 1, minHeight: 0 }}>
        <Sidebar active={page} onNav={setPage}
                 steamReady={steamStatus.ready} playerName={steamStatus.playerName} />
        <div className="main" style={{ flex: 1, minWidth: 0, overflow: "hidden", position: "relative" }}>
          {/* Wired pages: always mounted, hidden when inactive — preserves form state across tab switches */}
          {WIRED_PAGES.map(({ key, Component }) => (
            <div key={key} style={{
              display:       key === page ? "flex" : "none",
              flexDirection: "column",
              height:        "100%",
              overflow:      "hidden",
            }}>
              <Component showMedals={showMedals} setShowMedals={setShowMedals} />
            </div>
          ))}
          {/* Settings — mounted separately so it can update steamStatus */}
          <div style={{
            display: page === "settings" ? "flex" : "none",
            flexDirection: "column", height: "100%", overflow: "hidden",
          }}>
            <Settings onSteamConnected={setSteamStatus} />
          </div>
          {/* Placeholder for pages not yet implemented */}
          {!WIRED_KEYS.has(page) && page !== "settings" && (
            <Placeholder pageName={PAGE_TITLES[page] || page} />
          )}
        </div>
      </div>
    </div>
  );
}

createRoot(document.getElementById("root")).render(<App />);
