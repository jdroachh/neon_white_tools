import { LobbyDO } from "./lobby";

export { LobbyDO };

export interface Env {
  LOBBY: DurableObjectNamespace;
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);
    const { pathname } = url;

    if (pathname === "/health") {
      return new Response("ok", { status: 200 });
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
