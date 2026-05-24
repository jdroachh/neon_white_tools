// duplicate of web/src/protocol.ts — keep in sync.

export type EnvelopeBase = {
  t: string;
  ts: number;
  from?: string;
};

export type Hello       = EnvelopeBase & { t: "hello";    data: { token: string; nickname: string } };
export type TeamJoin    = EnvelopeBase & { t: "team_join"; data: { teamId: number | null } };
export type TeamRename  = EnvelopeBase & { t: "team_rename"; data: { teamId: number; name: string } };
export type SettingsMsg = EnvelopeBase & { t: "settings"; data: Settings };
export type Start       = EnvelopeBase & { t: "start";    data: { seed?: number } };
export type Claim       = EnvelopeBase & { t: "claim";    data: { squareIndex: number; timeMs: number | null } };
export type Unclaim     = EnvelopeBase & { t: "unclaim";  data: { squareIndex: number } };
export type Restart     = EnvelopeBase & { t: "restart";  data: { mode: "same" | "new" | "lobby" } };
export type Chat        = EnvelopeBase & { t: "chat";     data: { body: string; teamId?: number | null; nickname?: string | null; system?: boolean } };
export type State       = EnvelopeBase & { t: "state";    data: RoomState };
export type EndMsg      = EnvelopeBase & { t: "end";      data: { teamId: number; condition: WinConditionKey; shape?: number[] } };
export type ErrorMsg    = EnvelopeBase & { t: "error";    data: { message: string; reason?: string } };

export type Envelope = Hello | TeamJoin | TeamRename | SettingsMsg | Start | Claim | Unclaim | Restart | Chat | State | EndMsg | ErrorMsg;

export const MAX_TEAM_NAME_LEN = 24;

export type Settings = {
  boardSize: 5 | 7 | 9;
  sections: ("standard" | "level_completion" | "modded")[];
  allowModded: boolean;
  centerFree: boolean;
  lockout: boolean;       // ON = first team to claim owns it; OFF = multiple teams can claim same cell
  timeLimitMin: number;
  winConditions: WinConditionKey[];
  firstToN?: number;
};

export type WinConditionKey = "line" | "four_corners" | "full_house" | "first_to_n" | "time_limit";

export type MemberInfo = {
  nickname: string;
  teamId: number | null;
  online: boolean;
  joinedAt: number;
};

export type TeamInfo = {
  id: number;
  name: string;
  color: string;
  leaderToken: string | null;
  memberTokens: string[];
};

export type ClaimInfo = {
  teamId: number;
  timeMs: number | null;
  player: string;
  ts: number;
};

export type RoomState = {
  phase: "lobby" | "starting" | "playing" | "ended";
  hostToken: string | null;
  settings: Settings;
  members: Record<string, MemberInfo>;
  teams: TeamInfo[];
  board: { seed: number; squares: string[] } | null;
  claims: (ClaimInfo[] | null)[];   // each cell holds 0+ claims; null = empty. Lockout ON = at most one element.
  startingAt: number | null;        // populated during "starting" phase; countdown ends at startingAt + COUNTDOWN_MS
  startedAt: number | null;
  winner: { teamId: number; condition: WinConditionKey; shape?: number[] } | null;
};

export const COUNTDOWN_MS = 3000;

const VALID_BOARD_SIZES = new Set([5, 7, 9]);
const VALID_SECTIONS = new Set(["standard", "level_completion", "modded"]);
const VALID_WIN_CONDITIONS = new Set(["line", "four_corners", "full_house", "first_to_n", "time_limit"]);

