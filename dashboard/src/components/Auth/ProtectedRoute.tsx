/**
 * ProtectedRoute component with RBAC
 */

import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '../../store/authContext';
import type { PermissionScope } from '../../contracts/gateway';

interface ProtectedRouteProps {
  children: React.ReactNode;
  requiredPermission?: PermissionScope;
  fallbackPath?: string;
}

/**
 * Route wrapper that enforces authentication and optional permission checks
 */
export function ProtectedRoute({
  children,
  requiredPermission,
  fallbackPath = '/login',
}: ProtectedRouteProps) {
  const location = useLocation();
  const { isAuthenticated, hasPermission } = useAuth();

  // Not authenticated - redirect to login
  if (!isAuthenticated) {
    return <Navigate to={fallbackPath} state={{ from: location }} replace />;
  }

  // Check permission if required
  if (requiredPermission && !hasPermission(requiredPermission)) {
    // User is authenticated but lacks permission - show access denied
    return (
      <div className="access-denied">
        <h2>Access Denied</h2>
        <p>You don't have permission to access this resource.</p>
        <p>Required permission: {requiredPermission}</p>
      </div>
    );
  }

  return <>{children}</>;
}

export default ProtectedRoute;
