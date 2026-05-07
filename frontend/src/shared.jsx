/**
 * shared.jsx — design system components lifted from ClaudeDesignHandoff/hifi-shared.jsx.
 * Converted from Babel-in-browser globals to ES module exports.
 * seededOrder() removed — replaced by api.parseSeed() at call sites.
 */
import React from "react";

export const RUSHES = [
  { name: "White / Mikey", count: 96 },
  { name: "Violet",        count: 8 },
  { name: "Red",           count: 8 },
  { name: "Yellow",        count: 8 },
];

/* === Icons (inline SVG, stroke-only) === */
export const Icon = ({ name, size = 14 }) => {
  const s = { width: size, height: size };
  const sp = { fill: "none", stroke: "currentColor", strokeWidth: 1.5, strokeLinecap: "round", strokeLinejoin: "round" };
  switch (name) {
    case "export":   return <svg viewBox="0 0 16 16" style={s}><g {...sp}><path d="M8 11V2"/><path d="M5 5l3-3 3 3"/><path d="M3 11v3h10v-3"/></g></svg>;
    case "search":   return <svg viewBox="0 0 16 16" style={s}><g {...sp}><circle cx="7" cy="7" r="4.5"/><path d="M10.5 10.5L14 14"/></g></svg>;
    case "user":     return <svg viewBox="0 0 16 16" style={s}><g {...sp}><circle cx="8" cy="5.5" r="2.5"/><path d="M3 13c0-2.5 2.2-4.5 5-4.5s5 2 5 4.5"/></g></svg>;
    case "seed":     return <svg viewBox="0 0 16 16" style={s}><g {...sp}><path d="M8 2v12M3 8l5-3 5 3M3 12l5-3 5 3"/></g></svg>;
    case "parse":    return <svg viewBox="0 0 16 16" style={s}><g {...sp}><path d="M5 3L2 8l3 5M11 3l3 5-3 5M9 3l-2 10"/></g></svg>;
    case "splits":   return <svg viewBox="0 0 16 16" style={s}><g {...sp}><path d="M2 4h12M2 8h7M2 12h12M11 7l3 1-3 1"/></g></svg>;
    case "standard": return <svg viewBox="0 0 16 16" style={s}><g {...sp}><path d="M2 4h12M2 8h12M2 12h12M5 2l-3 2 3 2M11 6l3 2-3 2"/></g></svg>;
    case "timer":    return <svg viewBox="0 0 16 16" style={s}><g {...sp}><circle cx="8" cy="9" r="5"/><path d="M8 9V6M6 2h4M8 4v0"/></g></svg>;
    case "gear":     return <svg viewBox="0 0 16 16" style={s}><g {...sp}><circle cx="8" cy="8" r="2.5"/><path d="M8 1.5v2M8 12.5v2M14.5 8h-2M3.5 8h-2M12.6 3.4l-1.4 1.4M4.8 11.2l-1.4 1.4M12.6 12.6l-1.4-1.4M4.8 4.8L3.4 3.4"/></g></svg>;
    case "copy":     return <svg viewBox="0 0 16 16" style={s}><g {...sp}><rect x="5" y="5" width="9" height="9"/><path d="M3 11V3a1 1 0 011-1h7"/></g></svg>;
    case "play":     return <svg viewBox="0 0 16 16" style={s}><path d="M4 3l9 5-9 5z" fill="currentColor"/></svg>;
    case "caret":    return <svg viewBox="0 0 16 16" style={s}><path d="M5 6l3 3 3-3" {...sp}/></svg>;
    case "chev":     return <svg viewBox="0 0 16 16" style={s}><path d="M6 4l4 4-4 4" {...sp}/></svg>;
    case "min":      return <svg viewBox="0 0 12 12" style={s}><path d="M2 6h8" stroke="currentColor" strokeWidth="1"/></svg>;
    case "max":      return <svg viewBox="0 0 12 12" style={s}><rect x="2" y="2" width="8" height="8" fill="none" stroke="currentColor" strokeWidth="1"/></svg>;
    case "close":    return <svg viewBox="0 0 12 12" style={s}><path d="M2 2l8 8M10 2l-8 8" stroke="currentColor" strokeWidth="1"/></svg>;
    case "sw":       return <svg viewBox="0 0 16 16" style={s}><g {...sp}><path d="M2 8l3-3M2 8l3 3M14 8l-3-3M14 8l-3 3"/></g></svg>;
    case "check":    return <svg viewBox="0 0 16 16" style={s}><path d="M3 8l3 3 7-7" {...sp}/></svg>;
    case "warn":     return <svg viewBox="0 0 16 16" style={s}><g {...sp}><path d="M8 2L1.5 14h13L8 2z"/><path d="M8 6v4M8 12v0"/></g></svg>;
    case "ghost":    return <svg viewBox="0 0 16 16" style={s}><g {...sp}><path d="M3 13V7a5 5 0 0110 0v6l-2-1.5L9 13l-2-1.5L5 13l-2-1.5z"/><circle cx="6" cy="7" r="0.7" fill="currentColor"/><circle cx="10" cy="7" r="0.7" fill="currentColor"/></g></svg>;
    case "video":    return <svg viewBox="0 0 16 16" style={s}><g {...sp}><rect x="2" y="4" width="9" height="8" rx="1"/><path d="M11 7l3-2v6l-3-2z"/></g></svg>;
    default: return null;
  }
};

