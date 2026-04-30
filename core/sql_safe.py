"""Safe SQL helpers for connector preview/test paths.

Connector forms accept a user-authored SELECT/CTE query and we wrap it in
``SELECT * FROM (<query>) LIMIT N`` to fetch a small preview. Two failure
modes we care about:

1. A trailing ``;`` or ``-- comment`` in the inner query breaks the wrapper's
   syntax, which surfaces as a confusing parse error.
2. A multi-statement payload (``SELECT 1; DROP TABLE x``) escapes the wrapper
   and runs destructive SQL against the user's database.

``validate_readonly_sql`` rejects (2) and ``preview_query`` produces the
wrapped string used at every test_connection() call site.
"""
from __future__ import annotations

import re

# Write/DDL keywords we never want to see in a preview query.
_FORBIDDEN_KEYWORDS = (
    "DROP", "DELETE", "TRUNCATE", "ALTER",
    "INSERT", "UPDATE", "MERGE", "GRANT", "REVOKE", "CREATE",
)
_FORBIDDEN_KW_RE = re.compile(
    r"\b(" + "|".join(_FORBIDDEN_KEYWORDS) + r")\b",
    re.IGNORECASE,
)

# Multi-statement / comment markers — block at the wrapper layer.
_FORBIDDEN_TOKENS = (";", "--", "/*", "*/")


def validate_readonly_sql(query: str) -> str:
    """Return a normalized SELECT/CTE query, or raise ``ValueError``.

    Strips a single trailing semicolon (common, harmless), then enforces:
    starts with SELECT or WITH; contains no write/DDL keywords; contains
    no multi-statement or comment tokens.
    """
    if not isinstance(query, str):
        raise ValueError("Query must be a string.")

    q = query.strip()
    if q.endswith(";"):
        q = q[:-1].rstrip()

    if not q:
        raise ValueError("Query is empty.")

    lower = q.lower()
    if not (lower.startswith("select") or lower.startswith("with")):
        raise ValueError("Only SELECT or WITH (CTE) queries are allowed.")

    for token in _FORBIDDEN_TOKENS:
        if token in q:
            raise ValueError(f"Unsafe SQL token detected: {token!r}")

    match = _FORBIDDEN_KW_RE.search(q)
    if match:
        raise ValueError(f"Unsafe SQL keyword detected: {match.group(1).upper()}")

    return q


def preview_query(query: str, limit: int = 5, alias: str = "_preview") -> str:
    """Wrap a validated read-only query for a small preview fetch.

    ``alias`` is the subquery alias — some dialects (Postgres, MySQL) require
    one; BigQuery does not but tolerates it.
    """
    safe = validate_readonly_sql(query)
    n = int(limit)
    if n <= 0:
        raise ValueError("limit must be a positive integer.")
    return f"SELECT * FROM ({safe}) AS {alias} LIMIT {n}"
