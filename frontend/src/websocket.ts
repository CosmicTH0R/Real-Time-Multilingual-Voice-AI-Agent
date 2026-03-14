/**
 * WebSocket client for Voice AI Agent.
 * Handles connection management and message routing.
 */

export type MessageHandler = (data: any) => void;

export class VoiceWebSocket {
  private ws: WebSocket | null = null;
  private sessionId: string = '';
  private handlers: Map<string, MessageHandler[]> = new Map();
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;

  constructor(private baseUrl: string = '') {
    if (!this.baseUrl) {
      const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      this.baseUrl = `${proto}//${window.location.host}`;
    }
  }

  async connect(sessionId: string): Promise<void> {
    this.sessionId = sessionId;
    return new Promise((resolve, reject) => {
      const url = `${this.baseUrl}/ws/voice/${sessionId}`;
      this.ws = new WebSocket(url);

      this.ws.onopen = () => {
        this.reconnectAttempts = 0;
        this.emit('connected', { sessionId });
        resolve();
      };

      this.ws.onmessage = (event) => {
        if (event.data instanceof Blob) {
          // Binary audio data from server
          event.data.arrayBuffer().then((buffer) => {
            this.emit('audio', buffer);
          });
        } else {
          // JSON control/transcript message
          try {
            const msg = JSON.parse(event.data);
            this.emit(msg.type || 'message', msg);
          } catch {
            console.warn('Failed to parse WS message:', event.data);
          }
        }
      };

      this.ws.onclose = (event) => {
        this.emit('disconnected', { code: event.code, reason: event.reason });
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
          this.reconnectAttempts++;
          setTimeout(() => this.connect(sessionId), 2000 * this.reconnectAttempts);
        }
      };

      this.ws.onerror = (error) => {
        this.emit('error', error);
        reject(error);
      };
    });
  }

  sendAudio(audioData: ArrayBuffer): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(audioData);
    }
  }

  sendText(text: string): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ type: 'text_input', text }));
    }
  }

  sendControl(action: string, data: Record<string, any> = {}): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ type: 'control', action, ...data }));
    }
  }

  on(event: string, handler: MessageHandler): void {
    if (!this.handlers.has(event)) {
      this.handlers.set(event, []);
    }
    this.handlers.get(event)!.push(handler);
  }

  private emit(event: string, data: any): void {
    const handlers = this.handlers.get(event) || [];
    handlers.forEach((h) => h(data));
  }

  disconnect(): void {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }

  get isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }
}
