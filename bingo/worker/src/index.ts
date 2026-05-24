import { LobbyDO } from "./lobby";

export { LobbyDO };

export interface Env {
  LOBBY: DurableObjectNamespace;
}

// Code alphabet omits visually ambiguous chars (0/O, 1/I).
const CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789";
const CODE_LENGTH = 6;

function generateRoomCode(): string {
  const buf = new Uint8Array(CODE_LENGTH);
  crypto.getRandomValues(buf);
  let out = "";
  for (const b of buf) out += CODE_ALPHABET[b % CODE_ALPHABET.length];
  return out;
}

const CORS_HEADERS: Record<string, string> = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type",
};

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);
    const { pathname } = url;

    if (pathname === "/health") {
      return new Response("ok", { status: 200 });
    }

    if (pathname === "/create-room") {
      if (request.method === "OPTIONS") {
        return new Response(null, { status: 204, headers: CORS_HEADERS });
      }
      if (request.method !== "POST") {
        return new Response("Method Not Allowed", { status: 405, headers: CORS_HEADERS });
      }
      // 6-char from 32-char alphabet = 1B combinations. Collision risk at beta
      // scale is negligible; if a created code happens to hit an active room, the
      // would-be host's WS hello slots them in as a member of the existing room
      // instead — recoverable, just unlucky. Skip the existence probe for now.
      const code = generateRoomCode();
      return new Response(JSON.stringify({ code }), {
        status: 200,
        headers: { "Content-Type": "application/json", ...CORS_HEADERS },
      });
    }

    const wsMatch = pathname.match(/^\/ws\/([A-Za-z0-9_-]+)$/);
    if (wsMatch) {
      const roomCode = wsMatch[1];
      const id = env.LOBBY.idFromName(roomCode);
      const stub = env.LOBBY.get(id);
      return stub.fetch(request);
    }

    return new Response("Not Found", { status: 404 });
  },
};
