import { getConfig, saveConfigField } from "../api.js";

const STEAM_ID_RE = /^\d{17}$/;
const MAX_PROFILES = 50;

export function validateProfile(nickname, steam_id) {
  const nick = (nickname || "").trim();
  if (!nick || nick.length > 24) return "Nickname must be 1–24 characters.";
  if (!STEAM_ID_RE.test((steam_id || "").trim())) return "Steam ID must be exactly 17 digits.";
  return null;
}

export async function loadProfiles() {
  const cfg = await getConfig();
  return Array.isArray(cfg.saved_profiles) ? cfg.saved_profiles : [];
}

export async function saveProfiles(list) {
  await saveConfigField("saved_profiles", list);
}

export function addProfile(list, profile) {
  const nick = (profile.nickname || "").trim();
  const id   = (profile.steam_id || "").trim();
  const err  = validateProfile(nick, id);
  if (err) return { error: err, list };
  if (list.some(p => p.steam_id === id)) return { error: "That Steam ID is already saved.", list };
  if (list.length >= MAX_PROFILES) return { error: `Limit: ${MAX_PROFILES} profiles.`, list };
  return { error: null, list: [...list, { nickname: nick, steam_id: id }] };
}

export function updateProfile(list, idx, profile) {
  const nick = (profile.nickname || "").trim();
  const id   = (profile.steam_id || "").trim();
  const err  = validateProfile(nick, id);
  if (err) return { error: err, list };
  if (list.some((p, i) => i !== idx && p.steam_id === id)) return { error: "That Steam ID is already saved.", list };
  const next = list.map((p, i) => i === idx ? { nickname: nick, steam_id: id } : p);
  return { error: null, list: next };
}

export function removeProfile(list, idx) {
  return list.filter((_, i) => i !== idx);
}

export function moveProfile(list, idx, dir) {
  const next = [...list];
  const target = idx + dir;
  if (target < 0 || target >= next.length) return next;
  [next[idx], next[target]] = [next[target], next[idx]];
  return next;
}

export const isValidNewId = (id, list) =>
  STEAM_ID_RE.test((id || "").trim()) && !list.some(p => p.steam_id === (id || "").trim());

export const MAX = MAX_PROFILES;
