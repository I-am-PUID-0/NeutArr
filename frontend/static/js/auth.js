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

const nativeFetch = window.fetch.bind(window);
const storageNamespace = window.NEUTARR_INSTANCE_STORAGE_KEY || 'inst_default';

function scopedStorageKey(baseKey) {
  return `${baseKey}_${storageNamespace}`;
}

const AuthManager = (() => {
  const ACCESS_KEY = scopedStorageKey('neutarr_access_token');
  const REFRESH_KEY = scopedStorageKey('neutarr_refresh_token');
  const USERNAME_KEY = scopedStorageKey('neutarr_username');
  const API_KEY = scopedStorageKey('neutarr_api_key');

  let _refreshPromise = null; // Deduplicates concurrent refresh attempts
  let _bootstrapPromise = null;
  let _apiKey = null;

  function getAccessToken() {
    return localStorage.getItem(ACCESS_KEY);
  }

  function getRefreshToken() {
    return localStorage.getItem(REFRESH_KEY);
  }

  function getUsername() {
    return localStorage.getItem(USERNAME_KEY);
  }

  function getApiKey() {
    return _apiKey;
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
    localStorage.removeItem(API_KEY);
    _apiKey = null;
  }

  function setApiKey(apiKey) {
    if (apiKey) {
      _apiKey = apiKey;
    } else {
      localStorage.removeItem(API_KEY);
      _apiKey = null;
    }
  }

  async function bootstrap() {
    if (_bootstrapPromise) return _bootstrapPromise;

    _bootstrapPromise = (async () => {
      try {
        const response = await nativeFetch('/api/auth/status');
        if (!response.ok) return false;

        const data = await response.json();
        if (data.instance_storage_key && data.instance_storage_key !== storageNamespace) {
          return false;
        }
        if (data.frontend_api_key) {
          setApiKey(data.frontend_api_key);
          return true;
        }

        setApiKey(null);
        return false;
      } catch {
        return false;
      } finally {
        _bootstrapPromise = null;
      }
    })();

    return _bootstrapPromise;
  }

  async function refresh() {
    // Deduplicate: if a refresh is already in flight, return the same promise
    if (_refreshPromise) return _refreshPromise;

    const refreshToken = getRefreshToken();
    if (!refreshToken) return false;

    _refreshPromise = (async () => {
      try {
      const response = await nativeFetch('/api/auth/refresh', {
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
    const bootstrapped = await bootstrap();
    try {
      const headers = {};
      if (bootstrapped) {
        const apiKey = getApiKey();
        if (apiKey) headers['X-Api-Key'] = apiKey;
      }
      await nativeFetch('/api/auth/logout', { method: 'POST', headers });
    } catch { /* ignore network errors on logout */ }
    clearTokens();
    if (bootstrapped) {
      window.location.href = '/';
      return;
    }
    window.location.href = '/login';
  }

  return { getAccessToken, getRefreshToken, getUsername, getApiKey, setTokens, clearTokens, setApiKey, bootstrap, refresh, logout };
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
  await AuthManager.bootstrap();

  const token = AuthManager.getAccessToken();
  const apiKey = AuthManager.getApiKey();

  const headers = new Headers(options.headers || {});
  if (!headers.has('Content-Type') && !(options.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json');
  }
  if (token) {
    headers.set('Authorization', `Bearer ${token}`);
  } else if (apiKey) {
    headers.set('X-Api-Key', apiKey);
  }

  let response = await nativeFetch(url, { ...options, headers });

  // On 401, attempt token refresh then retry once
  if (response.status === 401 && token) {
    const refreshed = await AuthManager.refresh();
    if (refreshed) {
      const newToken = AuthManager.getAccessToken();
      if (newToken) headers.set('Authorization', `Bearer ${newToken}`);
      response = await nativeFetch(url, { ...options, headers });
    }

    // Still 401 after refresh — redirect to login
    if (response.status === 401) {
      AuthManager.logout();
      return response; // unreachable but satisfies linters
    }
  }

  return response;
}

function shouldAttachApiAuth(input) {
  const url = typeof input === 'string' ? input : input instanceof Request ? input.url : String(input);

  if (/^https?:\/\//i.test(url)) {
    try {
      const parsed = new URL(url, window.location.origin);
      if (parsed.origin !== window.location.origin) return false;
      return parsed.pathname.startsWith('/api/');
    } catch {
      return false;
    }
  }

  return url.startsWith('/api/');
}

window.fetch = async function(input, init = undefined) {
  if (!shouldAttachApiAuth(input)) {
    return nativeFetch(input, init);
  }

  await AuthManager.bootstrap();

  const originalRequest = input instanceof Request ? input : null;
  const requestInit = init ? { ...init } : {};
  const headers = new Headers(
    requestInit.headers || (originalRequest ? originalRequest.headers : undefined) || undefined
  );

  const token = AuthManager.getAccessToken();
  const apiKey = AuthManager.getApiKey();

  if (token && !headers.has('Authorization')) {
    headers.set('Authorization', `Bearer ${token}`);
  } else if (apiKey && !headers.has('X-Api-Key')) {
    headers.set('X-Api-Key', apiKey);
  }

  requestInit.headers = headers;

  if (originalRequest) {
    return nativeFetch(new Request(originalRequest, requestInit));
  }

  return nativeFetch(input, requestInit);
};
