/**
 * WebSocket client for the Smart Factory Gateway
 * 
 * SECURITY: READ-ONLY. No MQTT publish. Browser never initiates physical actuation.
 * This client only subscribes to telemetry and event streams from the gateway.
 * It never sends commands to the physical devices.
 */

import type { GatewayEvent, ConnectionStatus } from '../../contracts/gateway';

export type MessageHandler = (event: GatewayEvent) => void;
export type StatusHandler = (status: ConnectionStatus) => void;

export interface WebSocketClientOptions {
  url: string;
  onMessage: MessageHandler;
  onStatusChange: StatusHandler;
  reconnectInterval?: number;
  maxReconnectAttempts?: number;
}

export class GatewayWebSocketClient {
  private ws: WebSocket | null = null;
  private url: string;
  private onMessage: MessageHandler;
  private onStatusChange: StatusHandler;
  private reconnectInterval: number;
  private maxReconnectAttempts: number;
  private reconnectAttempts = 0;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private isIntentionallyClosed = false;

  constructor(options: WebSocketClientOptions) {
    this.url = options.url;
    this.onMessage = options.onMessage;
    this.onStatusChange = options.onStatusChange;
    this.reconnectInterval = options.reconnectInterval ?? 5000;
    this.maxReconnectAttempts = options.maxReconnectAttempts ?? 10;
  }

  /**
   * Connect to the gateway WebSocket
   */
  connect(): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      return;
    }

    this.isIntentionallyClosed = false;
    this.onStatusChange('connecting');

    try {
      this.ws = new WebSocket(this.url);

      this.ws.onopen = () => {
        this.reconnectAttempts = 0;
        this.onStatusChange('connected');
      };

      this.ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data) as GatewayEvent;
          this.onMessage(data);
        } catch (error) {
          console.error('Failed to parse WebSocket message:', error);
        }
      };

      this.ws.onerror = () => {
        this.onStatusChange('error');
      };

      this.ws.onclose = () => {
        if (!this.isIntentionallyClosed) {
          this.onStatusChange('disconnected');
          this.scheduleReconnect();
        }
      };
    } catch (error) {
      console.error('Failed to create WebSocket:', error);
      this.onStatusChange('error');
      this.scheduleReconnect();
    }
  }

  /**
   * Disconnect from the gateway
   */
  disconnect(): void {
    this.isIntentionallyClosed = true;
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    this.onStatusChange('disconnected');
  }

  /**
   * Schedule a reconnection attempt
   */
  private scheduleReconnect(): void {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.error('Max reconnection attempts reached');
      return;
    }

    this.reconnectAttempts++;
    const delay = this.reconnectInterval * Math.pow(1.5, this.reconnectAttempts - 1);
    
    this.reconnectTimer = setTimeout(() => {
      this.connect();
    }, delay);
  }

  /**
   * Get the current connection status
   */
  getStatus(): ConnectionStatus {
    if (!this.ws) return 'disconnected';
    switch (this.ws.readyState) {
      case WebSocket.CONNECTING:
        return 'connecting';
      case WebSocket.OPEN:
        return 'connected';
      case WebSocket.CLOSING:
      case WebSocket.CLOSED:
        return 'disconnected';
      default:
        return 'disconnected';
    }
  }
}

/**
 * Factory function to create a WebSocket client
 */
export function createGatewayWebSocket(
  url: string,
  onMessage: MessageHandler,
  onStatusChange: StatusHandler
): GatewayWebSocketClient {
  return new GatewayWebSocketClient({
    url,
    onMessage,
    onStatusChange,
  });
}
