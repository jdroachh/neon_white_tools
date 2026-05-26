import squaresData from "../../squares.json";
import type { Settings, ClaimInfo, WinConditionKey, MedalTier, MedalKind } from "./protocol";
import type { RoomState } from "./protocol";

type Square = {
  id: string;
  name: string;
  mods_required: string[];
  verification: string;
  medal_tier?: MedalTier;
  medal_kind?: MedalKind;
  rush?: boolean;
};
type SquaresJson = {
  standard: Square[];
  level_completion: Square[];
  modded: Square[];
  mean: Square[];
  medals: Square[];
  _meta?: unknown;
};

const squares = squaresData as SquaresJson;

const MEDAL_TIER_RANK: Record<MedalTier, number> = {
  dev: 0,
  emerald: 1,
  amethyst: 2,
  sapphire: 3,
};

function mulberry32(seed: number): () => number {
  return () => {
    let t = (seed += 0x6d2b79f5);
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function fisherYates<T>(arr: T[], rng: () => number): T[] {
  const a = arr.slice();
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(rng() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

function collectSection(section: string, settings: Settings): Square[] {
  const src = squares[section as keyof SquaresJson];
  if (!Array.isArray(src)) return [];
  const excluded = new Set(settings.excludedSquareIds);
  const out: Square[] = [];
  for (const s of src as Square[]) {
    if (s.verification !== "honor" && s.verification !== "dice") continue;
    if (!settings.allowModded && s.mods_required.length > 0) continue;
    if (!settings.allowRushes && s.rush) continue;
    if (excluded.has(s.id)) continue;
    if (section === "medals") {
      if (!s.medal_tier) continue;
      // Ceiling applies to both aggregated and per-level.
      if (MEDAL_TIER_RANK[s.medal_tier] > MEDAL_TIER_RANK[settings.medalThreshold]) continue;
      // Per-level squares are further gated by which tiers the host enabled.
      // Aggregated "Beat N [tier] medals" squares bypass this and are governed
      // by the ceiling alone.
      if (s.medal_kind === "per_level" && !settings.perLevelMedalTiers.includes(s.medal_tier)) continue;
    }
    out.push(s);
  }
  return out;
}

export function generateBoard(
  settings: Settings,
  seed: number,
): { squares: string[] } | { error: string } {
  const rng = mulberry32(seed);
  const total = settings.boardSize ** 2;
  const required = settings.centerFree ? total - 1 : total;

  const medalsEnabled = settings.sections.includes("medals");
  const otherSections = settings.sections.filter((s) => s !== "medals");
  const medalsOnly = medalsEnabled && otherSections.length === 0;

  const medalPool = medalsEnabled ? collectSection("medals", settings) : [];
  const otherPool: Square[] = [];
  for (const sec of otherSections) otherPool.push(...collectSection(sec, settings));

  // Cap medal picks. If medals is the only section, the cap is ignored — we need
  // to fill the whole board from medals.
  const cap = medalsOnly
    ? medalPool.length
    : Math.min(Math.max(0, settings.medalSquareCap), medalPool.length);

  const medalPick = fisherYates(medalPool, rng).slice(0, Math.min(cap, required));
  const needed = required - medalPick.length;

  if (otherPool.length < needed) {
    const excluded = new Set(settings.excludedSquareIds);
    const exclusionNote = excluded.size > 0 ? ` (${excluded.size} excluded via Advanced)` : "";
    const haveTotal = medalPick.length + otherPool.length;
    return {
      error: `Pool too small: ${haveTotal} squares available, ${required} needed${exclusionNote}. Try enabling more sections, raising the medal cap, allowing modded, lowering the medal threshold, or re-enabling excluded squares.`,
    };
  }

  const otherPick = fisherYates(otherPool, rng).slice(0, needed);
  const combined = fisherYates([...medalPick, ...otherPick], rng);
  const selected = combined.slice(0, required).map((s) => s.name);

  if (settings.centerFree) {
    const centerIdx = Math.floor(total / 2);
    selected.splice(centerIdx, 0, "FREE");
  }

  return { squares: selected };
}

// Win evaluators — each returns first hit or null.
// Claims model: claims[i] is either null (empty) or a non-empty array of
// ClaimInfo. Lockout ON enforces array.length === 1. FREE sentinel is stored
// as a single-element array with teamId = -1 and counts toward every team.

type WinResult = { teamId: number; shape?: number[] } | null;

// "Does this cell count for teamId?" — true if FREE sentinel OR any claim by teamId.
function cellCountsFor(cell: ClaimInfo[] | null, teamId: number): boolean {
  if (!cell) return false;
  return cell.some((c) => c.teamId === teamId || c.teamId === -1);
}

function realTeamsOnBoard(claims: (ClaimInfo[] | null)[]): Set<number> {
  const ids = new Set<number>();
  for (const cell of claims) {
    if (!cell) continue;
    for (const c of cell) if (c.teamId !== -1) ids.add(c.teamId);
  }
  return ids;
}

export function evalLine(
  claims: (ClaimInfo[] | null)[],
  boardSize: number,
): WinResult {
  const teamIds = realTeamsOnBoard(claims);

  const lines: number[][] = [];
  for (let r = 0; r < boardSize; r++) {
    const row: number[] = [];
    for (let c = 0; c < boardSize; c++) row.push(r * boardSize + c);
    lines.push(row);
  }
  for (let c = 0; c < boardSize; c++) {
    const col: number[] = [];
    for (let r = 0; r < boardSize; r++) col.push(r * boardSize + c);
    lines.push(col);
  }
  const diag1: number[] = [];
  const diag2: number[] = [];
  for (let i = 0; i < boardSize; i++) {
    diag1.push(i * boardSize + i);
    diag2.push(i * boardSize + (boardSize - 1 - i));
  }
  lines.push(diag1, diag2);

  for (const teamId of teamIds) {
    for (const line of lines) {
      if (line.every((idx) => cellCountsFor(claims[idx], teamId))) {
        return { teamId, shape: line };
      }
    }
  }
  return null;
}

export function evalFourCorners(
  claims: (ClaimInfo[] | null)[],
  boardSize: number,
): WinResult {
  const corners = [0, boardSize - 1, boardSize * (boardSize - 1), boardSize ** 2 - 1];
  for (const teamId of realTeamsOnBoard(claims)) {
    if (corners.every((idx) => cellCountsFor(claims[idx], teamId))) {
      return { teamId, shape: corners };
    }
  }
  return null;
}

export function evalFullHouse(
  claims: (ClaimInfo[] | null)[],
  boardSize: number,
): WinResult {
  const total = boardSize ** 2;
  for (const teamId of realTeamsOnBoard(claims)) {
    let full = true;
    for (let i = 0; i < total; i++) {
      if (!cellCountsFor(claims[i], teamId)) { full = false; break; }
    }
    if (full) return { teamId, shape: Array.from({ length: total }, (_, i) => i) };
  }
  return null;
}

export function evalFirstToN(
  claims: (ClaimInfo[] | null)[],
  settings: Settings,
): WinResult {
  const n = settings.firstToN ?? Math.ceil((settings.boardSize ** 2) / 2);
  for (const teamId of realTeamsOnBoard(claims)) {
    const idxs: number[] = [];
    for (let i = 0; i < claims.length; i++) {
      if (cellCountsFor(claims[i], teamId)) idxs.push(i);
    }
    if (idxs.length >= n) return { teamId, shape: idxs };
  }
  return null;
}

export function evalTimeLimit(
  claims: (ClaimInfo[] | null)[],
): WinResult {
  // Count cells per team (FREE counts for everyone); tie-break by sum of timeMs
  // across that team's actual claims (FREE has no timeMs).
  const stats = new Map<number, { count: number; timeSum: number; idxs: number[] }>();
  const teamIds = realTeamsOnBoard(claims);
  for (const teamId of teamIds) stats.set(teamId, { count: 0, timeSum: 0, idxs: [] });

  for (let i = 0; i < claims.length; i++) {
    const cell = claims[i];
    if (!cell) continue;
    for (const teamId of teamIds) {
      if (cellCountsFor(cell, teamId)) {
        const entry = stats.get(teamId)!;
        entry.count++;
        entry.idxs.push(i);
        // Sum times only across this team's own (non-FREE) claims on the cell.
        for (const c of cell) {
          if (c.teamId === teamId) entry.timeSum += c.timeMs ?? 0;
        }
      }
    }
  }
  if (stats.size === 0) return null;

  let best: { teamId: number; count: number; timeSum: number; idxs: number[] } | null = null;
  for (const [teamId, entry] of stats) {
    if (
      best === null ||
      entry.count > best.count ||
      (entry.count === best.count && entry.timeSum < best.timeSum)
    ) {
      best = { teamId, ...entry };
    }
  }
  if (!best) return null;
  return { teamId: best.teamId, shape: best.idxs };
}

export function evaluateWin(state: RoomState): { teamId: number; condition: WinConditionKey; shape?: number[] } | null {
  const { claims, board, settings } = state;
  if (!board) return null;
  const bs = settings.boardSize;

  for (const cond of settings.winConditions) {
    let result: WinResult = null;
    switch (cond) {
      case "line":         result = evalLine(claims, bs); break;
      case "four_corners": result = evalFourCorners(claims, bs); break;
      case "full_house":   result = evalFullHouse(claims, bs); break;
      case "first_to_n":   result = evalFirstToN(claims, settings); break;
      // time_limit is evaluated only by the alarm, never per-claim — otherwise
      // the first claim trivially "wins" (most cells = 1 vs 0 for everyone else).
      case "time_limit":   continue;
    }
    if (result) return { teamId: result.teamId, condition: cond, shape: result.shape };
  }

  // Board-full fallback: if every cell has a claim and no configured condition
  // has fired, award the win to the team with the most cells (ties broken by
  // lowest summed timeMs, same rule as time_limit). Prevents games from
  // stalling forever when settings make no winner reachable (e.g. lockout off
  // + line/first_to_n that no team will hit).
  if (claims.length > 0 && claims.every((c) => c !== null)) {
    const fallback = evalTimeLimit(claims);
    if (fallback) {
      return { teamId: fallback.teamId, condition: "board_full", shape: fallback.shape };
    }
  }
  return null;
}
