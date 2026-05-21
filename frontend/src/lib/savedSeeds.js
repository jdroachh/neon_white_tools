import { getConfig, saveConfigField } from "../api.js";

const MAX_SEEDS = 50;

export function validateNickname(nickname) {
  const nick = (nickname || "").trim();
  if (!nick || nick.length > 32) return "Nickname must be 1–32 characters.";
  return null;
}

export async function loadSeeds() {
  const cfg = await getConfig();
  return Array.isArray(cfg.saved_seeds) ? cfg.saved_seeds : [];
}

export async function saveSeeds(list) {
  await saveConfigField("saved_seeds", list);
}

export function addSeed(list, seedObj) {
  const err = validateNickname(seedObj.nickname);
  if (err) return { error: err, list };
  if (list.some(s => s.seed === seedObj.seed)) {
    return { error: "That seed is already saved.", list };
  }
  if (list.length >= MAX_SEEDS) {
    return { error: `Limit: ${MAX_SEEDS} seeds.`, list };
  }
  const nickname = (seedObj.nickname || "").trim();
  const next = [...list, { ...seedObj, nickname, saved_at: new Date().toISOString() }];
  return { error: null, list: next };
}

export function updateNickname(list, idx, nickname) {
  const err = validateNickname(nickname);
  if (err) return { error: err, list };
  const trimmed = nickname.trim();
  const next = list.map((s, i) => i === idx ? { ...s, nickname: trimmed } : s);
  return { error: null, list: next };
}

export function removeSeed(list, idx) {
  return list.filter((_, i) => i !== idx);
}

export function moveSeed(list, idx, dir) {
  const next = [...list];
  const target = idx + dir;
  if (target < 0 || target >= next.length) return next;
  [next[idx], next[target]] = [next[target], next[idx]];
  return next;
}

export const MAX = MAX_SEEDS;
