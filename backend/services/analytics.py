"""PostHog analytics helper. Captures events only when PostHog is configured."""

import logging
from typing import Any

logger = logging.getLogger(__name__)


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
