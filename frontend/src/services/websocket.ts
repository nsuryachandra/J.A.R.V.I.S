/**
 * Real-time WebSocket connection to JARVIS Holographic Core.
 */

export type CoreStatus = 'ONLINE' | 'CONNECTING' | 'OFFLINE';

export interface CoreTelemetryEvent {
  type: string;
  status?: string;
  timestamp?: string;
  level?: number;
  [key: string]: any;
}

export type TelemetryListener = (event: CoreTelemetryEvent) => void;

class JarvisWebSocketClient {
  private socket: WebSocket | null = null;
  private listeners: Set<TelemetryListener> = new Set();
  private status: CoreStatus = 'OFFLINE';
  private pingInterval: number | null = null;

  public connect() {
    if (this.socket && (this.socket.readyState === WebSocket.OPEN || this.socket.readyState === WebSocket.CONNECTING)) {
      return;
    }

    this.status = 'CONNECTING';
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    // Use window.location.host with fallback
    const host = window.location.host || 'localhost:5173';
    const wsUrl = `${protocol}//${host}/api/v1/ws/core`;

    try {
      this.socket = new WebSocket(wsUrl);

      this.socket.onopen = () => {
        this.status = 'ONLINE';
        this.notifyListeners({ type: 'STATUS_CHANGE', status: 'ONLINE' });
        this.startHeartbeat();
      };

      this.socket.onmessage = (event) => {
        try {
          const parsed = JSON.parse(event.data);
          this.notifyListeners(parsed);
        } catch {
          // Non-JSON message
        }
      };

      this.socket.onclose = () => {
        this.status = 'OFFLINE';
        this.stopHeartbeat();
        this.notifyListeners({ type: 'STATUS_CHANGE', status: 'OFFLINE' });
        // Attempt reconnect after 3 seconds
        setTimeout(() => this.connect(), 3000);
      };

      this.socket.onerror = () => {
        this.status = 'OFFLINE';
      };
    } catch {
      this.status = 'OFFLINE';
    }
  }

  public subscribe(listener: TelemetryListener): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  public send(data: object) {
    if (this.socket && this.socket.readyState === WebSocket.OPEN) {
      this.socket.send(JSON.stringify(data));
    }
  }

  public getStatus(): CoreStatus {
    return this.status;
  }

  private notifyListeners(event: CoreTelemetryEvent) {
    this.listeners.forEach((listener) => {
      try {
        listener(event);
      } catch (err) {
        console.error('WebSocket listener error:', err);
      }
    });
  }

  private startHeartbeat() {
    this.stopHeartbeat();
    this.pingInterval = window.setInterval(() => {
      this.send({ type: 'PING' });
    }, 15000);
  }

  private stopHeartbeat() {
    if (this.pingInterval) {
      clearInterval(this.pingInterval);
      this.pingInterval = null;
    }
  }
}

export const wsClient = new JarvisWebSocketClient();
