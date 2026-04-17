const ACCESS_TOKEN_KEY_PREFIX = 'order-access-token:';

export function getStoredOrderAccessToken(orderId: string | null | undefined): string | null {
  if (!orderId || typeof window === 'undefined') return null;
  return sessionStorage.getItem(`${ACCESS_TOKEN_KEY_PREFIX}${orderId}`);
}

export function storeOrderAccessToken(orderId: string | null | undefined, token: string | null | undefined): void {
  if (!orderId || !token || typeof window === 'undefined') return;
  sessionStorage.setItem(`${ACCESS_TOKEN_KEY_PREFIX}${orderId}`, token);
}

export function resolveOrderAccessToken(
  orderId: string | null | undefined,
  searchParams: URLSearchParams,
): string | null {
  const tokenFromQuery = searchParams.get('token');
  if (tokenFromQuery) {
    storeOrderAccessToken(orderId, tokenFromQuery);
    return tokenFromQuery;
  }
  return getStoredOrderAccessToken(orderId);
}

export function appendOrderToken(path: string, token: string | null | undefined): string {
  if (!token) return path;
  const url = new URL(path, window.location.origin);
  url.searchParams.set('token', token);
  return `${url.pathname}${url.search}`;
}
