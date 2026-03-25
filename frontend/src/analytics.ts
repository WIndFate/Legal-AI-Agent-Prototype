export async function bootstrapAnalytics() {
  const posthogKey = import.meta.env.VITE_POSTHOG_KEY as string | undefined;
  const sentryDsn = import.meta.env.VITE_SENTRY_DSN as string | undefined;

  const tasks: Promise<unknown>[] = [];

  if (posthogKey) {
    tasks.push(
      import('posthog-js').then(({ default: posthog }) => {
        posthog.init(posthogKey, {
          api_host: (import.meta.env.VITE_POSTHOG_HOST as string) || 'https://app.posthog.com',
          autocapture: true,
          capture_pageview: true,
          persistence: 'localStorage',
        });
      }),
    );
  }

  if (sentryDsn) {
    tasks.push(
      import('@sentry/react').then((Sentry) => {
        Sentry.init({
          dsn: sentryDsn,
          integrations: [
            Sentry.browserTracingIntegration(),
          ],
          tracesSampleRate: 0.1,
          beforeSend(event) {
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
      }),
    );
  }

  await Promise.all(tasks);
}
