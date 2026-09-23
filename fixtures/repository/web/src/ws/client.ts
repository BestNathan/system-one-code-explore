export class WebSocketClient {
  private socket?: WebSocket;
  private reconnectTimer?: ReturnType<typeof setTimeout>;

  connect(url: string) {
    this.socket = new WebSocket(url);
    this.socket.onopen = () => this.clearReconnect();
    this.socket.onclose = () => this.scheduleReconnect(url);
    this.socket.onerror = () => this.socket?.close();
  }

  private scheduleReconnect(url: string) {
    this.reconnectTimer = setTimeout(() => this.connect(url), 1000);
  }

  private clearReconnect() {
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
  }
}