/* === Title bar (Windows-style, non-functional chrome) === */
export const Titlebar = ({ pageTitle = "Tools" }) => (
  <div className="titlebar">
    <span className="nw-mark"><span>NEON</span><span className="accent">WHITE</span></span>
    <span className="titlebar-title">— Tools · {pageTitle}</span>
    <span className="titlebar-spacer"></span>
    <span className="win-btn"><Icon name="min" /></span>
    <span className="win-btn"><Icon name="max" /></span>
    <span className="win-btn close"><Icon name="close" /></span>
  </div>
);

const NAV_ITEMS = {
  leaderboard: [
    { key: "global",      label: "Global Export",    icn: "export" },
    { key: "levelsearch", label: "Level Search",     icn: "search" },
    { key: "lookup",      label: "Player Lookup",    icn: "user"   },
    { key: "compare",     label: "Compare Players",  icn: "user"   },
  ],
  rush: [
    { key: "find",   label: "Seed Finder",        icn: "seed"     },
    { key: "parse",  label: "Seed Parser",        icn: "parse"    },
    { key: "splits", label: "Splits Updater",     icn: "splits"   },
    { key: "std",    label: "Standardize Splits", icn: "standard" },
    { key: "timer",  label: "Run Timer",          icn: "timer"    },
  ],
  resources: [
    { key: "ghosts", label: "Ghosts",       icn: "ghost" },
    { key: "videos", label: "Route Videos", icn: "video" },
  ],
};

/* onNav: (key: string) => void — called when a nav item is clicked */
export const Sidebar = ({ active = "parse", onNav, steamReady = false, playerName = "" }) => (
  <div className="sidebar">
    <div className="sidebar-brand">
      <div className="logo">NEON<br /><span className="accent">WHITE</span></div>
      <div className="ver">Tools · v2.0-dev</div>
    </div>
    <div className="sidebar-section"><Icon name="caret" size={10} /> Leaderboard Tools</div>
    {NAV_ITEMS.leaderboard.map(n => (
      <div key={n.key}
           className={"nav " + (active === n.key ? "active" : "")}
           onClick={() => onNav && onNav(n.key)}
           style={{ cursor: "pointer" }}>
        <span className="icn"><Icon name={n.icn} /></span>{n.label}
      </div>
    ))}
    <div className="sidebar-section"><Icon name="caret" size={10} /> Rush Tools</div>
    {NAV_ITEMS.rush.map(n => (
      <div key={n.key}
           className={"nav " + (active === n.key ? "active" : "")}
           onClick={() => onNav && onNav(n.key)}
           style={{ cursor: "pointer" }}>
        <span className="icn"><Icon name={n.icn} /></span>{n.label}
      </div>
    ))}
    <div className="sidebar-section"><Icon name="caret" size={10} /> Resources</div>
    {NAV_ITEMS.resources.map(n => (
      <div key={n.key}
           className={"nav " + (active === n.key ? "active" : "")}
           onClick={() => onNav && onNav(n.key)}
           style={{ cursor: "pointer" }}>
        <span className="icn"><Icon name={n.icn} /></span>{n.label}
      </div>
    ))}
    <div className="sidebar-spacer"></div>
    <div className={"nav " + (active === "settings" ? "active" : "")}
         onClick={() => onNav && onNav("settings")} style={{ cursor: "pointer" }}>
      <span className="icn"><Icon name="gear" /></span>Settings
    </div>
    <div className="sidebar-footer">
      <div className="row">
        <span className={"dot " + (steamReady ? "ok" : "bad")}></span>
        {steamReady ? (playerName || "Connected") : "Not connected"}
      </div>
    </div>
  </div>
);

/* === Page header === */
export const PageHead = ({ crumb, title, accentWord, actions }) => (
  <div className="pageheader">
    <div>
      <div className="crumb"><span className="accent-slash">//</span> {crumb}</div>
      <h1>{title}{accentWord && <> <span className="accent">{accentWord}</span></>}</h1>
    </div>
    <div className="actions">{actions}</div>
  </div>
);

/* === Form primitives === */
export const Field = ({ label, hint, conditional, children }) => (
  <div className="field">
    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
      <span className="field-label">{label}</span>
      {conditional && <span className="conditional-pill">{conditional}</span>}
    </div>
    {children}
    {hint && <div className="field-hint">{hint}</div>}
  </div>
);

export const Seg = ({ options, value, onChange }) => (
  <div className="seg">
    {options.map(o => (
      <span key={o}
            className={"seg-btn " + (o === value ? "on" : "")}
            onClick={() => onChange && onChange(o)}>
        {o}
      </span>
    ))}
  </div>
);

