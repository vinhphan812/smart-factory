/**
 * Auth context and provider for session management with refresh token pattern
 */

import React, { createContext, useContext, useState, useEffect, useCallback, ReactNode } from 'react';
import { gatewayApi } from '../services/api/client';
import type { AuthUser, AuthTokens, LoginCredentials, PermissionScope } from '../contracts/gateway';
import { ROLE_PERMISSIONS } from '../contracts/gateway';

interface AuthContextType {
  user: AuthUser | null;
  tokens: AuthTokens | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;
  login: (credentials: LoginCredentials) => Promise<void>;
  logout: () => Promise<void>;
  refreshSession: () => Promise<void>;
  clearError: () => void;
  hasPermission: (permission: PermissionScope) => boolean;
  getAccessToken: () => string | null;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

// Token refresh buffer time (refresh 1 minute before expiry)
const REFRESH_BUFFER_SECONDS = 60;

// Local storage keys
const AUTH_STORAGE_KEY = 'smart-factory-auth';

interface StoredAuth {
  user: AuthUser;
  tokens: AuthTokens;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [tokens, setTokens] = useState<AuthTokens | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [refreshTimer, setRefreshTimer] = useState<ReturnType<typeof setTimeout> | null>(null);

  // Load persisted auth on mount
  useEffect(() => {
    try {
      const stored = localStorage.getItem(AUTH_STORAGE_KEY);
      if (stored) {
        const auth: StoredAuth = JSON.parse(stored);
        setUser(auth.user);
        setTokens(auth.tokens);

        // Schedule token refresh
        const timeUntilRefresh = (auth.tokens.expires_in - REFRESH_BUFFER_SECONDS) * 1000;
        if (timeUntilRefresh > 0) {
          const timer = setTimeout(() => {
            refreshSession();
          }, timeUntilRefresh);
          setRefreshTimer(timer);
        }
      }
    } catch {
      // Ignore parse errors
    }
  }, []);

  // Persist auth to localStorage
  useEffect(() => {
    if (user && tokens) {
      localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify({ user, tokens }));
    } else {
      localStorage.removeItem(AUTH_STORAGE_KEY);
    }
  }, [user, tokens]);

  // Cleanup timer on unmount
  useEffect(() => {
    return () => {
      if (refreshTimer) {
        clearTimeout(refreshTimer);
      }
    };
  }, [refreshTimer]);

  const scheduleRefresh = useCallback((newTokens: AuthTokens) => {
    if (refreshTimer) {
      clearTimeout(refreshTimer);
    }

    const timeUntilRefresh = (newTokens.expires_in - REFRESH_BUFFER_SECONDS) * 1000;
    if (timeUntilRefresh > 0) {
      const timer = setTimeout(() => {
        refreshSession();
      }, timeUntilRefresh);
      setRefreshTimer(timer);
    }
  }, [refreshTimer]);

  const login = async (credentials: LoginCredentials) => {
    setIsLoading(true);
    setError(null);

    try {
      const response = await gatewayApi.login(credentials);
      const { user: newUser, tokens: newTokens } = response;

      setUser(newUser);
      setTokens(newTokens);
      scheduleRefresh(newTokens);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Login failed';
      setError(message);
      throw err;
    } finally {
      setIsLoading(false);
    }
  };

  const logout = async () => {
    if (refreshTimer) {
      clearTimeout(refreshTimer);
      setRefreshTimer(null);
    }

    // Attempt to invalidate refresh token (ignore errors)
    try {
      if (tokens?.refresh_token) {
        await gatewayApi.logout(tokens.refresh_token);
      }
    } catch {
      // Ignore logout errors - local state cleanup is more important
    }

    setUser(null);
    setTokens(null);
    setIsLoading(false);
    setError(null);
  };

  const refreshSession = async () => {
    if (!tokens?.refresh_token) {
      await logout();
      return;
    }

    setIsLoading(true);

    try {
      const newTokens = await gatewayApi.refreshToken({
        refresh_token: tokens.refresh_token,
      });

      setTokens(newTokens);
      scheduleRefresh(newTokens);
    } catch (error) {
      console.error('Token refresh failed:', error);
      await logout();
    } finally {
      setIsLoading(false);
    }
  };

  const clearError = () => setError(null);

  const hasPermission = (permission: PermissionScope): boolean => {
    if (!user) {
      return false;
    }
    return user.permissions.includes(permission);
  };

  const getAccessToken = (): string | null => {
    return tokens?.access_token || null;
  };

  const value: AuthContextType = {
    user,
    tokens,
    isAuthenticated: !!user && !!tokens,
    isLoading,
    error,
    login,
    logout,
    refreshSession,
    clearError,
    hasPermission,
    getAccessToken,
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextType {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}

// Helper function to check permissions based on role
export function checkRolePermission(
  role: string,
  permission: PermissionScope
): boolean {
  return (ROLE_PERMISSIONS as Record<string, PermissionScope[]>)[role]?.includes(permission) ?? false;
}
