import React, { useState } from "react";
import { Btn } from "../shared.jsx";

/**
 * Shared "▾ Saved" dropdown used by Player Lookup, Compare Players, and Multi-Compare.
 *
 * Props:
 *   profiles     — list of { nickname, steam_id }
 *   onSelect     — (profile) => void, called when a profile is clicked
 *   disabled     — disables the toggle button (e.g. while a search is running)
 *   size         — Btn size variant, default "sm"
 *   label        — toggle label, default "▾ Saved"
 *   align        — menu anchor: "left" | "right" (default "right")
 *   disabledIds  — Set<string> | string[] of steam_ids that should be greyed out
 *                  and unclickable with an "in roster" tag (Multi-Compare uses
 *                  this to prevent picking the same profile into two roster rows)
 */
export default function SavedProfilesDropdown({
  profiles = [],
  onSelect,
  disabled = false,
  size = "sm",
  label = "▾ Saved",
  align = "right",
  disabledIds,
}) {
  const disabledSet = disabledIds instanceof Set
    ? disabledIds
    : new Set(disabledIds || []);
  const [open, setOpen] = useState(false);

  function handlePick(profile) {
    if (disabledSet.has(profile.steam_id)) return;
    onSelect && onSelect(profile);
    setOpen(false);
  }

  return (
    <div style={{ position: "relative", display: "flex" }}>
      <Btn kind="ghost" size={size} disabled={disabled}
           onClick={() => setOpen(v => !v)}>
        {label}
      </Btn>
      {open && (
        <>
          <div style={{ position: "fixed", inset: 0, zIndex: 199 }}
               onClick={() => setOpen(false)} />
          <div style={{
            position: "absolute", top: "100%", zIndex: 200,
            ...(align === "left" ? { left: 0 } : { right: 0 }),
            background: "var(--bg-2)", border: "1px solid var(--border)",
            borderRadius: 6, minWidth: 220, boxShadow: "0 4px 16px rgba(0,0,0,0.4)",
            marginTop: 4, maxHeight: 360, overflowY: "auto",
          }}>
            {profiles.length === 0 ? (
              <div style={{ padding: "10px 12px", fontSize: 11, color: "var(--text-3)" }}>
                No saved profiles yet. Use ★ to save a Steam ID.
              </div>
            ) : profiles.map((p, i) => {
              const taken = disabledSet.has(p.steam_id);
              return (
                <button
                  key={`${p.steam_id}-${i}`}
                  type="button"
                  onClick={() => handlePick(p)}
                  disabled={taken}
                  title={taken ? "Already in roster" : undefined}
                  style={{
                    display: "block", width: "100%", textAlign: "left",
                    padding: "7px 12px", background: "none", border: "none",
                    color: taken ? "var(--text-3)" : "var(--text)",
                    cursor: taken ? "not-allowed" : "pointer",
                    fontSize: 12,
                    opacity: taken ? 0.5 : 1,
                  }}
                  onMouseEnter={e => { if (!taken) e.currentTarget.style.background = "var(--bg-3, var(--surface-2))"; }}
                  onMouseLeave={e => e.currentTarget.style.background = "none"}
                >
                  <span style={{ fontWeight: 600 }}>{p.nickname}</span>
                  {taken ? (
                    <span style={{ color: "var(--text-3)", marginLeft: 8, fontSize: 10, fontStyle: "italic" }}>
                      in roster
                    </span>
                  ) : (
                    <span style={{ color: "var(--text-3)", marginLeft: 8, fontSize: 10 }}>
                      {p.steam_id}
                    </span>
                  )}
                </button>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}
