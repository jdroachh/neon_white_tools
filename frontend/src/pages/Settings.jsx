import React, { useState, useEffect } from "react";
import { PageHead, Field, Btn, ErrorBanner } from "../shared.jsx";
import { getConfig, saveConfigField, initSteam, pickDllFile, pickFolder } from "../api.js";

export default function Settings({ onSteamConnected, onFolderChange }) {
  const [dllPath, setDllPath]         = useState("");
  const [outputFolder, setOutputFolder] = useState("");
  const [status, setStatus]           = useState("");
  const [error, setError]             = useState("");
  const [connecting, setConnecting]   = useState(false);

  useEffect(() => {
    getConfig().then(cfg => {
      setDllPath(cfg.dll_path || "");
      setOutputFolder(cfg.output_folder || "");
    });
  }, []);

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
          </div>
        </div>
        <div className="panel-right" style={{ padding: 24 }}>
          <div className="muted" style={{ fontSize: 12 }}>
            Connect to Steam to enable leaderboard lookups.
          </div>
        </div>
      </div>
    </>
  );
}
