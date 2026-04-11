from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


def split_database_ssl_settings(database_url: str) -> tuple[str, str | None]:
    """Return a database URL without ssl query params plus an asyncpg/sqlalchemy ssl value."""
    parts = urlsplit(database_url)
    filtered_query: list[tuple[str, str]] = []
    ssl_value: str | None = None

    for key, value in parse_qsl(parts.query, keep_blank_values=True):
        lowered = key.lower()
        if lowered in {"ssl", "sslmode"}:
            ssl_value = value or "require"
            continue
        filtered_query.append((key, value))

    cleaned_url = urlunsplit(
        (parts.scheme, parts.netloc, parts.path, urlencode(filtered_query), parts.fragment)
    )
    return cleaned_url, ssl_value


def to_asyncpg_dsn(database_url: str) -> tuple[str, str | None]:
    cleaned_url, ssl_value = split_database_ssl_settings(database_url)
    return cleaned_url.replace("+asyncpg", ""), ssl_value


def sqlalchemy_connect_args(database_url: str) -> dict[str, str]:
    _, ssl_value = split_database_ssl_settings(database_url)
    if not ssl_value:
        return {}
    return {"ssl": ssl_value}
