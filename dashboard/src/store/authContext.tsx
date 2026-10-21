/**
 * Auth context and provider for session management with httpOnly cookies
 *
 * SECURITY: This implementation uses httpOnly cookies for token storage instead of
 * localStorage. Tokens are:
 * - Not accessible to JavaScript (prevents XSS token theft)
 * - Automatically sent with requests (credentials: 'include')
 * - Protected by SameSite=strict CSRF mitigation
 *
 * Residual limitations:
 * - Requires same-origin API or proper CORS with credentials support
 * - Session-based (no "remember me" functionality)
 * - Tokens cleared on browser close (session cookies)
 * - Cannot be used with separate domain APIs without proper CORS
 */

import React, { createContext, useContext, useState, useEffect, useCallback, ReactNode } from 'react';
import { gatewayApi } from '../services/api/client';
import type { AuthUser, LoginCredentials } from '../contracts/gateway';
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
  hasPermission: (permission: string) => boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

// Refresh token stored in memory (not localStorage for security)
let refreshToken: string | null = null;

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [isLoading, setIsLoading] = useState(true); // Start true to check session on mount
  const [error, setError] = useState<string | null>(null);

  // Check for existing session on mount via API call
  // This works because cookies are automatically sent with requests
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

  const login = async (credentials: LoginCredentials) => {
    setIsLoading(true);
    setError(null);

    try {
      const response = await gatewayApi.login(credentials);
      const { user: newUser, tokens } = response;

      // Store refresh token in memory (NOT localStorage)
      refreshToken = tokens.refresh_token;

      setUser(newUser);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Login failed';
      setError(message);
      throw err;
    } finally {
      setIsLoading(false);
    }
  };

  const logout = async () => {
    // Attempt to invalidate refresh token (ignore errors)
    try {
      if (refreshToken) {
        await gatewayApi.logout(refreshToken);
      }
    } catch {
      // Ignore logout errors - local state cleanup is more important
    }

    // Clear in-memory token
    refreshToken = null;
    setUser(null);
    setIsLoading(false);
    setError(null);
  };

  const refreshSession = async () => {
    if (!refreshToken) {
      await logout();
      return;
    }

    setIsLoading(true);

    try {
      const newTokens = await gatewayApi.refreshToken({
        refresh_token: refreshToken,
      });

      // Update in-memory refresh token
      refreshToken = newTokens.refresh_token;

      // Refresh user info since access token changed
      const currentUser = await gatewayApi.getCurrentUser();
      setUser(currentUser);
    } catch (error) {
      console.error('Token refresh failed:', error);
      await logout();
    } finally {
      setIsLoading(false);
    }
  };

  const clearError = () => setError(null);

  const hasPermission = (permission: string): boolean => {
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
  permission: string
): boolean {
  return (ROLE_PERMISSIONS as Record<string, string[]>)[role]?.includes(permission) ?? false;
}
