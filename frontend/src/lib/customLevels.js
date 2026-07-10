// Persistence for the custom-level-set picker (Player Lookup / Compare Players /
// Multi Compare). Last selection is per-page; presets are global (a named set
// means the same thing on every page). Mirrors the savedProfiles.js pattern.
import { getConfig, saveConfigField } from "../api.js";

const LAST_KEYS = {
  pl: "custom_levels_last_pl",
  cp: "custom_levels_last_cp",
  mc: "custom_levels_last_mc",
  avg: "custom_levels_last_avg",
  medal: "custom_levels_last_medal",
};
const PRESETS_KEY = "custom_level_presets";
const MAX_PRESETS = 50;

const asStringArray = (v) =>
  Array.isArray(v) ? v.filter(x => typeof x === "string") : [];

export async function loadLastSelection(pageKey) {
  const cfg = await getConfig();
  return asStringArray(cfg[LAST_KEYS[pageKey]]);
}

export async function saveLastSelection(pageKey, levels) {
  await saveConfigField(LAST_KEYS[pageKey], asStringArray(levels));
}

export async function loadPresets() {
  const cfg = await getConfig();
  if (!Array.isArray(cfg[PRESETS_KEY])) return [];
  return cfg[PRESETS_KEY]
    .filter(p => p && typeof p.name === "string" && Array.isArray(p.levels))
    .map(p => ({ name: p.name, levels: asStringArray(p.levels) }));
}

export async function savePresets(list) {
  await saveConfigField(PRESETS_KEY, list);
}

// Returns { error, list }. Newest preset goes to the top.
export function addPreset(list, name, levels) {
  const nm = (name || "").trim();
  if (!nm) return { error: "Preset name can't be empty.", list };
  if (nm.length > 40) return { error: "Preset name must be 40 characters or fewer.", list };
  if (!levels.length) return { error: "Pick at least one level before saving a preset.", list };
  if (list.some(p => p.name.toLowerCase() === nm.toLowerCase()))
    return { error: `A preset named "${nm}" already exists.`, list };
  if (list.length >= MAX_PRESETS) return { error: `Limit: ${MAX_PRESETS} presets.`, list };
  return { error: null, list: [{ name: nm, levels: [...levels] }, ...list] };
}

export function removePreset(list, name) {
  return list.filter(p => p.name !== name);
}

export const MAX = MAX_PRESETS;
