import React, { useState } from "react";
import { PageHead, Btn } from "../shared.jsx";
import { findSteamDll, initSteam, saveConfigFields } from "../api.js";

export default function Welcome({ onDismiss, onSteamConnected }) {
  const [dontShow, setDontShow]   = useState(false);
  const [finding, setFinding]     = useState(false);
  const [findError, setFindError] = useState("");

  async function handleFindAndConnect() {
    setFindError("");
    setFinding(true);
    try {
      const r = await findSteamDll();
      if (r.found && r.path) {
        const sr = await initSteam(r.path);
        if (sr.ok) {
          onSteamConnected && onSteamConnected({ ready: true, playerName: sr.player_name, steamId: sr.steam_id });
          const fields = { dll_path: r.path };
          if (dontShow) fields.welcome_seen = true;
          await saveConfigFields(fields);
          onDismiss(null);
          return;
        } else {
          setFindError(sr.message || "Steam connection failed. Check that Steam is running.");
        }
      } else {
        setFindError("Couldn't locate steam_api64.dll automatically. Use Browse in Settings to find it manually.");
      }
    } catch (e) {
      setFindError("Unexpected error. Check Settings to connect manually.");
    } finally {
      setFinding(false);
    }
  }

  async function handleLater() {
    if (dontShow) await saveConfigFields({ welcome_seen: true });
    onDismiss("settings");
  }

  return (
    <>
      <PageHead crumb="Getting Started" title="GETTING" accentWord="STARTED" />
      <div className="body">
        <div className="panel-left">
          <div className="form">
            <p style={{ fontSize: 13, lineHeight: 1.6, marginBottom: 16 }}>
              <strong>Neon White Tools</strong> is a desktop companion for Neon White speedrunners.
              Use bulk leaderboard search tools, search for optimal seeds, browse and download ghosts, and watch
              world record VODs — all without leaving the app.
            </p>

            <div style={{ marginBottom: 16 }}>
              {[
                ["Leaderboard Tools", "Global export, level search, player lookup, and side-by-side comparison."],
                ["Seed Tools",        "Find seeds matching your desired starting levels; parse and standardize splits."],
                ["Resources",         "Ghost replays, route videos, world record VODs, and community guides."],
                ["Compare Players",   "Run two Steam IDs head-to-head across any level, chapter, or the whole game."],
              ].map(([title, desc]) => (
                <div key={title} style={{ display: "flex", gap: 10, marginBottom: 8, alignItems: "flex-start" }}>
                  <span style={{ color: "var(--accent)", fontWeight: 700, fontSize: 11, minWidth: 8, marginTop: 2 }}>▸</span>
                  <span style={{ fontSize: 12 }}>
                    <strong>{title}</strong> — <span className="muted">{desc}</span>
                  </span>
                </div>
              ))}
            </div>

            {findError && (
              <div style={{ fontSize: 11, color: "var(--bad, #f87171)", marginBottom: 12 }}>{findError}</div>
            )}

            <Btn kind="primary" size="lg" onClick={handleFindAndConnect} disabled={finding}
                 title="Checks your Steam install path to locate the Neon White folder. No data is collected or sent.">
              {finding ? "Searching…" : "Find Steam DLL & Connect"}
            </Btn>

            <div style={{ marginTop: 10 }}>
              <button
                onClick={handleLater}
                style={{ background: "none", border: "none", color: "var(--muted)", fontSize: 12,
                         cursor: "pointer", padding: 0, textDecoration: "underline" }}>
                I'll set it up later
              </button>
            </div>

            <div style={{ marginTop: 20, display: "flex", alignItems: "center", gap: 8 }}>
              <input
                type="checkbox"
                id="dont-show"
                checked={dontShow}
                onChange={e => setDontShow(e.target.checked)}
                style={{ cursor: "pointer" }}
              />
              <label htmlFor="dont-show" style={{ fontSize: 11, color: "var(--muted)", cursor: "pointer" }}>
                Don't show this page again
              </label>
            </div>
          </div>
        </div>
        <div className="panel-right" style={{ padding: 24 }}>
          <div className="muted" style={{ fontSize: 12 }}>
            Steam must be running and logged in. The DLL (<code>steam_api64.dll</code>) ships
            with Neon White — it's in your game's install folder.
          </div>
          <div className="muted" style={{ fontSize: 12, marginTop: 16 }}>
            You can always connect manually from Settings later.
          </div>
        </div>
      </div>
    </>
  );
}
