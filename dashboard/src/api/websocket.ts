/**
 * WebSocket Client for Smart Factory IoT Gateway
 *
 * Provides resilient WebSocket connection with:
 * - Automatic reconnection with exponential backoff
 * - Stale data detection
 * - Event deduplication
 * - Connection state management
 */

import type { CanonicalEvent, ConnectionState } from '../types/gateway';

// Default WebSocket URL
const DEFAULT_WS_URL = import.meta.env.VITE_GATEWAY_WS_URL || 'ws://localhost:8000';

/** Initial reconnection delay in ms */
const INITIAL_RECONNECT_DELAY = 1000;
/** Maximum reconnection delay in ms */
const MAX_RECONNECT_DELAY = 30000;
/** Multiplier for exponential backoff */
const RECONNECT_MULTIPLIER = 2;
/** Jitter factor (0-1) to prevent thundering herd */
const JITTER_FACTOR = 0.3;
/** Time in ms after which data is considered stale */
const STALE_THRESHOLD_MS = 30000;

/** WebSocket message types */
export type WsMessageType = 'event' | 'ping' | 'pong' | 'snapshot_sync';

/** Incoming WebSocket message */
export interface WsIncomingMessage {
  type: WsMessageType;
  payload: CanonicalEvent | null;
}

/** Callback types for WebSocket events */
export interface WsCallbacks {
  onEvent: (event: CanonicalEvent) => void;
  onConnectionStateChange: (state: ConnectionState) => void;
  onError: (error: Error) => void;
  onStaleData: () => void;
}

/**
 * Calculate reconnection delay with exponential backoff and jitter
 */
function calculateReconnectDelay(attempt: number): number {
  const exponentialDelay = Math.min(
    INITIAL_RECONNECT_DELAY * Math.pow(RECONNECT_MULTIPLIER, attempt),
    MAX_RECONNECT_DELAY
  );
  const jitter = exponentialDelay * JITTER_FACTOR * Math.random();
  return exponentialDelay + jitter;
}

/**
 * Check if data is stale based on last update time
 */
function isDataStale(lastUpdateMs: number): boolean {
  return Date.now() - lastUpdateMs > STALE_THRESHOLD_MS;
}

/**
 * Resilient WebSocket client for the Smart Factory IoT Gateway
 */
export class GatewayWebSocketClient {
  private ws: WebSocket | null = null;
  private readonly url: string;
  private callbacks: WsCallbacks | null = null;

  // Connection state
  private connectionState: ConnectionState = 'disconnected';
  private reconnectAttempt = 0;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private pingTimer: ReturnType<typeof setInterval> | null = null;
  private lastMessageTime = 0;

  // Sequence tracking for deduplication
  private lastSequence = 0;
  private seenEventIds = new Set<string>();

  constructor(url: string = DEFAULT_WS_URL) {
    this.url = url;
  }

  /**
   * Connect to the WebSocket server
   */
  connect(callbacks: WsCallbacks): void {
    this.callbacks = callbacks;
    this.doConnect();
  }

  /**
   * Internal connect logic
   */
  private doConnect(): void {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }

    this.setConnectionState('connecting');

    try {
      this.ws = new WebSocket(this.url);
      this.setupEventHandlers();
    } catch (error) {
      this.handleConnectionError(error as Error);
    }
  }

  /**
   * Set up WebSocket event handlers
   */
  private setupEventHandlers(): void {
    if (!this.ws) return;

    this.ws.onopen = () => {
      this.reconnectAttempt = 0;
      this.lastMessageTime = Date.now();
      this.setConnectionState('connected');
      this.startPingTimer();
    };

    this.ws.onmessage = (event: MessageEvent) => {
      this.lastMessageTime = Date.now();
      this.handleMessage(event.data);
    };

    this.ws.onerror = () => {
      this.callbacks?.onError(new Error('WebSocket error'));
    };

    this.ws.onclose = (event: CloseEvent) => {
      this.stopPingTimer();
      this.setConnectionState('disconnected');

      // Don't reconnect on clean close
      if (event.code === 1000) {
        return;
      }

      this.scheduleReconnect();
    };
  }

  /**
   * Handle incoming WebSocket message
   */
  private handleMessage(data: string): void {
    try {
      const message = JSON.parse(data) as CanonicalEvent;

      // Deduplicate by event_id
      if (message.event_id && this.seenEventIds.has(message.event_id)) {
        return;
      }

      // Track sequence for ordering
      if (message.sequence > this.lastSequence) {
        this.lastSequence = message.sequence;
      }

      // Store event_id for deduplication
      if (message.event_id) {
        this.seenEventIds.add(message.event_id);
        // Limit storage size
        if (this.seenEventIds.size > 10000) {
          const entries = Array.from(this.seenEventIds);
          this.seenEventIds = new Set(entries.slice(-5000));
        }
      }

      // Check for stale data
      if (isDataStale(this.lastMessageTime)) {
        this.callbacks?.onStaleData();
      }

      // Notify callback
      this.callbacks?.onEvent(message);
    } catch (error) {
      console.warn('Failed to parse WebSocket message:', error);
    }
  }

  /**
   * Schedule a reconnection attempt with backoff
   */
  private scheduleReconnect(): void {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
    }

    const delay = calculateReconnectDelay(this.reconnectAttempt);
    this.reconnectAttempt++;

    this.reconnectTimer = setTimeout(() => {
      if (this.callbacks) {
        this.doConnect();
      }
    }, delay);
  }

  /**
   * Handle connection error
   */
  private handleConnectionError(error: Error): void {
    this.setConnectionState('error');
    this.callbacks?.onError(error);
    this.scheduleReconnect();
  }

  /**
   * Set connection state and notify callback
   */
  private setConnectionState(state: ConnectionState): void {
    if (this.connectionState !== state) {
      this.connectionState = state;
      this.callbacks?.onConnectionStateChange(state);
    }
  }

  /**
   * Start ping timer for connection health check
   */
  private startPingTimer(): void {
    this.stopPingTimer();

    // Send ping every 30 seconds
    this.pingTimer = setInterval(() => {
      if (this.ws?.readyState === WebSocket.OPEN) {
        // Check if we haven't received data for a while
        if (isDataStale(this.lastMessageTime)) {
          this.callbacks?.onStaleData();
        }
        // Optional: send ping frame if needed
      }
    }, 30000);
  }

  /**
   * Stop ping timer
   */
  private stopPingTimer(): void {
    if (this.pingTimer) {
      clearInterval(this.pingTimer);
      this.pingTimer = null;
    }
  }

  /**
   * Disconnect from WebSocket server
   */
  disconnect(): void {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }

    this.stopPingTimer();

    if (this.ws) {
      this.ws.close(1000, 'Client disconnect');
      this.ws = null;
    }

    this.setConnectionState('disconnected');
  }

  /**
   * Get current connection state
   */
  getConnectionState(): ConnectionState {
    return this.connectionState;
  }

  /**
   * Get last known sequence number
   */
  getLastSequence(): number {
    return this.lastSequence;
  }

  /**
   * Reset sequence tracking (for full resync)
   */
  resetSequence(): void {
    this.lastSequence = 0;
    this.seenEventIds.clear();
  }

  /**
   * Check if connection is healthy
   */
  isConnected(): boolean {
    return this.connectionState === 'connected' && this.ws?.readyState === WebSocket.OPEN;
  }
}

// Singleton instance for convenience
export const gatewayWsClient = new GatewayWebSocketClient();
