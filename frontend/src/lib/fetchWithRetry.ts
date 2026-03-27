const DEFAULT_RETRY_DELAY_MS = 450;

interface FetchWithRetryOptions {
  timeoutMs?: number;
  retries?: number;
  retryDelayMs?: number;
}

function sleep(ms: number) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

function shouldRetryStatus(status: number) {
  return status === 502 || status === 503 || status === 504;
}

export async function fetchWithRetry(
  input: RequestInfo | URL,
  init?: RequestInit,
  options: FetchWithRetryOptions = {},
) {
  const { timeoutMs, retries = 0, retryDelayMs = DEFAULT_RETRY_DELAY_MS } = options;
  let attempt = 0;

  while (true) {
    const controller = new AbortController();
    const timeoutId = timeoutMs ? window.setTimeout(() => controller.abort(), timeoutMs) : null;

    try {
      const response = await fetch(input, {
        ...init,
        signal: controller.signal,
      });

      if (shouldRetryStatus(response.status) && attempt < retries) {
        attempt += 1;
        await sleep(retryDelayMs * attempt);
        continue;
      }

      return response;
    } catch (error) {
      if (attempt >= retries) {
        throw error;
      }

      attempt += 1;
      await sleep(retryDelayMs * attempt);
    } finally {
      if (timeoutId) {
        window.clearTimeout(timeoutId);
      }
    }
  }
}