export const Cb = ({ on, label, onChange }) => (
  <span className={"cb " + (on ? "on" : "")}
        onClick={() => onChange && onChange(!on)}
        style={{ cursor: onChange ? "pointer" : "default" }}>
    <span className="cb-box"></span>
    {label}
  </span>
);

export const Btn = ({ children, kind = "", size = "", icn, onClick, disabled }) => (
  <button className={"btn " + kind + " " + size} onClick={onClick} disabled={disabled}>
    {icn && <span style={{ display: "inline-flex", verticalAlign: "middle", marginRight: 6 }}>
      <Icon name={icn} size={12} />
    </span>}
    {children}
  </button>
);

/* === Rush dropdown === */
export const RushSelect = ({ value, onChange }) => (
  <select className="input" value={value} onChange={e => onChange(e.target.value)}>
    {RUSHES.map(r => (
      <option key={r.name} value={r.name}>{r.name} — {r.count} levels</option>
    ))}
  </select>
);

/* === Output panel === */
export const OutputPanel = ({ title, body, onCopy }) => (
  <div className="output-panel">
    <div className="output-header">
      <span className="title">{title}</span>
      <div style={{ flex: 1 }} />
      {onCopy && <Btn kind="ghost" size="sm" icn="copy" onClick={onCopy}>Copy</Btn>}
    </div>
    <div className="output-body">{body}</div>
  </div>
);

/* === Medal badge === */
const MEDAL_COLORS = {
  "BLOOD DIAMOND": "#ff003d",
  "TOPAZ":         "#ffd700",
  "SAPPHIRE":      "#6ab0ff",
  "AMETHYST":      "#c77dff",
  "EMERALD":       "#3ddc84",
  "DEV":           "#ff4444",
  "ACE":           "#8de4e0",
  "GOLD":          "#ffd700",
  "SILVER":        "#c0c0c0",
  "BRONZE":        "#cd7f32",
};

const MEDAL_GRADIENTS = {
  "BLOOD DIAMOND": "linear-gradient(to right, #660000, #FF003D)",
  "TOPAZ":         "linear-gradient(to right, #ff4500, #ffd700)",
};

export const MedalBadge = ({ medal, plain = false }) => {
  if (!medal) return null;
  const gradient = MEDAL_GRADIENTS[medal];
  const color = MEDAL_COLORS[medal] || "var(--text-3)";

  if (plain) {
    if (gradient) {
      return (
        <span style={{
          display: "inline-block",
          fontSize: "0.82em", fontWeight: 700, letterSpacing: 0.5,
          background: gradient,
          WebkitBackgroundClip: "text",
          WebkitTextFillColor: "transparent",
          backgroundClip: "text",
          whiteSpace: "nowrap",
        }}>
          {medal}
        </span>
      );
    }
    return (
      <span style={{
        fontSize: "0.82em", fontWeight: 700, letterSpacing: 0.5,
        color, whiteSpace: "nowrap",
      }}>
        {medal}
      </span>
    );
  }

  // Pill mode
  if (gradient) {
    return (
      <span style={{
        display: "inline-block",
        fontSize: 9, fontWeight: 700, letterSpacing: 0.5,
        padding: "2px 5px", borderRadius: 1,
        background: "rgba(255,255,255,0.07)",
        border: "1px solid rgba(255,255,255,0.18)",
        whiteSpace: "nowrap",
      }}>
        <span style={{
          background: gradient,
          WebkitBackgroundClip: "text",
          WebkitTextFillColor: "transparent",
          backgroundClip: "text",
        }}>
          {medal}
        </span>
      </span>
    );
  }

  return (
    <span style={{
      fontSize: 9, fontWeight: 700, letterSpacing: 0.5,
      padding: "2px 5px", borderRadius: 1,
      background: color + "22",
      color,
      border: `1px solid ${color}55`,
      whiteSpace: "nowrap",
    }}>
      {medal}
    </span>
  );
};

/* === Medal toggle === */
export const MedalToggle = ({ value, onChange }) => (
  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
    <span style={{ fontSize: 11, color: "var(--text-2)" }}>Medals</span>
    <div
      role="switch"
      aria-checked={value}
      onClick={() => onChange(!value)}
      style={{
        width: 34, height: 18, borderRadius: 9, cursor: "pointer",
        background: value ? "var(--accent)" : "var(--surface-2)",
        border: `1px solid ${value ? "var(--accent)" : "var(--border)"}`,
        position: "relative", transition: "background 0.15s, border-color 0.15s",
        flexShrink: 0,
      }}
    >
      <div style={{
        position: "absolute", top: 2, left: value ? 16 : 2,
        width: 12, height: 12, borderRadius: "50%",
        background: value ? "var(--bg)" : "var(--text-3)",
        transition: "left 0.15s",
      }} />
    </div>
  </div>
);

/* === Error / status banner === */
export const ErrorBanner = ({ message }) =>
  message ? (
    <div style={{
      padding: "8px 12px",
      background: "rgba(255,90,95,0.12)",
      border: "1px solid rgba(255,90,95,0.3)",
      borderRadius: 2,
      color: "var(--bad)",
      fontSize: 11,
    }}>
      {message}
    </div>
  ) : null;
