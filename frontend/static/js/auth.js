/**
 * NeutArr Auth Manager
 *
 * Handles the browser's HttpOnly cookie session, automatic token refresh on
 * 401, and logout. Include this before all other JS files.
 *
 * Token storage:
 *   - Access and refresh JWTs: HttpOnly cookies managed by the server
 *   - Username only: localStorage, scoped per NeutArr instance
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

  let _refreshPromise = null; // Deduplicates concurrent refresh attempts
  let _bootstrapPromise = null;
  let _bypassActive = false;
  let _legacyTokenMigrationPending = false;

  function getUsername() {
    return localStorage.getItem(USERNAME_KEY);
  }

  function clearLegacyBrowserTokens() {
    for (const key of [ACCESS_KEY, REFRESH_KEY, 'neutarr_access_token', 'neutarr_refresh_token']) {
      if (localStorage.getItem(key)) {
        _legacyTokenMigrationPending = true;
      }
      localStorage.removeItem(key);
    }
  }

  function setSession(username) {
    clearLegacyBrowserTokens();
    if (username) localStorage.setItem(USERNAME_KEY, username);
  }

  function clearSession() {
    clearLegacyBrowserTokens();
    localStorage.removeItem(USERNAME_KEY);
    _bypassActive = false;
  }

  async function bootstrap() {
    if (_bootstrapPromise) return _bootstrapPromise; // In-flight request

    _bootstrapPromise = (async () => {
      try {
        const response = await nativeFetch('/api/auth/status');
        if (!response.ok) return false;

        const data = await response.json();
        if (data.instance_storage_key && data.instance_storage_key !== storageNamespace) {
          return false;
        }
        _bypassActive = Boolean(data.proxy_request_authenticated || data.local_client_bypass);
        if (_legacyTokenMigrationPending) {
          _legacyTokenMigrationPending = false;
          await refresh();
        }
        return _bypassActive;
      } catch {
        _bypassActive = false;
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

    _refreshPromise = (async () => {
      try {
        const response = await nativeFetch('/api/auth/refresh', {
          method: 'POST',
        });

        if (!response.ok) {
          return false;
        }

        const data = await response.json();
        setSession(data.username);
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
      await nativeFetch('/api/auth/logout', { method: 'POST' });
    } catch { /* ignore network errors on logout */ }
    clearSession();
    if (bootstrapped) {
      window.location.href = '/';
      return;
    }
    window.location.href = '/login';
  }

  function isBypassActive() {
    return _bypassActive;
  }

  clearLegacyBrowserTokens();

  return { getUsername, setSession, clearSession, bootstrap, refresh, logout, isBypassActive };
})();


/**
 * authFetch — drop-in replacement for fetch() that adds a JSON content type
 * when appropriate. The global fetch wrapper handles cookie refresh.
 *
 * @param {string} url
 * @param {RequestInit} [options]
 * @returns {Promise<Response>}
 */
async function authFetch(url, options = {}) {
  const headers = new Headers(options.headers || {});
  if (!headers.has('Content-Type') && !(options.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json');
  }
  return window.fetch(url, { ...options, headers });
}

function getSameOriginApiPath(input) {
  const url = typeof input === 'string' ? input : input instanceof Request ? input.url : String(input);

  if (/^https?:\/\//i.test(url)) {
    try {
      const parsed = new URL(url, window.location.origin);
      if (parsed.origin !== window.location.origin || !parsed.pathname.startsWith('/api/')) return null;
      return parsed.pathname;
    } catch {
      return null;
    }
  }

  if (!url.startsWith('/api/')) return null;
  return new URL(url, window.location.origin).pathname;
}

window.fetch = async function(input, init = undefined) {
  const apiPath = getSameOriginApiPath(input);
  if (!apiPath) {
    return nativeFetch(input, init);
  }

  await AuthManager.bootstrap();

  const originalRequest = input instanceof Request ? input : null;
  const retryInput = originalRequest ? originalRequest.clone() : input;
  let response = await nativeFetch(input, init);

  const refreshExcluded = new Set([
    '/api/auth/login',
    '/api/auth/logout',
    '/api/auth/refresh',
    '/api/auth/setup',
    '/api/auth/status',
    '/api/auth/verify',
  ]);
  if (
    response.status !== 401 ||
    response.headers.get('X-NeutArr-Auth-Required') !== '1' ||
    refreshExcluded.has(apiPath) ||
    AuthManager.isBypassActive()
  ) {
    return response;
  }

  if (await AuthManager.refresh()) {
    response = await nativeFetch(retryInput, init);
  }

  if (response.status === 401) {
    AuthManager.logout();
  }
  return response;
};
