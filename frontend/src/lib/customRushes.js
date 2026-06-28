// Persistence for user-built "custom rushes" used by the Run Timer's custom mode.
// Unlike custom_level_presets (an unordered level *set*), a rush is an ordered
// sequence — `levels` preserves play order. Mirrors the customLevels.js pattern.
import { getConfig, saveConfigField } from "../api.js";

const KEY = "custom_rushes";
const MAX_RUSHES = 50;

const asStringArray = (v) =>
  Array.isArray(v) ? v.filter(x => typeof x === "string") : [];

export async function loadCustomRushes() {
  const cfg = await getConfig();
  if (!Array.isArray(cfg[KEY])) return [];
  return cfg[KEY]
    .filter(r => r && typeof r.name === "string" && Array.isArray(r.levels))
    .map(r => ({ name: r.name, levels: asStringArray(r.levels) }));
}

export async function saveCustomRushes(list) {
  await saveConfigField(KEY, list);
}

// Returns { error, list }. Newest rush goes to the top. `levels` is kept in the
// given order (play order) — NOT sorted.
export function addCustomRush(list, name, levels) {
  const nm = (name || "").trim();
  if (!nm) return { error: "Rush name can't be empty.", list };
  if (nm.length > 40) return { error: "Rush name must be 40 characters or fewer.", list };
  if (!levels.length) return { error: "Add at least one stage before saving a rush.", list };
  if (list.some(r => r.name.toLowerCase() === nm.toLowerCase()))
    return { error: `A rush named "${nm}" already exists.`, list };
  if (list.length >= MAX_RUSHES) return { error: `Limit: ${MAX_RUSHES} rushes.`, list };
  return { error: null, list: [{ name: nm, levels: [...levels] }, ...list] };
}

export function removeCustomRush(list, name) {
  return list.filter(r => r.name !== name);
}

export const MAX = MAX_RUSHES;
