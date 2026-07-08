import React, { useState, useEffect } from "react";
import { PageHead, Field, Btn, ErrorBanner, Seg } from "../shared.jsx";
import { getConfig, saveConfigField, initSteam, pickDllFile, pickFolder, applyAccent, openLogFolder, getAppVersion, findSteamDll, checkForUpdate, openExternalUrl, openConfigFolder, exportConfig, importConfig } from "../api.js";
import { retryUntilOk } from "../lib/retry.js";
import { loadProfiles, saveProfiles, addProfile, updateProfile, removeProfile, moveProfile, validateProfile, MAX as MAX_PROFILES } from "../lib/savedProfiles.js";
import { loadSeeds, saveSeeds, removeSeed, moveSeed, updateNickname as updateSeedNickname, MAX as MAX_SEEDS } from "../lib/savedSeeds.js";
import { loadRosters, saveRosters, removeRoster, moveRoster, updateNickname as updateRosterNickname, MAX as MAX_ROSTERS } from "../lib/savedRosters.js";

const ACCENT_PRESETS = [
  { hex: "#00e09a", label: "Mint"    },
  { hex: "#22d3ee", label: "Cyan"    },
  { hex: "#38bdf8", label: "Sky"     },
  { hex: "#a78bfa", label: "Violet"  },
  { hex: "#f472b6", label: "Magenta" },
  { hex: "#fb923c", label: "Orange"  },
  { hex: "#fbbf24", label: "Amber"   },
  { hex: "#fb7185", label: "Rose"    },
  { hex: "#ffffff", label: "White"   },
];

