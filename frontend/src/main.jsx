import React, { useState, useEffect } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";
import "./mc-styles.css";

import { Sidebar } from "./shared.jsx";
import { getSteamStatus, getConfig, applyAccent, saveConfigFields, initSteam, checkForUpdate, openExternalUrl } from "./api.js";
import Welcome       from "./pages/Welcome.jsx";
import SeedParser    from "./pages/SeedParser.jsx";
import SplitsUpdater from "./pages/SplitsUpdater.jsx";
import Standardize   from "./pages/Standardize.jsx";
import SeedFinder    from "./pages/SeedFinder.jsx";
import RunTimer      from "./pages/RunTimer.jsx";
import GlobalExport  from "./pages/GlobalExport.jsx";
import GlobalNeonRankings from "./pages/GlobalNeonRankings.jsx";
import LevelSearch   from "./pages/LevelSearch.jsx";
import PlayerLookup   from "./pages/PlayerLookup.jsx";
import ComparePlayers from "./pages/ComparePlayers.jsx";
import MultiCompare   from "./pages/MultiCompare.jsx";
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
  neonrankings: "Global Neon Rankings",
  levelsearch: "Level Search",
  lookup:      "Player Lookup",
  compare:     "Compare Players",
  multicompare: "Multi Compare",
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
  { key: "neonrankings", Component: GlobalNeonRankings },
  { key: "levelsearch", Component: LevelSearch    },
  { key: "lookup",      Component: PlayerLookup   },
  { key: "compare",     Component: ComparePlayers },
  { key: "multicompare", Component: MultiCompare   },
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

function UpdateBanner({ latest, onDownload, onDismiss }) {
  return (
    <div style={{
      display: "flex", alignItems: "center", gap: 12,
      padding: "6px 14px",
      background: "var(--surface-2, #1c1c1c)",
      borderBottom: "1px solid var(--accent)",
      fontSize: 11, letterSpacing: "0.04em",
      color: "var(--text)",
      flexShrink: 0,
    }}>
      <span style={{ color: "var(--accent)", fontWeight: 600 }}>▲ UPDATE AVAILABLE</span>
      <span className="muted">v{latest} is out — you're on the previous version.</span>
      <span style={{ flex: 1 }} />
      <button
        type="button"
        onClick={onDownload}
        style={{
          background: "transparent", border: "1px solid var(--accent)",
          color: "var(--accent)", padding: "3px 10px", borderRadius: 2,
          fontSize: 10, letterSpacing: "0.08em", textTransform: "uppercase",
          cursor: "pointer", fontFamily: "var(--ui-font)",
        }}>Download</button>
      <button
        type="button"
        onClick={onDismiss}
        title="Dismiss until the next release"
        style={{
          background: "transparent", border: "none",
          color: "var(--text-3)", padding: "2px 6px",
          fontSize: 14, cursor: "pointer", lineHeight: 1,
        }}>✕</button>
    </div>
  );
}

function Placeholder({ pageName }) {
  return (
    <div style={{ display: "flex", alignItems: "center", justifyContent: "center",
                  flex: 1, minHeight: 0, flexDirection: "column", gap: 12 }}>
      <span style={{ fontSize: 32, color: "var(--accent)", fontFamily: "var(--display-font)" }}>
        {pageName}
      </span>
      <span className="muted" style={{ fontSize: 12 }}>Coming in a future milestone.</span>
    </div>
  );
}

const VALID_LAST_TABS = new Set([
  "parse", "splits", "std", "find", "timer",
  "global", "neonrankings", "levelsearch", "lookup", "compare", "multicompare",
  "ghosts", "videos", "wrs", "guides", "links",
]);

