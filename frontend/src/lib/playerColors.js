// 16-color palette extending ROYGBIV. Used by the Multi-Compare roster color
// picker and cell renderer (must have at least MAX_ROWS entries so every
// player can get a distinct winner-cell color). Neutral name on purpose —
// Bingo Mode (Phase 2) will import the same palette for team colors.
//
// `key` is the canonical identifier stored on a player row.

export const PLAYER_COLORS = [
  { key: "red",     label: "Red",     hex: "#ef4444" },
  { key: "orange",  label: "Orange",  hex: "#ff9900" },
  { key: "yellow",  label: "Yellow",  hex: "#FFEE00" },
  { key: "green",   label: "Green",   hex: "#22c55e" },
  { key: "blue",    label: "Blue",    hex: "#3b82f6" },
  { key: "navy",    label: "Navy",    hex: "#1e3a8a" },
  { key: "violet",  label: "Violet",  hex: "#a855f7" },
  { key: "pink",    label: "Pink",    hex: "#ec4899" },
  { key: "cyan",    label: "Cyan",    hex: "#06b6d4" },
  { key: "white",   label: "White",   hex: "#e5e7eb" },
  { key: "lime",    label: "Lime",    hex: "#a3e635" },
  { key: "teal",    label: "Teal",    hex: "#0f766e" },
  { key: "indigo",  label: "Indigo",  hex: "#6366f1" },
  { key: "magenta", label: "Magenta", hex: "#d946ef" },
  { key: "brown",   label: "Brown",   hex: "#b45309" },
  { key: "slate",   label: "Slate",   hex: "#94a3b8" },
];

export const COLOR_BY_KEY = Object.fromEntries(PLAYER_COLORS.map(c => [c.key, c]));

export function hexFor(key) {
  return (COLOR_BY_KEY[key] || PLAYER_COLORS[0]).hex;
}

// Returns the first palette color not currently used by any row.
export function nextAvailableColor(usedKeys) {
  const used = new Set(usedKeys);
  const free = PLAYER_COLORS.find(c => !used.has(c.key));
  return (free || PLAYER_COLORS[0]).key;
}
