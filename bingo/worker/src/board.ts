import squaresData from "../../squares.json";
import type { Settings, ClaimInfo, WinConditionKey } from "./protocol";
import type { RoomState } from "./protocol";

type Square = { name: string; mods_required: string[]; verification: string };
type SquaresJson = {
  standard: Square[];
  level_completion: Square[];
  modded: Square[];
  _meta?: unknown;
};

const squares = squaresData as SquaresJson;

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

export function generateBoard(
  settings: Settings,
  seed: number,
): { squares: string[] } | { error: string } {
  const pool: Square[] = [];
  for (const section of settings.sections) {
    const src = squares[section as keyof SquaresJson];
    if (Array.isArray(src)) {
      pool.push(...(src as Square[]).filter((s) => s.verification === "honor"));
    }
  }

  const filtered = pool.filter((s) => {
    if (!settings.allowModded && s.mods_required.length > 0) return false;
    return true;
  });

  const total = settings.boardSize ** 2;
  const required = settings.centerFree ? total - 1 : total;

  if (filtered.length < required) {
    return {
      error: `Pool too small: ${filtered.length} squares available, ${required} needed. Try enabling more sections or allowModded.`,
    };
  }

  const rng = mulberry32(seed);
  const shuffled = fisherYates(filtered, rng);
  const selected = shuffled.slice(0, required).map((s) => s.name);

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
  const n = settings.firstToN ?? 5;
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
      case "time_limit":   result = evalTimeLimit(claims); break;
    }
    if (result) return { teamId: result.teamId, condition: cond, shape: result.shape };
  }
  return null;
}
