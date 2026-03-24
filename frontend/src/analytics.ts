/**
 * PostHog + Sentry initialization.
 * Import this module early in main.tsx so tracking starts on page load.
 */

import posthog from 'posthog-js';
import * as Sentry from '@sentry/react';

// PostHog — only init if env var is set
const posthogKey = import.meta.env.VITE_POSTHOG_KEY as string | undefined;
if (posthogKey) {
  posthog.init(posthogKey, {
    api_host: (import.meta.env.VITE_POSTHOG_HOST as string) || 'https://app.posthog.com',
    autocapture: true,
    capture_pageview: true,
    persistence: 'localStorage',
  });
}

// Sentry — only init if env var is set
const sentryDsn = import.meta.env.VITE_SENTRY_DSN as string | undefined;
if (sentryDsn) {
  Sentry.init({
    dsn: sentryDsn,
    integrations: [
      Sentry.browserTracingIntegration(),
    ],
    tracesSampleRate: 0.1,
    beforeSend(event) {
      // Strip contract text from breadcrumbs and request data
      if (event.breadcrumbs) {
        for (const crumb of event.breadcrumbs) {
          if (crumb.data && typeof crumb.data === 'object' && 'contract_text' in crumb.data) {
            crumb.data.contract_text = '[REDACTED]';
          }
        }
      }
      return event;
    },
  });
}

export { posthog, Sentry };
