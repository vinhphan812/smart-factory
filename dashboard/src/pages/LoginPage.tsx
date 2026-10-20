/**
 * Login page with operator authentication
 */

import { useState, type FormEvent } from 'react';
import { useNavigate, useLocation, type NavigateFunction, type Location } from 'react-router-dom';
import { useAuth } from '../store/authContext';
import { Button } from '../design-system';
import styles from './LoginPage.module.css';

interface LoginPageProps {
  // Optional props for customization
}

export function LoginPage(_props: LoginPageProps) {
  const navigate: NavigateFunction = useNavigate();
  const location: Location = useLocation();
  const { login, isLoading, error, clearError } = useAuth();

  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');

  // Where to redirect after login (default to overview)
  const from = (location.state as { from?: Location })?.from?.pathname || '/';

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();

    // Clear previous errors
    clearError();

    try {
      await login({ username, password });
      // Redirect to the page they tried to access or default to overview
      navigate(from, { replace: true });
    } catch {
      // Error is handled by the store
    }
  };

  return (
    <div className={styles.container}>
      <div className={styles.card}>
        <div className={styles.header}>
          <h1 className={styles.title}>Smart Factory</h1>
          <p className={styles.subtitle}>Operator Login</p>
        </div>

        <form onSubmit={handleSubmit} className={styles.form}>
          {error && (
            <div className={styles.error}>
              {error}
            </div>
          )}

          <div className={styles.field}>
            <label htmlFor="username" className={styles.label}>
              Username
            </label>
            <input
              id="username"
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className={styles.input}
              placeholder="Enter your username"
              required
              autoComplete="username"
              disabled={isLoading}
            />
          </div>

          <div className={styles.field}>
            <label htmlFor="password" className={styles.label}>
              Password
            </label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className={styles.input}
              placeholder="Enter your password"
              required
              autoComplete="current-password"
              disabled={isLoading}
            />
          </div>

          <Button
            type="submit"
            variant="primary"
            fullWidth
            isLoading={isLoading}
            disabled={isLoading}
          >
            {isLoading ? 'Signing in...' : 'Sign In'}
          </Button>
        </form>

        <div className={styles.footer}>
          <p className={styles.hint}>
            Use your operator credentials to access the dashboard.
          </p>
        </div>
      </div>
    </div>
  );
}

export default LoginPage;
