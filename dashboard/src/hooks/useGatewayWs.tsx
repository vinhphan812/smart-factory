/**
 * React context and hook for WebSocket connection to the gateway
 */

import React, { createContext, useContext, useEffect, useState, useCallback, useRef, ReactNode } from 'react';
import { GatewayWebSocketClient, createGatewayWebSocket } from '../services/ws/client';
import type { GatewayEvent, ConnectionStatus, GatewayConfig } from '../contracts/gateway';

interface GatewayWsContextValue {
  status: ConnectionStatus;
  events: GatewayEvent[];
  lastEvent: GatewayEvent | null;
  connect: () => void;
  disconnect: () => void;
  clearEvents: () => void;
}

const GatewayWsContext = createContext<GatewayWsContextValue | null>(null);

const DEFAULT_WS_URL = import.meta.env.VITE_GATEWAY_WS_URL || 'ws://localhost:8000';

interface GatewayWsProviderProps {
  children: ReactNode;
  config?: Partial<GatewayConfig>;
}

export function GatewayWsProvider({ children, config }: GatewayWsProviderProps) {
  const [status, setStatus] = useState<ConnectionStatus>('disconnected');
  const [events, setEvents] = useState<GatewayEvent[]>([]);
  const [lastEvent, setLastEvent] = useState<GatewayEvent | null>(null);
  const clientRef = useRef<GatewayWebSocketClient | null>(null);

  const handleMessage = useCallback((event: GatewayEvent) => {
    setEvents((prev) => {
      const updated = [event, ...prev];
      // Keep only last 200 events in memory
      return updated.slice(0, 200);
    });
    setLastEvent(event);
  }, []);

  const handleStatusChange = useCallback((newStatus: ConnectionStatus) => {
    setStatus(newStatus);
  }, []);

  const connect = useCallback(() => {
    if (!clientRef.current) {
      const wsUrl = config?.wsUrl || DEFAULT_WS_URL;
      clientRef.current = createGatewayWebSocket(
        wsUrl,
        handleMessage,
        handleStatusChange
      );
    }
    clientRef.current.connect();
  }, [config?.wsUrl, handleMessage, handleStatusChange]);

  const disconnect = useCallback(() => {
    if (clientRef.current) {
      clientRef.current.disconnect();
    }
  }, []);

  const clearEvents = useCallback(() => {
    setEvents([]);
    setLastEvent(null);
  }, []);

  useEffect(() => {
    return () => {
      if (clientRef.current) {
        clientRef.current.disconnect();
      }
    };
  }, []);

  const value: GatewayWsContextValue = {
    status,
    events,
    lastEvent,
    connect,
    disconnect,
    clearEvents,
  };

  return (
    <GatewayWsContext.Provider value={value}>
      {children}
    </GatewayWsContext.Provider>
  );
}

export function useGatewayWs(): GatewayWsContextValue {
  const context = useContext(GatewayWsContext);
  if (!context) {
    throw new Error('useGatewayWs must be used within a GatewayWsProvider');
  }
  return context;
}

export default useGatewayWs;