function App() {
  const [page, setPage]               = useState("parse");
  const [showWelcome, setShowWelcome] = useState(false);
  const [showMedals, setShowMedals]   = useState(true);
  const [steamStatus, setSteamStatus] = useState({ ready: false, playerName: "", steamId: 0 });
  const [outputFolder, setOutputFolder] = useState("");
  const [updateInfo, setUpdateInfo]     = useState(null);  // {latest, release_url} when banner should show

  useEffect(() => {
    Promise.all([
      getSteamStatus().catch(() => null),
      getConfig().catch(() => null),
    ]).then(async ([s, cfg]) => {
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
      let ready = !!(s && s.ready);

      // Auto-connect: if a DLL is configured and Steam isn't already up,
      // try to init once. On failure, fall through to Settings for manual recovery.
      if (hasDll && !ready) {
        const r = await initSteam(cfg.dll_path).catch(() => null);
        if (r && r.ok) {
          setSteamStatus({ ready: true, playerName: r.player_name, steamId: r.steam_id });
          ready = true;
        }
      }

      if (!hasDll || !ready) {
        setPage("settings");
        return;
      }

      const lastTab = cfg && cfg.last_tab;
      setPage(VALID_LAST_TABS.has(lastTab) ? lastTab : "lookup");
    });

    // Launch-time update check. Banner appears only if the latest version
    // hasn't already been dismissed for this user.
    checkForUpdate().then(u => {
      if (!u || !u.ok || !u.update_available) return;
      getConfig().then(cfg => {
        const dismissed = (cfg && cfg.update_dismissed_version) || "";
        if (dismissed !== u.latest) {
          setUpdateInfo({ latest: u.latest, release_url: u.release_url });
        }
      }).catch(() => setUpdateInfo({ latest: u.latest, release_url: u.release_url }));
    }).catch(() => {});
  }, []);

  function handleDismissUpdate() {
    const latest = updateInfo && updateInfo.latest;
    setUpdateInfo(null);
    if (latest) saveConfigFields({ update_dismissed_version: latest }).catch(() => {});
  }
  function handleDownloadUpdate() {
    if (updateInfo && updateInfo.release_url) {
      openExternalUrl(updateInfo.release_url).catch(() => {});
    }
  }

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
      <div style={{ display: "flex", flex: 1, minHeight: 0 }}>
        <Sidebar active={page} onNav={handleNav}
                 steamReady={steamStatus.ready} playerName={steamStatus.playerName} />
        <div className="main" style={{ flex: 1, minWidth: 0, overflow: "hidden", position: "relative", display: "flex", flexDirection: "column" }}>
          {updateInfo && (
            <UpdateBanner
              latest={updateInfo.latest}
              onDownload={handleDownloadUpdate}
              onDismiss={handleDismissUpdate}
            />
          )}
          {/* Welcome page */}
          {showWelcome && page === "welcome" && (
            <div style={{ display: "flex", flexDirection: "column", flex: 1, minHeight: 0, overflow: "hidden" }}>
              <Welcome onDismiss={handleWelcomeDismiss} onSteamConnected={setSteamStatus} />
            </div>
          )}
          {/* Wired pages: always mounted, hidden when inactive — preserves form state across tab switches */}
          {WIRED_PAGES.map(({ key, Component }) => (
            <div key={key} style={{
              display:       !showWelcome && key === page ? "flex" : "none",
              flexDirection: "column",
              flex:          1,
              minHeight:     0,
              overflow:      "hidden",
            }}>
              <Component showMedals={showMedals} setShowMedals={setShowMedals}
                         outputFolder={outputFolder} visible={!showWelcome && key === page} />
            </div>
          ))}
          {/* Settings — mounted separately so it can update steamStatus and outputFolder */}
          <div style={{
            display: !showWelcome && page === "settings" ? "flex" : "none",
            flexDirection: "column", flex: 1, minHeight: 0, overflow: "hidden",
          }}>
            <Settings onSteamConnected={setSteamStatus} onFolderChange={setOutputFolder}
                      visible={!showWelcome && page === "settings"} />
          </div>
          {/* Post-welcome landing panel */}
          {!showWelcome && page === "welcome" && (
            <div style={{ display: "flex", alignItems: "center", justifyContent: "center",
                          flex: 1, minHeight: 0, flexDirection: "column", gap: 12 }}>
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