export default function Settings({ onSteamConnected, onFolderChange, steamReady = false, onDisconnect, visible = false }) {
  const [dllPath, setDllPath]         = useState("");
  const [outputFolder, setOutputFolder] = useState("");
  const [status, setStatus]           = useState("");
  const [error, setError]             = useState("");
  const [connecting, setConnecting]   = useState(false);
  const [disconnecting, setDisconnecting] = useState(false);
  const [accentColor, setAccentColor] = useState("#00e09a");
  const [savedProfiles, setSavedProfiles] = useState([]);
  const [profileErrors, setProfileErrors] = useState({});
  const [newNickname, setNewNickname]   = useState("");
  const [newSteamId, setNewSteamId]     = useState("");
  const [addError, setAddError]         = useState("");
  const [appVersion, setAppVersion]     = useState("");
  const [updateAvail, setUpdateAvail]   = useState(null);  // {latest, release_url} when out of date
  const [logStatus, setLogStatus]       = useState("");
  const [findingDll, setFindingDll]     = useState(false);
  const [findDllError, setFindDllError] = useState("");
  const [savedSection, setSavedSection] = useState("profiles");
  const [savedSeeds, setSavedSeeds]     = useState([]);
  const [seedErrors, setSeedErrors]     = useState({});
  const [savedRosters, setSavedRosters] = useState([]);
  const [rosterErrors, setRosterErrors] = useState({});
  const [dataStatus, setDataStatus]     = useState("");
  const [dataError, setDataError]       = useState("");

  useEffect(() => {
    getConfig().then(cfg => {
      setDllPath(cfg.dll_path || "");
      setOutputFolder(cfg.output_folder || "");
      setAccentColor(cfg.accent_color || "#00e09a");
    });
    loadProfiles().then(setSavedProfiles);
    loadSeeds().then(setSavedSeeds);
    loadRosters().then(setSavedRosters);
    // Retry past the first-boot window so the version isn't left blank (see shared.jsx).
    retryUntilOk(getAppVersion, v => !!v, { label: "getAppVersion" }).then(v => setAppVersion(v || ""));
    checkForUpdate().then(u => {
      if (u && u.ok && u.update_available) {
        setUpdateAvail({ latest: u.latest, release_url: u.release_url });
      }
    }).catch(() => {});
  }, []);

  // If the session is dropped from elsewhere (e.g. the sidebar power button),
  // clear the stale "Connected as …" line so Settings stops claiming we're up.
  useEffect(() => {
    if (!steamReady) setStatus(s => (s.startsWith("Connected") ? "" : s));
  }, [steamReady]);

  useEffect(() => {
    if (visible) {
      loadProfiles().then(setSavedProfiles);
      loadSeeds().then(setSavedSeeds);
      loadRosters().then(setSavedRosters);
    }
  }, [visible]);

  async function handleOpenLogs() {
    setLogStatus("");
    const r = await openLogFolder();
    if (!r.ok) setLogStatus(r.error || "Could not open log folder.");
  }

  async function handleOpenConfig() {
    setDataStatus(""); setDataError("");
    const r = await openConfigFolder();
    if (!r.ok) setDataError(r.error || "Could not open config folder.");
  }

  async function handleExport() {
    setDataStatus(""); setDataError("");
    const r = await exportConfig();
    if (r.cancelled) return;
    if (r.ok) setDataStatus(`Saved backup to ${r.path}`);
    else setDataError(r.error || "Export failed.");
  }

  async function handleImport() {
    setDataStatus(""); setDataError("");
    if (!window.confirm("Import will overwrite your current settings, saved profiles, rosters, and seeds with the contents of the backup file. Continue?")) return;
    const r = await importConfig();
    if (r.cancelled) return;
    if (!r.ok) { setDataError(r.error || "Import failed."); return; }
    // Reload everything the import may have changed.
    const cfg = await getConfig();
    setDllPath(cfg.dll_path || "");
    setOutputFolder(cfg.output_folder || "");
    const accent = cfg.accent_color || "#00e09a";
    setAccentColor(accent);
    applyAccent(accent);
    loadProfiles().then(setSavedProfiles);
    loadSeeds().then(setSavedSeeds);
    loadRosters().then(setSavedRosters);
    setDataStatus(`Imported ${r.count} setting${r.count === 1 ? "" : "s"} group. Reconnect to Steam if your DLL path changed.`);
  }

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

  async function handleDisconnect() {
    if (!onDisconnect) return;
    setError(""); setStatus("Disconnecting…");
    setDisconnecting(true);
    const r = await onDisconnect();
    setDisconnecting(false);
    if (r && r.ok) {
      setStatus("Disconnected.");
    } else {
      setError((r && r.error) || "Disconnect failed.");
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

  async function handleFindDll() {
    setFindDllError(""); setFindingDll(true);
    try {
      const r = await findSteamDll();
      if (r.found && r.path) {
        setDllPath(r.path);
        await saveConfigField("dll_path", r.path);
        const sr = await initSteam(r.path);
        if (sr.ok) {
          setStatus(`Connected as ${sr.player_name}`);
          setError("");
          onSteamConnected && onSteamConnected({ ready: true, playerName: sr.player_name, steamId: sr.steam_id });
        } else {
          setError(sr.message || "DLL found but Steam connection failed.");
          setStatus("");
        }
      } else {
        setFindDllError("Couldn't locate steam_api64.dll automatically. Use Browse to find it manually.");
      }
    } catch (e) {
      setFindDllError("Unexpected error during DLL search.");
    } finally {
      setFindingDll(false);
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

  async function handleProfileFieldChange(idx, field, value) {
    const p = { ...savedProfiles[idx], [field]: value };
    const err = validateProfile(p.nickname, p.steam_id);
    const errs = { ...profileErrors };
    if (err) errs[idx] = err; else delete errs[idx];
    setProfileErrors(errs);
    const next = savedProfiles.map((x, i) => i === idx ? { nickname: p.nickname, steam_id: p.steam_id } : x);
    setSavedProfiles(next);
  }

  async function handleProfileFieldBlur(idx) {
    const p = savedProfiles[idx];
    const err = validateProfile(p.nickname, p.steam_id);
    if (err) return;
    const result = updateProfile(savedProfiles, idx, p);
    if (result.error) {
      setProfileErrors(prev => ({ ...prev, [idx]: result.error }));
      return;
    }
    setSavedProfiles(result.list);
    await saveProfiles(result.list);
  }

  async function handleProfileDelete(idx) {
    const next = removeProfile(savedProfiles, idx);
    setSavedProfiles(next);
    const errs = { ...profileErrors };
    delete errs[idx];
    setProfileErrors(errs);
    await saveProfiles(next);
  }

  async function handleProfileMove(idx, dir) {
    const next = moveProfile(savedProfiles, idx, dir);
    setSavedProfiles(next);
    await saveProfiles(next);
  }

  async function handleAddProfile() {
    setAddError("");
    const result = addProfile(savedProfiles, { nickname: newNickname, steam_id: newSteamId });
    if (result.error) { setAddError(result.error); return; }
    setSavedProfiles(result.list);
    setNewNickname("");
    setNewSteamId("");
    await saveProfiles(result.list);
  }

  function handleSeedNicknameChange(idx, value) {
    const next = savedSeeds.map((s, i) => i === idx ? { ...s, nickname: value } : s);
    setSavedSeeds(next);
  }

  async function handleSeedNicknameBlur(idx) {
    const s = savedSeeds[idx];
    const result = updateSeedNickname(savedSeeds, idx, s.nickname);
    if (result.error) {
      setSeedErrors(prev => ({ ...prev, [idx]: result.error }));
      return;
    }
    setSeedErrors(prev => { const next = { ...prev }; delete next[idx]; return next; });
    setSavedSeeds(result.list);
    await saveSeeds(result.list);
  }

  async function handleSeedDelete(idx) {
    const name = savedSeeds[idx]?.nickname ?? "this seed";
    if (!window.confirm(`Delete saved seed "${name}"?`)) return;
    const next = removeSeed(savedSeeds, idx);
    setSavedSeeds(next);
    setSeedErrors(prev => { const e = { ...prev }; delete e[idx]; return e; });
    await saveSeeds(next);
  }

  function handleRosterNicknameChange(idx, value) {
    const next = savedRosters.map((r, i) => i === idx ? { ...r, nickname: value } : r);
    setSavedRosters(next);
  }

  async function handleRosterNicknameBlur(idx) {
    const r = savedRosters[idx];
    const result = updateRosterNickname(savedRosters, idx, r.nickname);
    if (result.error) {
      setRosterErrors(prev => ({ ...prev, [idx]: result.error }));
      return;
    }
    setRosterErrors(prev => { const next = { ...prev }; delete next[idx]; return next; });
    setSavedRosters(result.list);
    await saveRosters(result.list);
  }

  async function handleRosterDelete(idx) {
    const name = savedRosters[idx]?.nickname ?? "this roster";
    if (!window.confirm(`Delete saved roster "${name}"?`)) return;
    const next = removeRoster(savedRosters, idx);
    setSavedRosters(next);
    setRosterErrors(prev => { const e = { ...prev }; delete e[idx]; return e; });
    await saveRosters(next);
  }

  async function handleRosterMove(idx, dir) {
    const next = moveRoster(savedRosters, idx, dir);
    setSavedRosters(next);
    await saveRosters(next);
  }

  async function handleSeedMove(idx, dir) {
    const next = moveSeed(savedSeeds, idx, dir);
    setSavedSeeds(next);
    await saveSeeds(next);
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
                <Btn kind="ghost" onClick={handleFindDll} disabled={findingDll}
                     title="Checks your Steam install path to locate the Neon White folder. No data is collected or sent.">
                  {findingDll ? "Searching…" : "Find DLL"}
                </Btn>
              </div>
            </Field>
            {findDllError && (
              <div style={{ fontSize: 11, color: "var(--bad, #f87171)", marginBottom: 4 }}>{findDllError}</div>
            )}
            <ErrorBanner message={error} />
            {status && (
              <div style={{ fontSize: 11, color: "var(--good, #3ddc84)" }}>{status}</div>
            )}
            <div style={{ display: "flex", gap: 8 }}>
              <Btn kind="primary" size="lg" onClick={handleConnect} disabled={connecting}>
                {connecting ? "Connecting..." : "Connect to Steam"}
              </Btn>
              {steamReady && (
                <Btn kind="ghost" size="lg" onClick={handleDisconnect} disabled={disconnecting}>
                  {disconnecting ? "Disconnecting…" : "Disconnect"}
                </Btn>
              )}
            </div>
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
            <div style={{ borderTop: "1px solid var(--border)", margin: "4px 0" }} />
            <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 6 }}>
              <div style={{ fontWeight: 600, fontSize: 12 }}>Saved items</div>
              <Seg
                options={["profiles", "seeds", "rosters"]}
                value={savedSection}
                onChange={setSavedSection}
              />
            </div>

            {savedSection === "profiles" && (
              <>
                <div className="muted" style={{ fontSize: 11, marginBottom: 8 }}>
                  Nickname + Steam ID pairs used in Player Lookup and Compare Players.
                </div>
                <div style={{ maxHeight: 400, overflow: "auto", paddingRight: 4 }}>
                  {savedProfiles.map((p, i) => (
                    <div key={i} style={{ marginBottom: 8 }}>
                      <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
                        <input className="input" style={{ width: 110 }}
                          value={p.nickname}
                          onChange={e => handleProfileFieldChange(i, "nickname", e.target.value)}
                          onBlur={() => handleProfileFieldBlur(i)}
                          placeholder="Nickname" />
                        <input className="input" style={{ flex: 1, fontSize: 10 }}
                          value={p.steam_id}
                          onChange={e => handleProfileFieldChange(i, "steam_id", e.target.value)}
                          onBlur={() => handleProfileFieldBlur(i)}
                          placeholder="17-digit Steam ID" />
                        <Btn kind="ghost" size="sm" disabled={i === 0}
                             onClick={() => handleProfileMove(i, -1)}>↑</Btn>
                        <Btn kind="ghost" size="sm" disabled={i === savedProfiles.length - 1}
                             onClick={() => handleProfileMove(i, 1)}>↓</Btn>
                        <Btn kind="danger" size="sm"
                             onClick={() => handleProfileDelete(i)}>✕</Btn>
                      </div>
                      {profileErrors[i] && (
                        <div style={{ fontSize: 11, color: "var(--bad, #f87171)", marginTop: 3 }}>
                          {profileErrors[i]}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
                {savedProfiles.length < MAX_PROFILES ? (
                  <div style={{ display: "flex", gap: 6, alignItems: "center", marginTop: 4 }}>
                    <input className="input" style={{ width: 110 }}
                      value={newNickname}
                      onChange={e => { setNewNickname(e.target.value); setAddError(""); }}
                      placeholder="Nickname" />
                    <input className="input" style={{ flex: 1, fontSize: 10 }}
                      value={newSteamId}
                      onChange={e => { setNewSteamId(e.target.value); setAddError(""); }}
                      placeholder="17-digit Steam ID" />
                    <Btn kind="ghost" size="sm" onClick={handleAddProfile}>+ Add</Btn>
                  </div>
                ) : (
                  <div className="muted" style={{ fontSize: 11, marginTop: 4 }}>Limit: {MAX_PROFILES} profiles.</div>
                )}
                {addError && (
                  <div style={{ fontSize: 11, color: "var(--bad, #f87171)", marginTop: 4 }}>{addError}</div>
                )}
              </>
            )}

            {savedSection === "seeds" && (
              <>
                <div className="muted" style={{ fontSize: 11, marginBottom: 8 }}>
                  Favorited seeds from Seed Finder. New seeds are saved with the ★ button on result cards.
                </div>
                {savedSeeds.length === 0 ? (
                  <div className="muted" style={{ fontSize: 11, padding: "8px 0" }}>
                    No saved seeds yet.
                  </div>
                ) : (
                  <div style={{ maxHeight: 400, overflow: "auto", paddingRight: 4 }}>
                    {savedSeeds.map((s, i) => (
                      <div key={s.seed} style={{ marginBottom: 8 }}>
                        <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
                          <input className="input" style={{ flex: 1, minWidth: 0 }}
                            value={s.nickname}
                            onChange={e => handleSeedNicknameChange(i, e.target.value)}
                            onBlur={() => handleSeedNicknameBlur(i)}
                            placeholder="Nickname" />
                          <Btn kind="ghost" size="sm" disabled={i === 0}
                               onClick={() => handleSeedMove(i, -1)}>↑</Btn>
                          <Btn kind="ghost" size="sm" disabled={i === savedSeeds.length - 1}
                               onClick={() => handleSeedMove(i, 1)}>↓</Btn>
                          <Btn kind="danger" size="sm"
                               onClick={() => handleSeedDelete(i)}>✕</Btn>
                        </div>
                        <div className="muted data" style={{ fontSize: 10, marginTop: 2, paddingLeft: 2 }}>
                          {s.seed} · {s.rush}
                        </div>
                        {seedErrors[i] && (
                          <div style={{ fontSize: 11, color: "var(--bad, #f87171)", marginTop: 3 }}>
                            {seedErrors[i]}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
                <div className="muted" style={{ fontSize: 11, marginTop: 4 }}>
                  {savedSeeds.length} / {MAX_SEEDS} saved.
                </div>
              </>
            )}

            {savedSection === "rosters" && (
              <>
                <div className="muted" style={{ fontSize: 11, marginBottom: 8 }}>
                  Player rosters from Multi-Compare. New rosters are saved with the ★ button on the Multi-Compare page.
                </div>
                {savedRosters.length === 0 ? (
                  <div className="muted" style={{ fontSize: 11, padding: "8px 0" }}>
                    No saved rosters yet.
                  </div>
                ) : (
                  <div style={{ maxHeight: 400, overflow: "auto", paddingRight: 4 }}>
                    {savedRosters.map((r, i) => (
                      <div key={i} style={{ marginBottom: 8 }}>
                        <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
                          <input className="input" style={{ flex: 1, minWidth: 0 }}
                            value={r.nickname}
                            onChange={e => handleRosterNicknameChange(i, e.target.value)}
                            onBlur={() => handleRosterNicknameBlur(i)}
                            placeholder="Roster name" />
                          <Btn kind="ghost" size="sm" disabled={i === 0}
                               onClick={() => handleRosterMove(i, -1)}>↑</Btn>
                          <Btn kind="ghost" size="sm" disabled={i === savedRosters.length - 1}
                               onClick={() => handleRosterMove(i, 1)}>↓</Btn>
                          <Btn kind="danger" size="sm"
                               onClick={() => handleRosterDelete(i)}>✕</Btn>
                        </div>
                        <div className="muted data" style={{ fontSize: 10, marginTop: 2, paddingLeft: 2 }}>
                          {(r.members || []).length} player{(r.members || []).length === 1 ? "" : "s"}
                          {(r.members || []).length > 0 && (
                            <>
                              {" · "}
                              {(r.members || []).map(m => m.name || `(${(m.steam_id || "").slice(-4)})`).join(", ")}
                            </>
                          )}
                        </div>
                        {rosterErrors[i] && (
                          <div style={{ fontSize: 11, color: "var(--bad, #f87171)", marginTop: 3 }}>
                            {rosterErrors[i]}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
                <div className="muted" style={{ fontSize: 11, marginTop: 4 }}>
                  {savedRosters.length} / {MAX_ROSTERS} saved.
                </div>
              </>
            )}
            <div style={{ borderTop: "1px solid var(--border)", margin: "4px 0" }} />
            <div style={{ fontWeight: 600, fontSize: 12, marginBottom: 6 }}>Backup &amp; data</div>
            <div className="muted" style={{ fontSize: 11, marginBottom: 8, lineHeight: 1.5 }}>
              Your saved data lives in <code>%APPDATA%\NeonWhiteLeaderboardTool</code> and now survives app
              updates automatically. Export a backup file to move it to another PC or keep a copy; Import
              restores everything (profiles, rosters, seeds, settings) from a backup.
            </div>
            <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
              <Btn kind="ghost" onClick={handleExport}>Export data</Btn>
              <Btn kind="ghost" onClick={handleImport}>Import data</Btn>
              <Btn kind="ghost" onClick={handleOpenConfig}>Open config folder</Btn>
            </div>
            {dataStatus && (
              <div style={{ fontSize: 11, color: "var(--good, #3ddc84)", marginTop: 4, wordBreak: "break-all" }}>{dataStatus}</div>
            )}
            {dataError && (
              <div style={{ fontSize: 11, color: "var(--bad, #f87171)", marginTop: 4 }}>{dataError}</div>
            )}
            <div style={{ borderTop: "1px solid var(--border)", margin: "4px 0" }} />
            <div style={{ fontWeight: 600, fontSize: 12, marginBottom: 6 }}>Diagnostics</div>
            <div className="muted" style={{ fontSize: 11, marginBottom: 8 }}>
              Hitting a bug? Open the log folder and attach <code>app.log</code> to your report.
            </div>
            <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
              <Btn kind="ghost" onClick={handleOpenLogs}>Open log folder</Btn>
              {appVersion && (
                <span className="muted" style={{ fontSize: 11 }}>
                  Version {appVersion}
                </span>
              )}
              {updateAvail && (
                <span style={{ fontSize: 11, color: "var(--accent)" }}>
                  ▲ v{updateAvail.latest} available —{" "}
                  <a
                    href="#"
                    onClick={(e) => { e.preventDefault(); openExternalUrl(updateAvail.release_url).catch(() => {}); }}
                    style={{ color: "var(--accent)", textDecoration: "underline" }}
                  >download</a>
                </span>
              )}
            </div>
            {logStatus && (
              <div style={{ fontSize: 11, color: "var(--bad, #f87171)", marginTop: 4 }}>{logStatus}</div>
            )}
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
