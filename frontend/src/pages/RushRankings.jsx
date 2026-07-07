import React, { useState, useEffect, useMemo, useRef } from "react";
import { PageHead, Field, Seg, Btn, ErrorBanner } from "../shared.jsx";
import { getRushBoards, runRushSearch, findRushPlayer, stopLeaderboard,
         pickFolder, getCheaterCount, getSteamStatus } from "../api.js";
import { loadProfiles, saveProfiles, addProfile, isValidNewId } from "../lib/savedProfiles.js";
import { loadWithRetry } from "../lib/retryLevels.js";
import SavedProfilesDropdown from "../components/SavedProfilesDropdown.jsx";

const TH = { padding: "4px 8px", fontWeight: 600, fontSize: "0.91em", borderBottom: "1px solid var(--border)", textAlign: "left" };
const TD = { padding: "3px 8px", fontSize: "1em" };

export default function RushRankings({ outputFolder: defaultFolder = "" }) {
  const [boards, setBoards]       = useState([]);
  const [rushKey, setRushKey]     = useState("");
  const [difficulty, setDiff]     = useState("heaven");   // "heaven" | "hell"
  const [mode, setMode]           = useState("topn");     // "topn" | "find"

  // ── Top-N state ──
  const [count, setCount]         = useState("100");
  const [outMode, setOutMode]     = useState("display");
  const [folder, setFolder]       = useState(defaultFolder);
  const [folderTouched, setFolderTouched] = useState(false);
  const [running, setRunning]     = useState(false);
  const [status, setStatus]       = useState("");
  const [error, setError]         = useState("");
  const [rows, setRows]           = useState([]);
  const [largeText, setLargeText] = useState(false);
  const [cheaterCount, setCheaterCount] = useState(0);
  const [nameFilter, setNameFilter]     = useState("");

  // ── Find-player state ──
  const [findSid, setFindSid]       = useState("");
  const [findResult, setFindResult] = useState(null);   // null | {ok, ...}
  const [findLoading, setFindLoading] = useState(false);
  const [savedProfiles, setSavedProfiles] = useState([]);
  const [mySteamId, setMySteamId]   = useState("");

  // Session-only cache of completed Top-N fetches, keyed "{rush}:{difficulty}".
  // Lets the user flip between boards without re-querying Steam each time; dropped
  // on app close. searchMetaRef records what the in-flight search is for so the
  // `done` event writes the cache under the right key/count.
  const cacheRef = useRef({});
  const searchMetaRef = useRef({ key: "", count: "" });
  const keyFor = (rk, diff) => `${rk}:${diff}`;

  // Switching board (rush or difficulty) swaps the on-screen results for that
  // board's cached fetch, or a blank slate if it was never fetched — the table
  // header + find card are labeled from the current selection, so the old board's
  // rows can't be left behind. The typed SteamID is kept (reusable across boards);
  // the find card always clears (it's a per-board single lookup, not cached).
  function selectBoard(rk, diff) {
    const cached = cacheRef.current[keyFor(rk, diff)];
    if (cached) {
      setRows(cached.rows); setStatus(cached.status); setCount(cached.count);
    } else {
      setRows([]); setStatus("");
    }
    setError(""); setNameFilter(""); setFindResult(null);
  }

  function handleRushChange(key) {
    if (key === rushKey) return;
    setRushKey(key);
    selectBoard(key, difficulty);
  }

  function handleDiffChange(label) {
    if (running) return;           // don't wipe rows out from under a live fetch
    const next = label.toLowerCase();
    if (next === difficulty) return;
    setDiff(next);
    selectBoard(rushKey, next);
  }

  const selectedBoard = useMemo(() => boards.find(b => b.key === rushKey) || null, [boards, rushKey]);
  const diffAvailable = selectedBoard ? selectedBoard[`${difficulty}_available`] : false;
  const rushLabel = selectedBoard ? selectedBoard.label : "";

  const filteredRows = useMemo(() => {
    const q = nameFilter.trim().toLowerCase();
    if (!q) return rows;
    return rows.filter(r => r.name.toLowerCase().includes(q));
  }, [rows, nameFilter]);

  useEffect(() => { getCheaterCount().then(n => { if (n > 0) setCheaterCount(n); }); }, []);

  useEffect(() => {
    loadWithRetry(getRushBoards, {
      onData: bs => {
        setBoards(bs);
        const first = bs.find(b => b.heaven_available || b.hell_available);
        if (first) setRushKey(first.key);
      },
    });
    loadProfiles().then(setSavedProfiles);
    getSteamStatus().then(s => {
      setMySteamId(s.ready && s.steam_id ? String(s.steam_id) : "");
    }).catch(() => {});

    window._nwRushEvent = (ev) => {
      if (ev.type === "status") {
        setStatus(ev.message);
      } else if (ev.type === "row") {
        setRows(prev => [...prev, ev]);
      } else if (ev.type === "done") {
        const doneStatus = ev.csv_path ? `${ev.message} → ${ev.csv_path}` : ev.message;
        setStatus(doneStatus);
        setRunning(false);
        // Snapshot the completed fetch into the session cache for its board. Uses a
        // functional setRows so it reads the final streamed rows, not a stale closure.
        const { key, count: fetchedCount } = searchMetaRef.current;
        if (key) {
          setRows(prev => {
            cacheRef.current[key] = { rows: prev, status: doneStatus, count: fetchedCount };
            return prev;
          });
        }
        getCheaterCount().then(n => { if (n > 0) setCheaterCount(n); });
      } else if (ev.type === "error") {
        setError(ev.message);
        setRunning(false);
      }
    };
    return () => { window._nwRushEvent = null; };
  }, []);

  useEffect(() => {
    if (!folderTouched) setFolder(defaultFolder);
  }, [defaultFolder]);

  async function handlePickFolder() {
    const r = await pickFolder();
    if (r.ok && r.path) { setFolder(r.path); setFolderTouched(true); }
  }

  async function handleRun() {
    setError(""); setStatus(""); setRows([]); setNameFilter("");
    searchMetaRef.current = { key: keyFor(rushKey, difficulty), count };
    // Set running before the await so a double-click can't start two runs.
    setRunning(true);
    try {
      const r = await runRushSearch(rushKey, difficulty, count, outMode, folder);
      if (!r.ok) { setError(r.error); setRunning(false); }
    } catch (err) {
      setError("Run failed."); setRunning(false);
    }
  }

  async function handleStop() {
    await stopLeaderboard();
    setStatus("Stopping...");
  }

  function handleCopy() {
    const text = filteredRows.map(r => `${r.rank}\t${r.name}\t${r.time}`).join("\n");
    navigator.clipboard.writeText(text).catch(() => {});
  }

  // ── Find-player handlers ──
  async function handleUseMine() {
    const s = await getSteamStatus();
    if (s.ready && s.steam_id) setFindSid(String(s.steam_id));
    else setFindResult({ ok: false, error: "Steam not connected. Connect in Settings first." });
  }

  function handleLoadProfile(profile) { setFindSid(profile.steam_id); }

  async function handleQuickSave(id) {
    const nickname = window.prompt(`Save this profile\nSteam ID: ${id}\n\nEnter a nickname (1–24 chars):`);
    if (nickname === null) return;
    const result = addProfile(savedProfiles, { nickname, steam_id: id });
    if (result.error) { setFindResult({ ok: false, error: result.error }); return; }
    setSavedProfiles(result.list);
    await saveProfiles(result.list);
  }

  async function handleFind() {
    const sid = findSid.trim();
    if (!/^\d{17}$/.test(sid)) {
      setFindResult({ ok: false, error: "Steam ID must be a 17-digit number." });
      return;
    }
    setFindLoading(true); setFindResult(null);
    const r = await findRushPlayer(rushKey, difficulty, sid)
      .catch(() => ({ ok: false, error: "Lookup failed." }));
    setFindResult(r);
    setFindLoading(false);
  }

  const showFolder = outMode === "csv" || outMode === "both";
  const diffLabel = difficulty === "heaven" ? "Heaven" : "Hell";

  return (
    <>
      <PageHead crumb="Leaderboard Tools" title="RUSH" accentWord="RANKINGS"
        actions={<>
          {mode === "topn" && filteredRows.length > 0 && !running && outMode !== "csv" &&
            <Btn kind="ghost" size="sm" icn="copy" onClick={handleCopy}>Copy</Btn>}
        </>}
      />
      <div className="body">
        <div className="panel-left">
          <div className="form">
            <Field label="Rush">
              <select className="input" value={rushKey}
                      onChange={e => handleRushChange(e.target.value)} disabled={running}>
                {boards.map(b => {
                  const avail = b.heaven_available || b.hell_available;
                  return (
                    <option key={b.key} value={b.key} disabled={!avail}>
                      {b.label}{avail ? "" : " (name pending)"}
                    </option>
                  );
                })}
              </select>
            </Field>
            <Field label="Difficulty">
              <Seg options={["Heaven", "Hell"]} value={diffLabel}
                   onChange={handleDiffChange} />
            </Field>
            {!diffAvailable && rushLabel && (
              <div className="muted" style={{ fontSize: 11, color: "var(--bad)" }}>
                {rushLabel} {diffLabel} Rush board name isn't known yet — this one
                can't be searched.
              </div>
            )}
            <Field label="Mode">
              <Seg options={["Top N", "Find player"]}
                   value={mode === "topn" ? "Top N" : "Find player"}
                   onChange={v => { setMode(v === "Top N" ? "topn" : "find"); setError(""); }} />
            </Field>

            {mode === "topn" ? (
              <>
                <Field label="Entries to fetch">
                  <input className="input" value={count}
                         onChange={e => setCount(e.target.value)} disabled={running}
                         style={{ width: 100 }} />
                </Field>
                <Field label="Output">
                  <Seg options={["display", "csv", "both"]} value={outMode} onChange={setOutMode} />
                </Field>
                {showFolder && (
                  <Field label="Output folder"
                         hint={`Saved as ${(rushLabel || "Rush")}_${diffLabel}_top{count}.csv`}>
                    <div style={{ display: "flex", gap: 8 }}>
                      <input className="input" style={{ flex: 1, fontSize: 10 }} value={folder}
                             onChange={e => { setFolder(e.target.value); setFolderTouched(true); }}
                             disabled={running} placeholder="Select a folder..." />
                      <Btn kind="ghost" size="sm" onClick={handlePickFolder} disabled={running}>Browse</Btn>
                    </div>
                  </Field>
                )}
                <ErrorBanner message={error} />
                <div style={{ display: "flex", gap: 8 }}>
                  {running
                    ? <Btn kind="danger" size="lg" onClick={handleStop}>Stop</Btn>
                    : <>
                        {rows.length > 0 && (
                          <Btn kind="ghost" size="lg" icn="refresh" onClick={handleRun}
                               disabled={!diffAvailable}
                               title="Re-fetch this board fresh from Steam">Refresh</Btn>
                        )}
                        <Btn kind="primary" size="lg" icn="search" onClick={handleRun}
                             disabled={!diffAvailable}>Search</Btn>
                      </>}
                </div>
                {status && <div className="muted" style={{ fontSize: 11 }}>{status}</div>}
              </>
            ) : (
              <>
                <Field label="Find a player"
                       hint={`Look up a player's ${rushLabel || "rush"} ${diffLabel} Rush position by Steam ID.`}>
                  <div style={{ display: "flex", gap: 8 }}>
                    <input className="input" style={{ flex: 1 }} value={findSid}
                           onChange={e => setFindSid(e.target.value)}
                           placeholder="76561198..." disabled={findLoading || running} />
                    <Btn kind="ghost" size="sm" onClick={handleUseMine}
                         disabled={findLoading || running}>Mine</Btn>
                    <SavedProfilesDropdown
                      profiles={savedProfiles}
                      onSelect={handleLoadProfile}
                      disabled={findLoading || running}
                    />
                    {isValidNewId(findSid, savedProfiles) && findSid !== mySteamId && (
                      <Btn kind="ghost" size="sm" disabled={findLoading || running}
                           title="Save this ID as a profile"
                           onClick={() => handleQuickSave(findSid)}>★</Btn>
                    )}
                  </div>
                </Field>
                <Btn kind="primary" size="lg" icn="search" onClick={handleFind}
                     disabled={findLoading || running || !diffAvailable || !findSid.trim()}>
                  {findLoading ? "Looking up..." : "Find rank"}
                </Btn>
                {running && (
                  <div className="muted" style={{ fontSize: 10 }}>
                    Lookup pauses while a Top-N run is in progress.
                  </div>
                )}
                {findResult && (findResult.ok ? (
                  <div style={{
                    padding: "10px 12px", border: "1px solid var(--border)",
                    borderRadius: 4, background: "var(--surface-2)",
                  }}>
                    <div style={{ fontSize: 13, fontWeight: 600 }}>{findResult.name}</div>
                    <div style={{ fontSize: 12, marginTop: 4 }}>
                      {rushLabel} {diffLabel} Rank{" "}
                      <span style={{ color: "var(--accent)", fontWeight: 700 }}>
                        #{Number(findResult.rank).toLocaleString()}
                      </span>
                    </div>
                    <div style={{ fontSize: 12, marginTop: 2 }}>
                      Time <span style={{ fontWeight: 600 }}>{findResult.time}</span>
                    </div>
                    <div className="muted" style={{ fontSize: 10, marginTop: 2 }}>
                      of {Number(findResult.total).toLocaleString()} runners
                    </div>
                  </div>
                ) : (
                  <div className="muted" style={{ fontSize: 11, color: "var(--bad)" }}>
                    {findResult.error}
                  </div>
                ))}
              </>
            )}
          </div>
        </div>
        <div className="panel-right" style={{ overflow: "auto", display: "flex", flexDirection: "column" }}>
          {mode === "find" ? (
            <div className="muted" style={{ padding: 32, fontSize: 12, textAlign: "center" }}>
              Enter a Steam ID on the left to find a player's rank on the selected board.
            </div>
          ) : outMode === "csv" ? (
            <div className="muted" style={{ padding: 32, fontSize: 12, textAlign: "center" }}>
              {running ? "Fetching and writing CSV..." : status || "Results will be saved to CSV only."}
            </div>
          ) : rows.length > 0 ? (
            <>
              <div style={{ display: "flex", alignItems: "center", gap: 12, padding: "10px 16px 6px", flexShrink: 0 }}>
                <span style={{ fontSize: 12, fontWeight: 600 }}>
                  {rushLabel} {diffLabel}
                  {nameFilter.trim() && (
                    <span style={{ color: "var(--text-3)", fontWeight: 400 }}>
                      {" "}· {filteredRows.length.toLocaleString()} of {rows.length.toLocaleString()}
                    </span>
                  )}
                </span>
                <input
                  className="input"
                  value={nameFilter}
                  onChange={e => setNameFilter(e.target.value)}
                  placeholder="Filter by player name…"
                  style={{ width: 200, fontSize: 11 }}
                />
                <div style={{ display: "flex", alignItems: "center", gap: 12, marginLeft: "auto" }}>
                  {cheaterCount > 0 && <span style={{ fontSize: 10, color: "var(--accent)" }}>{cheaterCount} cheaters filtered</span>}
                  <Seg value={largeText ? "Large" : "Normal"} onChange={v => setLargeText(v === "Large")}
                       options={["Normal", "Large"]} />
                </div>
              </div>
              <div style={{ fontSize: largeText ? 14 : 11, overflow: "auto", flex: 1 }}>
                <table className="nwt-hover-rows" style={{ width: "100%", borderCollapse: "collapse", tableLayout: "fixed" }}>
                  <colgroup>
                    <col style={{ width: 80 }} />
                    <col />
                    <col style={{ width: 140 }} />
                  </colgroup>
                  <thead style={{ position: "sticky", top: 0, background: "var(--bg-2)" }}>
                    <tr>
                      <th style={TH}>Rank</th>
                      <th style={TH}>Player</th>
                      <th style={TH}>Time</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredRows.map(r => (
                      <tr key={r.rank} style={{ borderBottom: "1px solid var(--border)" }}>
                        <td style={TD}>{r.rank}</td>
                        <td style={TD}>{r.name}</td>
                        <td style={TD}>{r.time}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          ) : (
            <div className="muted" style={{ padding: 32, fontSize: 12, textAlign: "center" }}>
              {running ? "Fetching entries..." : "Select a rush and press Search."}
            </div>
          )}
        </div>
      </div>
    </>
  );
}
