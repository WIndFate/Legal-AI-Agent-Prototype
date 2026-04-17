const ACCESS_TOKEN_KEY_PREFIX = 'order-access-token:';
const OWNER_TOKEN_HEADER = 'X-Order-Token';

export function getStoredOrderAccessToken(orderId: string | null | undefined): string | null {
  if (!orderId || typeof window === 'undefined') return null;
  return sessionStorage.getItem(`${ACCESS_TOKEN_KEY_PREFIX}${orderId}`);
}

export function storeOrderAccessToken(orderId: string | null | undefined, token: string | null | undefined): void {
  if (!orderId || !token || typeof window === 'undefined') return;
  sessionStorage.setItem(`${ACCESS_TOKEN_KEY_PREFIX}${orderId}`, token);
}

function parseHashToken(hash: string): string | null {
  if (!hash) return null;
  const trimmed = hash.startsWith('#') ? hash.slice(1) : hash;
  if (!trimmed) return null;
  const params = new URLSearchParams(trimmed);
  const token = params.get('t');
  return token ? token : null;
}

function stripTokenFromUrl(): void {
  if (typeof window === 'undefined' || !window.history?.replaceState) return;
  const url = new URL(window.location.href);
  // Remove legacy owner-token query params while preserving legitimate routing
  // params such as `lang`, `ref`, `s`, and `dev_payment`.
  url.searchParams.delete('token');
  // Always drop the fragment after reading `#t=` so owner tokens do not linger
  // in the address bar, browser history, or copy-pasted URLs.
  url.hash = '';
  const nextUrl = `${url.pathname}${url.search}`;
  window.history.replaceState(null, '', nextUrl);
}

export function resolveOrderAccessToken(
  orderId: string | null | undefined,
  searchParams: URLSearchParams,
): string | null {
  if (typeof window === 'undefined') {
    return getStoredOrderAccessToken(orderId);
  }
  // Preferred entry: URL fragment `#t=<token>` (never hits the server access log).
  const hashToken = parseHashToken(window.location.hash);
  if (hashToken) {
    storeOrderAccessToken(orderId, hashToken);
    stripTokenFromUrl();
    return hashToken;
  }
  // Fallback: `?token=` query (kept for manual pastes). Strip immediately after read.
  const queryToken = searchParams.get('token');
  if (queryToken) {
    storeOrderAccessToken(orderId, queryToken);
    stripTokenFromUrl();
    return queryToken;
  }
  return getStoredOrderAccessToken(orderId);
}

export function ownerHeaders(token: string | null | undefined): Record<string, string> {
  return token ? { [OWNER_TOKEN_HEADER]: token } : {};
}

export function withOwnerHeaders(
  token: string | null | undefined,
  init?: RequestInit,
): RequestInit {
  if (!token) return init ?? {};
  const merged = new Headers(init?.headers);
  merged.set(OWNER_TOKEN_HEADER, token);
  return { ...(init ?? {}), headers: merged };
}

export function buildShareUrl(orderId: string, shareToken: string): string {
  if (typeof window === 'undefined') {
    return `/report/${orderId}?s=${encodeURIComponent(shareToken)}`;
  }
  const url = new URL(`/report/${orderId}`, window.location.origin);
  url.searchParams.set('s', shareToken);
  return url.toString();
}
