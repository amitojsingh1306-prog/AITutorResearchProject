"""Timezone-safe timestamp helpers."""

from datetime import datetime, timezone


def utc_now() -> datetime:
    """Return the current timezone-aware UTC timestamp."""

    return datetime.now(timezone.utc)


def parse_timestamp(value: str) -> datetime:
    """Parse an ISO-8601 timestamp stored in ChromaDB."""

    return datetime.fromisoformat(value)
