const WS_BASE =
  import.meta.env.VITE_WS_URL ?? "ws://localhost:8787";

const connectBtn = document.getElementById("connect-btn") as HTMLButtonElement;
const sendBtn = document.getElementById("send-btn") as HTMLButtonElement;
const nicknameInput = document.getElementById("nickname") as HTMLInputElement;
const roomCodeInput = document.getElementById("room-code") as HTMLInputElement;
const messageInput = document.getElementById("message-input") as HTMLInputElement;
const statusEl = document.getElementById("status") as HTMLDivElement;
const logEl = document.getElementById("log") as HTMLDivElement;

let socket: WebSocket | null = null;
let nickname = "";

function appendLog(text: string): void {
  const entry = document.createElement("div");
  entry.className = "log-entry";
  const ts = new Date().toLocaleTimeString();
  entry.innerHTML = `<span class="ts">[${ts}]</span> ${escapeHtml(text)}`;
  logEl.appendChild(entry);
  logEl.scrollTop = logEl.scrollHeight;
}

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function setConnected(connected: boolean): void {
  connectBtn.disabled = connected;
  sendBtn.disabled = !connected;
  messageInput.disabled = !connected;
  nicknameInput.disabled = connected;
  roomCodeInput.disabled = connected;
}

connectBtn.addEventListener("click", () => {
  nickname = nicknameInput.value.trim();
  const roomCode = roomCodeInput.value.trim();

  if (!nickname || !roomCode) {
    statusEl.textContent = "Please enter a nickname and room code.";
    return;
  }

  const url = `${WS_BASE}/ws/${encodeURIComponent(roomCode)}`;
  console.log(`[${new Date().toISOString()}] Connecting to ${url}`);
  statusEl.textContent = `Connecting to room "${roomCode}"…`;

  socket = new WebSocket(url);

  socket.addEventListener("open", () => {
    console.log(`[${new Date().toISOString()}] WebSocket open`);
    statusEl.textContent = `Connected to room "${roomCode}" as "${nickname}".`;
    setConnected(true);
    appendLog(`*** You joined as "${nickname}".`);
  });

  socket.addEventListener("message", (event) => {
    const raw = typeof event.data === "string" ? event.data : "[binary]";
    console.log(`[${new Date().toISOString()}] Message received: ${raw}`);

    let display: string;
    try {
      const parsed = JSON.parse(raw) as { nickname?: string; body?: string; ts?: number };
      const sender = parsed.nickname ?? "unknown";
      const body = parsed.body ?? raw;
      display = `<${sender}> ${body}`;
    } catch {
      display = raw;
    }
    appendLog(display);
  });

  socket.addEventListener("close", (event) => {
    console.log(`[${new Date().toISOString()}] WebSocket closed — code=${event.code}`);
    statusEl.textContent = `Disconnected (code ${event.code}).`;
    setConnected(false);
    appendLog(`*** Disconnected.`);
    socket = null;
  });

  socket.addEventListener("error", () => {
    console.log(`[${new Date().toISOString()}] WebSocket error`);
    statusEl.textContent = "Connection error.";
  });
});

sendBtn.addEventListener("click", sendMessage);
messageInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter") sendMessage();
});

function sendMessage(): void {
  if (!socket || socket.readyState !== WebSocket.OPEN) return;
  const body = messageInput.value.trim();
  if (!body) return;

  const payload = JSON.stringify({ nickname, body, ts: Date.now() });
  socket.send(payload);
  appendLog(`<${nickname}> ${body}`);
  messageInput.value = "";
}
