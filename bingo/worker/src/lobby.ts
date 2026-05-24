import { DurableObject } from "cloudflare:workers";

export class LobbyDO extends DurableObject {
  async fetch(request: Request): Promise<Response> {
    const upgradeHeader = request.headers.get("Upgrade");
    if (!upgradeHeader || upgradeHeader.toLowerCase() !== "websocket") {
      return new Response("Expected WebSocket upgrade", { status: 426 });
    }

    const pair = new WebSocketPair();
    const [client, server] = Object.values(pair);

    this.ctx.acceptWebSocket(server);

    console.log(`[${new Date().toISOString()}] WebSocket accepted; total sockets: ${this.ctx.getWebSockets().length}`);

    return new Response(null, { status: 101, webSocket: client });
  }

  webSocketMessage(ws: WebSocket, message: string | ArrayBuffer): void {
    const sockets = this.ctx.getWebSockets();
    console.log(`[${new Date().toISOString()}] Message received; broadcasting to ${sockets.length - 1} other socket(s)`);

    for (const socket of sockets) {
      if (socket === ws) continue;
      socket.send(message);
    }
  }

  webSocketClose(ws: WebSocket, code: number, reason: string, wasClean: boolean): void {
    console.log(`[${new Date().toISOString()}] WebSocket closed — code=${code} reason=${reason} wasClean=${wasClean}`);
  }

  webSocketError(ws: WebSocket, error: unknown): void {
    console.log(`[${new Date().toISOString()}] WebSocket error — ${String(error)}`);
  }
}
