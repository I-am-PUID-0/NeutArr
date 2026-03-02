/**
 * NeutArr Auth Manager
 *
 * Handles JWT token storage, Authorization header injection, automatic token
 * refresh on 401, and logout. Include this before all other JS files.
 *
 * Token storage:
 *   - Access token: localStorage (neutarr_access_token) + neutarr_token cookie
 *     (cookie is set by server on login/refresh for browser page-request auth)
 *   - Refresh token: localStorage (neutarr_refresh_token) for explicit refresh calls
 *
 * Usage:
 *   authFetch('/api/something', { method: 'POST', body: JSON.stringify(data) })
 *     .then(r => r.json())
 *
 *   AuthManager.logout()
 *   AuthManager.getUsername()
 */

const AuthManager = (() => {
  const ACCESS_KEY = 'neutarr_access_token';
  const REFRESH_KEY = 'neutarr_refresh_token';
  const USERNAME_KEY = 'neutarr_username';

  let _refreshPromise = null; // Deduplicates concurrent refresh attempts

  function getAccessToken() {
    return localStorage.getItem(ACCESS_KEY);
  }

  function getRefreshToken() {
    return localStorage.getItem(REFRESH_KEY);
  }

  function getUsername() {
    return localStorage.getItem(USERNAME_KEY);
  }

  function setTokens(accessToken, refreshToken, username) {
    if (accessToken) localStorage.setItem(ACCESS_KEY, accessToken);
    if (refreshToken) localStorage.setItem(REFRESH_KEY, refreshToken);
    if (username) localStorage.setItem(USERNAME_KEY, username);
  }

  function clearTokens() {
    localStorage.removeItem(ACCESS_KEY);
    localStorage.removeItem(REFRESH_KEY);
    localStorage.removeItem(USERNAME_KEY);
  }

  async function refresh() {
    // Deduplicate: if a refresh is already in flight, return the same promise
    if (_refreshPromise) return _refreshPromise;

    const refreshToken = getRefreshToken();
    if (!refreshToken) return false;

    _refreshPromise = (async () => {
      try {
        const response = await fetch('/api/auth/refresh', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ refresh_token: refreshToken }),
        });

        if (!response.ok) {
          clearTokens();
          return false;
        }

        const data = await response.json();
        setTokens(data.access_token, data.refresh_token, data.username);
        return true;
      } catch {
        return false;
      } finally {
        _refreshPromise = null;
      }
    })();

    return _refreshPromise;
  }

  async function logout() {
    try {
      await fetch('/api/auth/logout', { method: 'POST' });
    } catch { /* ignore network errors on logout */ }
    clearTokens();
    window.location.href = '/login';
  }

  return { getAccessToken, getRefreshToken, getUsername, setTokens, clearTokens, refresh, logout };
})();


/**
 * authFetch — drop-in replacement for fetch() that:
 *   1. Adds Authorization: Bearer <token> header
 *   2. On 401: tries one token refresh then retries
 *   3. On second 401: redirects to /login
 *
 * @param {string} url
 * @param {RequestInit} [options]
 * @returns {Promise<Response>}
 */
async function authFetch(url, options = {}) {
  const token = AuthManager.getAccessToken();

  const headers = new Headers(options.headers || {});
  if (!headers.has('Content-Type') && !(options.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json');
  }
  if (token) {
    headers.set('Authorization', `Bearer ${token}`);
  }

  let response = await fetch(url, { ...options, headers });

  // On 401, attempt token refresh then retry once
  if (response.status === 401) {
    const refreshed = await AuthManager.refresh();
    if (refreshed) {
      const newToken = AuthManager.getAccessToken();
      if (newToken) headers.set('Authorization', `Bearer ${newToken}`);
      response = await fetch(url, { ...options, headers });
    }

    // Still 401 after refresh — redirect to login
    if (response.status === 401) {
      AuthManager.logout();
      return response; // unreachable but satisfies linters
    }
  }

  return response;
}
