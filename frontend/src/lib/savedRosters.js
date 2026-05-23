import { getConfig, saveConfigField } from "../api.js";

const MAX_ROSTERS = 25;

export function validateNickname(nickname) {
  const nick = (nickname || "").trim();
  if (!nick || nick.length > 32) return "Nickname must be 1–32 characters.";
  return null;
}

export async function loadRosters() {
  const cfg = await getConfig();
  return Array.isArray(cfg.saved_rosters) ? cfg.saved_rosters : [];
}

export async function saveRosters(list) {
  await saveConfigField("saved_rosters", list);
}

/**
 * Roster shape:
 *   { nickname, members: [{color, name, initial, steam_id}], saved_at }
 *
 * `members` is the *filled* roster snapshot — empty rows are filtered out
 * before save (caller decides). No validation of member format here; we trust
 * the caller (MultiCompare.jsx) to pass clean data.
 */
export function addRoster(list, rosterObj) {
  const err = validateNickname(rosterObj.nickname);
  if (err) return { error: err, list };
  if (list.some(r => r.nickname.toLowerCase() === rosterObj.nickname.trim().toLowerCase())) {
    return { error: "A roster with that name is already saved.", list };
  }
  if (list.length >= MAX_ROSTERS) {
    return { error: `Limit: ${MAX_ROSTERS} rosters.`, list };
  }
  const nickname = (rosterObj.nickname || "").trim();
  const next = [...list, { ...rosterObj, nickname, saved_at: new Date().toISOString() }];
  return { error: null, list: next };
}

export function updateNickname(list, idx, nickname) {
  const err = validateNickname(nickname);
  if (err) return { error: err, list };
  const trimmed = nickname.trim();
  if (list.some((r, i) => i !== idx && r.nickname.toLowerCase() === trimmed.toLowerCase())) {
    return { error: "A roster with that name is already saved.", list };
  }
  const next = list.map((r, i) => i === idx ? { ...r, nickname: trimmed } : r);
  return { error: null, list: next };
}

export function removeRoster(list, idx) {
  return list.filter((_, i) => i !== idx);
}

export function moveRoster(list, idx, dir) {
  const next = [...list];
  const target = idx + dir;
  if (target < 0 || target >= next.length) return next;
  [next[idx], next[target]] = [next[target], next[idx]];
  return next;
}

export const MAX = MAX_ROSTERS;
