import React, { useState, useEffect } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";

import { Titlebar, Sidebar } from "./shared.jsx";
import { getSteamStatus, getConfig, applyAccent, saveConfigFields } from "./api.js";
import Welcome       from "./pages/Welcome.jsx";
import SeedParser    from "./pages/SeedParser.jsx";
import SplitsUpdater from "./pages/SplitsUpdater.jsx";
import Standardize   from "./pages/Standardize.jsx";
import SeedFinder    from "./pages/SeedFinder.jsx";
import RunTimer      from "./pages/RunTimer.jsx";
import GlobalExport  from "./pages/GlobalExport.jsx";
import LevelSearch   from "./pages/LevelSearch.jsx";
import PlayerLookup   from "./pages/PlayerLookup.jsx";
import ComparePlayers from "./pages/ComparePlayers.jsx";
import Ghosts           from "./pages/Ghosts.jsx";
import RouteVideos      from "./pages/RouteVideos.jsx";
import WorldRecordVods  from "./pages/WorldRecordVods.jsx";
import Guides           from "./pages/Guides.jsx";
import HelpfulLinks     from "./pages/HelpfulLinks.jsx";
import Settings      from "./pages/Settings.jsx";

const PAGE_TITLES = {
  welcome:     "Getting Started",
  parse:       "Seed Parser",
  splits:      "Splits Updater",
  std:         "Standardize Splits",
  find:        "Seed Finder",
  timer:       "Run Timer",
  global:      "Global Export",
  levelsearch: "Level Search",
  lookup:      "Player Lookup",
  compare:     "Compare Players",
  ghosts:      "Ghosts",
  videos:      "Route Videos",
  wrs:         "World Record VODs",
  guides:      "Guides",
  links:       "Helpful Links",
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
  { key: "global",      Component: GlobalExport   },
  { key: "levelsearch", Component: LevelSearch    },
  { key: "lookup",      Component: PlayerLookup   },
  { key: "compare",     Component: ComparePlayers },
];
const RES_PAGES = [
  { key: "ghosts",  Component: Ghosts          },
  { key: "videos",  Component: RouteVideos     },
  { key: "wrs",     Component: WorldRecordVods },
  { key: "guides",  Component: Guides          },
  { key: "links",   Component: HelpfulLinks    },
];
const WIRED_PAGES = [...RUSH_PAGES, ...LB_PAGES, ...RES_PAGES];
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

const VALID_LAST_TABS = new Set([
  "parse", "splits", "std", "find", "timer",
  "global", "levelsearch", "lookup", "compare",
  "ghosts", "videos", "wrs", "guides", "links",
]);

function App() {
  const [page, setPage]               = useState("parse");
  const [showWelcome, setShowWelcome] = useState(false);
  const [showMedals, setShowMedals]   = useState(true);
  const [steamStatus, setSteamStatus] = useState({ ready: false, playerName: "", steamId: 0 });
  const [outputFolder, setOutputFolder] = useState("");

  useEffect(() => {
    Promise.all([
      getSteamStatus().catch(() => null),
      getConfig().catch(() => null),
    ]).then(([s, cfg]) => {
      if (cfg) {
        setOutputFolder(cfg.output_folder || "");
        applyAccent(cfg.accent_color || "#00e09a");
      }
      if (s && s.ready) {
        setSteamStatus({ ready: true, playerName: s.player_name, steamId: s.steam_id });
      }

      if (!cfg || !cfg.welcome_seen) {
        setShowWelcome(true);
        setPage("welcome");
        return;
      }

      // Welcome already seen — smart routing
      const hasDll = cfg && cfg.dll_path;
      if (!hasDll || !(s && s.ready)) {
        setPage("settings");
        return;
      }

      const lastTab = cfg && cfg.last_tab;
      setPage(VALID_LAST_TABS.has(lastTab) ? lastTab : "lookup");
    });
  }, []);

  function handleNav(key) {
    if (key !== "welcome") setShowWelcome(false);
    setPage(key);
    if (key !== "welcome" && key !== "settings") {
      saveConfigFields({ last_tab: key }).catch(() => {});
    }
  }

  function handleWelcomeDismiss(target) {
    setShowWelcome(false);
    // null target = stay on a neutral landing panel (post-connect)
    // "settings" = go to settings (set it up later)
    setPage(target || "welcome");
    if (target && target !== "settings") {
      saveConfigFields({ last_tab: target }).catch(() => {});
    }
  }

  return (
    <div className="hifi dark"
         style={{ width: "100vw", height: "100vh", display: "flex", flexDirection: "column", overflow: "hidden" }}>
      <Titlebar pageTitle={PAGE_TITLES[page] || page} />
      <div style={{ display: "flex", flex: 1, minHeight: 0 }}>
        <Sidebar active={page} onNav={handleNav}
                 steamReady={steamStatus.ready} playerName={steamStatus.playerName} />
        <div className="main" style={{ flex: 1, minWidth: 0, overflow: "hidden", position: "relative" }}>
          {/* Welcome page */}
          {showWelcome && page === "welcome" && (
            <div style={{ display: "flex", flexDirection: "column", height: "100%", overflow: "hidden" }}>
              <Welcome onDismiss={handleWelcomeDismiss} onSteamConnected={setSteamStatus} />
            </div>
          )}
          {/* Wired pages: always mounted, hidden when inactive — preserves form state across tab switches */}
          {WIRED_PAGES.map(({ key, Component }) => (
            <div key={key} style={{
              display:       !showWelcome && key === page ? "flex" : "none",
              flexDirection: "column",
              height:        "100%",
              overflow:      "hidden",
            }}>
              <Component showMedals={showMedals} setShowMedals={setShowMedals}
                         outputFolder={outputFolder} visible={!showWelcome && key === page} />
            </div>
          ))}
          {/* Settings — mounted separately so it can update steamStatus and outputFolder */}
          <div style={{
            display: !showWelcome && page === "settings" ? "flex" : "none",
            flexDirection: "column", height: "100%", overflow: "hidden",
          }}>
            <Settings onSteamConnected={setSteamStatus} onFolderChange={setOutputFolder} />
          </div>
          {/* Post-welcome landing panel */}
          {!showWelcome && page === "welcome" && (
            <div style={{ display: "flex", alignItems: "center", justifyContent: "center",
                          height: "100%", flexDirection: "column", gap: 12 }}>
              <span style={{ fontSize: 32, color: "var(--accent)", fontFamily: "var(--display-font)" }}>
                WELCOME
              </span>
              <span className="muted" style={{ fontSize: 12 }}>
                Continue by clicking any of the tabs on the left.
              </span>
            </div>
          )}
          {/* Placeholder for pages not yet implemented */}
          {!showWelcome && !WIRED_KEYS.has(page) && page !== "settings" && page !== "welcome" && (
            <Placeholder pageName={PAGE_TITLES[page] || page} />
          )}
        </div>
      </div>
    </div>
  );
}

createRoot(document.getElementById("root")).render(<App />);
