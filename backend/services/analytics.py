"""Analytics helpers. PostHog event capture and Sentry exception forwarding.

Both helpers are no-ops when the corresponding SDK is not configured, so the
main request flow is never blocked by an observability failure.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


def _sentry_initialized(sentry_sdk: Any) -> bool:
    client = sentry_sdk.get_client()
    return bool(client and client.is_active())


def capture(distinct_id: str, event: str, properties: dict[str, Any] | None = None) -> None:
    """Send an event to PostHog. No-op if PostHog is not configured."""
    try:
        import posthog

        if not posthog.api_key:
            logger.debug("PostHog not configured; skipping event %s", event)
            return
        posthog.capture(distinct_id, event, properties or {})
        logger.debug(
            "PostHog event captured: event=%s distinct_id=%s properties=%s",
            event,
            distinct_id,
            properties or {},
        )
    except Exception as e:
        # Never let analytics break the main flow
        logger.debug("PostHog capture failed: %s", e)


def capture_exception(exc: BaseException, *, tags: dict[str, str] | None = None) -> None:
    """Forward an exception to Sentry. No-op if Sentry is not initialized."""
    try:
        import sentry_sdk

        if not _sentry_initialized(sentry_sdk):
            logger.debug("Sentry not initialized; skipping exception capture")
            return
        if tags:
            with sentry_sdk.push_scope() as scope:
                for key, value in tags.items():
                    scope.set_tag(key, value)
                sentry_sdk.capture_exception(exc)
        else:
            sentry_sdk.capture_exception(exc)
    except Exception as e:
        logger.debug("Sentry capture_exception failed: %s", e)


def capture_message(message: str, *, level: str = "warning", tags: dict[str, str] | None = None) -> None:
    """Forward a message to Sentry. No-op if Sentry is not initialized."""
    try:
        import sentry_sdk

        if not _sentry_initialized(sentry_sdk):
            logger.debug("Sentry not initialized; skipping message capture")
            return
        if tags:
            with sentry_sdk.push_scope() as scope:
                for key, value in tags.items():
                    scope.set_tag(key, value)
                sentry_sdk.capture_message(message, level=level)
        else:
            sentry_sdk.capture_message(message, level=level)
    except Exception as e:
        logger.debug("Sentry capture_message failed: %s", e)
