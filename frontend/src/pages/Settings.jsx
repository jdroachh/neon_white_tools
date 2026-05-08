import React, { useState, useEffect } from "react";
import { PageHead, Field, Btn, ErrorBanner } from "../shared.jsx";
import { getConfig, saveConfigField, initSteam, pickDllFile, pickFolder, applyAccent } from "../api.js";

const ACCENT_PRESETS = [
  { hex: "#00e09a", label: "Mint"    },
  { hex: "#22d3ee", label: "Cyan"    },
  { hex: "#38bdf8", label: "Sky"     },
  { hex: "#a78bfa", label: "Violet"  },
  { hex: "#f472b6", label: "Magenta" },
  { hex: "#fb923c", label: "Orange"  },
  { hex: "#fbbf24", label: "Amber"   },
  { hex: "#fb7185", label: "Rose"    },
];

export default function Settings({ onSteamConnected, onFolderChange }) {
  const [dllPath, setDllPath]         = useState("");
  const [outputFolder, setOutputFolder] = useState("");
  const [status, setStatus]           = useState("");
  const [error, setError]             = useState("");
  const [connecting, setConnecting]   = useState(false);
  const [accentColor, setAccentColor] = useState("#00e09a");

  useEffect(() => {
    getConfig().then(cfg => {
      setDllPath(cfg.dll_path || "");
      setOutputFolder(cfg.output_folder || "");
      setAccentColor(cfg.accent_color || "#00e09a");
    });
  }, []);

  async function handleAccentPick(hex) {
    setAccentColor(hex);
    applyAccent(hex);
    await saveConfigField("accent_color", hex);
  }

  async function handleConnect() {
    if (!dllPath.trim()) { setError("Enter the path to steam_api64.dll."); return; }
    setError(""); setStatus("Connecting...");
    setConnecting(true);
    const r = await initSteam(dllPath.trim());
    setConnecting(false);
    if (r.ok) {
      setStatus(`Connected as ${r.player_name}`);
      onSteamConnected && onSteamConnected({ ready: true, playerName: r.player_name, steamId: r.steam_id });
    } else {
      setError(r.message || "Connection failed.");
      setStatus("");
    }
  }

  async function handleBrowseDll() {
    const r = await pickDllFile();
    if (r.ok && r.path) {
      setDllPath(r.path);
      await saveConfigField("dll_path", r.path);
    }
  }

  async function handleBrowseFolder() {
    const r = await pickFolder();
    if (r.ok && r.path) {
      setOutputFolder(r.path);
      await saveConfigField("output_folder", r.path);
      onFolderChange && onFolderChange(r.path);
    }
  }

  async function handleDllBlur() {
    if (dllPath.trim()) await saveConfigField("dll_path", dllPath.trim());
  }

  async function handleFolderBlur() {
    const val = outputFolder.trim();
    if (val) {
      await saveConfigField("output_folder", val);
      onFolderChange && onFolderChange(val);
    }
  }

  return (
    <>
      <PageHead crumb="Settings" title="SETTINGS" />
      <div className="body">
        <div className="panel-left">
          <div className="form">
            <Field label="steam_api64.dll path"
                   hint="From your Neon White install folder.">
              <div style={{ display: "flex", gap: 8 }}>
                <input className="input" style={{ flex: 1 }}
                       value={dllPath}
                       onChange={e => setDllPath(e.target.value)}
                       onBlur={handleDllBlur}
                       placeholder="C:\...\Neon White\steam_api64.dll" />
                <Btn kind="ghost" onClick={handleBrowseDll}>Browse</Btn>
              </div>
            </Field>
            <ErrorBanner message={error} />
            {status && (
              <div style={{ fontSize: 11, color: "var(--good, #3ddc84)" }}>{status}</div>
            )}
            <Btn kind="primary" size="lg" onClick={handleConnect} disabled={connecting}>
              {connecting ? "Connecting..." : "Connect to Steam"}
            </Btn>
            <div style={{ borderTop: "1px solid var(--border)", margin: "4px 0" }} />
            <Field label="Default output folder"
                   hint="Used as the default save location for CSV exports.">
              <div style={{ display: "flex", gap: 8 }}>
                <input className="input" style={{ flex: 1, fontSize: 10 }}
                       value={outputFolder}
                       onChange={e => setOutputFolder(e.target.value)}
                       onBlur={handleFolderBlur}
                       placeholder="e.g. C:\Users\you\Desktop" />
                <Btn kind="ghost" onClick={handleBrowseFolder}>Browse</Btn>
              </div>
            </Field>
            <div className="muted" style={{ fontSize: 11, lineHeight: 1.5 }}>
              Steam must be running and logged in. The DLL is bundled with Neon White.
            </div>
            <div style={{ borderTop: "1px solid var(--border)", margin: "4px 0" }} />
            <Field label="Color Picker (Restrain setting)"
                   hint="Accent color used across buttons, toggles, and highlights.">
              <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                {ACCENT_PRESETS.map(({ hex, label }) => (
                  <button
                    key={hex}
                    title={label}
                    onClick={() => handleAccentPick(hex)}
                    style={{
                      width: 28, height: 28,
                      borderRadius: 4,
                      background: hex,
                      border: accentColor === hex
                        ? "2px solid var(--text)"
                        : "2px solid transparent",
                      outline: accentColor === hex ? `2px solid ${hex}` : "none",
                      outlineOffset: 1,
                      cursor: "pointer",
                      padding: 0,
                      flexShrink: 0,
                    }}
                  />
                ))}
              </div>
            </Field>
          </div>
        </div>
        <div className="panel-right" style={{ padding: 24 }}>
          <div className="muted" style={{ fontSize: 12 }}>
            Connect to Steam to enable leaderboard lookups.
          </div>
          <div className="muted" style={{ fontSize: 12, marginTop: 16 }}>
            Changes the accent color used across buttons, toggles, and highlights. Medal colors are unchanged.
          </div>
        </div>
      </div>
    </>
  );
}
