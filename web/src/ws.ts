import type { WsEvent } from "./types";

export class ChattySocket {
  private ws: WebSocket | null = null;
  private token: string | null = null;
  private closedByUser = false;
  private reconnectTimer: number | null = null;

  constructor(private onEvent: (ev: WsEvent) => void) {}

  connect(token: string) {
    if (this.token === token && this.ws?.readyState === WebSocket.OPEN) return;
    this.disconnect();
    this.token = token;
    this.closedByUser = false;
    this.open();
  }

  private open() {
    if (!this.token) return;
    const proto = location.protocol === "https:" ? "wss" : "ws";
    this.ws = new WebSocket(`${proto}://${location.host}/ws?token=${encodeURIComponent(this.token)}`);
    this.ws.onmessage = (e) => {
      try {
        this.onEvent(JSON.parse(e.data) as WsEvent);
      } catch {
        /* ignore */
      }
    };
    this.ws.onclose = () => {
      if (!this.closedByUser) {
        this.reconnectTimer = window.setTimeout(() => this.open(), 2000);
      }
    };
    this.ws.onopen = () => {
      // keepalive
      this.ws?.send(JSON.stringify({ type: "ping" }));
    };
  }

  disconnect() {
    this.closedByUser = true;
    if (this.reconnectTimer) window.clearTimeout(this.reconnectTimer);
    this.ws?.close();
    this.ws = null;
  }
}