function isObject(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

function isHello(e: Record<string, unknown>): e is Hello {
  const d = e["data"];
  return isObject(d) && typeof d["token"] === "string" && typeof d["nickname"] === "string";
}

function isTeamJoin(e: Record<string, unknown>): e is TeamJoin {
  const d = e["data"];
  return isObject(d) && (d["teamId"] === null || typeof d["teamId"] === "number");
}

function isTeamRename(e: Record<string, unknown>): e is TeamRename {
  const d = e["data"];
  return (
    isObject(d) &&
    typeof d["teamId"] === "number" &&
    typeof d["name"] === "string" &&
    (d["name"] as string).trim().length > 0 &&
    (d["name"] as string).length <= MAX_TEAM_NAME_LEN
  );
}

function isSettingsMsg(e: Record<string, unknown>): e is SettingsMsg {
  const d = e["data"];
  if (!isObject(d)) return false;
  return (
    VALID_BOARD_SIZES.has(d["boardSize"] as number) &&
    Array.isArray(d["sections"]) &&
    (d["sections"] as unknown[]).every((s) => VALID_SECTIONS.has(s as string)) &&
    typeof d["allowModded"] === "boolean" &&
    typeof d["centerFree"] === "boolean" &&
    typeof d["lockout"] === "boolean" &&
    typeof d["timeLimitMin"] === "number" &&
    Array.isArray(d["winConditions"]) &&
    (d["winConditions"] as unknown[]).every((w) => VALID_WIN_CONDITIONS.has(w as string))
  );
}

function isStart(e: Record<string, unknown>): e is Start {
  const d = e["data"];
  return isObject(d) && (d["seed"] === undefined || typeof d["seed"] === "number");
}

function isClaim(e: Record<string, unknown>): e is Claim {
  const d = e["data"];
  return (
    isObject(d) &&
    typeof d["squareIndex"] === "number" &&
    (d["timeMs"] === null || typeof d["timeMs"] === "number")
  );
}

function isUnclaim(e: Record<string, unknown>): e is Unclaim {
  const d = e["data"];
  return isObject(d) && typeof d["squareIndex"] === "number";
}

function isRestart(e: Record<string, unknown>): e is Restart {
  const d = e["data"];
  return isObject(d) && (d["mode"] === "same" || d["mode"] === "new" || d["mode"] === "lobby");
}

function isChat(e: Record<string, unknown>): e is Chat {
  const d = e["data"];
  if (!isObject(d) || typeof d["body"] !== "string") return false;
  // Optional fields — accept undefined or correct type.
  if (d["teamId"] !== undefined && d["teamId"] !== null && typeof d["teamId"] !== "number") return false;
  if (d["nickname"] !== undefined && d["nickname"] !== null && typeof d["nickname"] !== "string") return false;
  if (d["system"] !== undefined && typeof d["system"] !== "boolean") return false;
  return true;
}

export function parseEnvelope(raw: string): Envelope | null {
  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch {
    return null;
  }
  if (!isObject(parsed)) return null;
  if (typeof parsed["t"] !== "string") return null;
  if (typeof parsed["ts"] !== "number") return null;

  const t = parsed["t"];
  switch (t) {
    case "hello":    return isHello(parsed) ? parsed : null;
    case "team_join": return isTeamJoin(parsed) ? parsed : null;
    case "team_rename": return isTeamRename(parsed) ? parsed : null;
    case "settings": return isSettingsMsg(parsed) ? parsed : null;
    case "start":    return isStart(parsed) ? parsed : null;
    case "claim":    return isClaim(parsed) ? parsed : null;
    case "unclaim":  return isUnclaim(parsed) ? parsed : null;
    case "restart":  return isRestart(parsed) ? parsed : null;
    case "chat":     return isChat(parsed) ? parsed : null;
    default:         return null;
  }
}

export const DEFAULT_SETTINGS: Settings = {
  boardSize: 5,
  sections: ["standard"],
  allowModded: false,
  centerFree: false,
  lockout: true,
  timeLimitMin: 20,
  winConditions: ["line"],
};

export const TEAM_PALETTE: { name: string; color: string }[] = [
  { name: "Team 1", color: "#a78bfa" },
  { name: "Team 2", color: "#22c55e" },
  { name: "Team 3", color: "#eab308" },
  { name: "Team 4", color: "#ef4444" },
  { name: "Team 5", color: "#06b6d4" },
  { name: "Team 6", color: "#ec4899" },
];

export function makeInitialState(): RoomState {
  return {
    phase: "lobby",
    hostToken: null,
    settings: { ...DEFAULT_SETTINGS, sections: [...DEFAULT_SETTINGS.sections], winConditions: [...DEFAULT_SETTINGS.winConditions] },
    members: {},
    teams: TEAM_PALETTE.map((p, i) => ({
      id: i,
      name: p.name,
      color: p.color,
      leaderToken: null,
      memberTokens: [],
    })),
    board: null,
    claims: [],
    startingAt: null,
    startedAt: null,
    winner: null,
  };
}
