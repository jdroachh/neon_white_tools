import React, { useState, useEffect } from "react";
import { PageHead, Field, Btn, ErrorBanner } from "../shared.jsx";
import { getConfig, saveConfigField, initSteam, pickDllFile } from "../api.js";

export default function Settings({ onSteamConnected }) {
  const [dllPath, setDllPath]     = useState("");
  const [status, setStatus]       = useState("");
  const [error, setError]         = useState("");
  const [connecting, setConnecting] = useState(false);

  useEffect(() => {
    getConfig().then(cfg => setDllPath(cfg.dll_path || ""));
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

  async function handleBrowse() {
    const r = await pickDllFile();
    if (r.ok && r.path) {
      setDllPath(r.path);
      await saveConfigField("dll_path", r.path);
    }
  }

  async function handleDllBlur() {
    if (dllPath.trim()) await saveConfigField("dll_path", dllPath.trim());
  }

  return (
    <>
      <PageHead crumb="Settings" title="SETTINGS" />
      <div className="body">
        <div className="panel-left">
          <div className="form">
            <Field label="steam_api64.dll path"
                   hint="Path to steam_api64.dll from your Neon White install folder.">
              <div style={{ display: "flex", gap: 8 }}>
                <input className="input" style={{ flex: 1 }}
                       value={dllPath}
                       onChange={e => setDllPath(e.target.value)}
                       onBlur={handleDllBlur}
                       placeholder="C:\Program Files (x86)\Steam\steamapps\common\Neon White\" />
                <Btn kind="ghost" onClick={handleBrowse}>Browse</Btn>
              </div>
            </Field>
            <ErrorBanner message={error} />
            {status && (
              <div style={{ fontSize: 11, color: "var(--good, #3ddc84)" }}>{status}</div>
            )}
            <Btn kind="primary" size="lg" onClick={handleConnect} disabled={connecting}>
              {connecting ? "Connecting..." : "Connect to Steam"}
            </Btn>
            <div className="muted" style={{ fontSize: 11, lineHeight: 1.5 }}>
              Steam must be running and logged in. The DLL is bundled with Neon White — look in the
              game&apos;s install folder.
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
