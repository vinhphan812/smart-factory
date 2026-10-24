/**
 * Auth context and provider for session management with cookie-based auth
 * 
 * SECURITY: P0 - Token persistence removed
 * - No tokens stored in localStorage/sessionStorage
 * - Uses httpOnly cookies via credentials: 'include' for all API calls
 * - Session validated via /api/auth/me endpoint
 */

import React, { createContext, useContext, useState, useEffect, useCallback, ReactNode } from 'react';
import { gatewayApi } from '../services/api/client';
import type { AuthUser, LoginCredentials, PermissionScope } from '../contracts/gateway';
import { ROLE_PERMISSIONS } from '../contracts/gateway';

interface AuthContextType {
  user: AuthUser | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;
  login: (credentials: LoginCredentials) => Promise<void>;
  logout: () => Promise<void>;
  refreshSession: () => Promise<void>;
  clearError: () => void;
  hasPermission: (permission: PermissionScope) => boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshTimer, setRefreshTimer] = useState<ReturnType<typeof setTimeout> | null>(null);

  // Check for existing session on mount using /api/auth/me
  // This validates the httpOnly cookie-based session
  useEffect(() => {
    const checkSession = async () => {
      try {
        const currentUser = await gatewayApi.getCurrentUser();
        setUser(currentUser);
      } catch {
        // No valid session - user is not authenticated
        setUser(null);
      } finally {
        setIsLoading(false);
      }
    };
    
    checkSession();
  }, []);

  // Cleanup timer on unmount
  useEffect(() => {
    return () => {
      if (refreshTimer) {
        clearTimeout(refreshTimer);
      }
    };
  }, [refreshTimer]);

  const scheduleRefresh = useCallback(() => {
    // Schedule token refresh via cookie-based refresh endpoint
    // Refresh 5 minutes before the 30-minute access token expires
    if (refreshTimer) {
      clearTimeout(refreshTimer);
    }

    // Refresh every 25 minutes (5 minutes before 30-minute expiry)
    const refreshInterval = 25 * 60 * 1000;
    const timer = setTimeout(() => {
      refreshSession();
    }, refreshInterval);
    setRefreshTimer(timer);
  }, [refreshTimer]);

  const login = async (credentials: LoginCredentials) => {
    setIsLoading(true);
    setError(null);

    try {
      // Login sets httpOnly cookies via response
      // We still call it to get user info and establish session
      const userInfo = await gatewayApi.login(credentials);
      
      setUser(userInfo.user);
      
      // Schedule token refresh
      scheduleRefresh();
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

    // Attempt to invalidate session (ignore errors)
    try {
      await gatewayApi.logout();
    } catch {
      // Ignore logout errors - local state cleanup is more important
    }

    setUser(null);
    setIsLoading(false);
    setError(null);
  };

  const refreshSession = async () => {
    setIsLoading(true);

    try {
      // Refresh via cookie - this updates the httpOnly cookies
      await gatewayApi.refreshToken();
      
      // Re-fetch user info to verify session is still valid
      const currentUser = await gatewayApi.getCurrentUser();
      setUser(currentUser);
      
      // Schedule next refresh
      scheduleRefresh();
    } catch (error) {
      console.error('Session refresh failed:', error);
      // Session is invalid - clear state
      setUser(null);
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

  const value: AuthContextType = {
    user,
    isAuthenticated: !!user,
    isLoading,
    error,
    login,
    logout,
    refreshSession,
    clearError,
    hasPermission,
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
