"""Retry + timeout policy for real-data connector fetches.

Connectors in :mod:`utils.real_connectors` historically called the remote
system once and let any failure bubble. A flaky network blip on a slow
Snowflake or BigQuery query would fail the whole pipeline run; a 503 on
HuggingFace's GCS proxy would do the same. This helper centralises a
small, opinionated retry policy so every connector inherits the same
behaviour without each fetch needing its own try/except.

Policy
------
* **Max 3 attempts** by default (one initial + two retries).
* **Exponential backoff** with jitter — 0.4s, 0.8s, 1.6s baseline. Caps
  at ``MAX_BACKOFF_SECONDS`` so a misconfigured retry doesn't stall the
  UI for a minute.
* **Only transient errors retry.** Auth failures (401/403), bad
  arguments (``ValueError``), missing dependencies (``ImportError``)
  fail fast — retrying won't help and just delays the error message
  the user needs to see.
* **A hard ceiling on total wall time** (``DEADLINE_SECONDS``) so a
  pathological retry loop can't hang the ESG Command Center Run button.

Why this lives here, not on the connectors themselves
-----------------------------------------------------
Each connector's ``fetch()`` does network I/O at a different layer
(``requests.get``, ``boto3.client.get_object``, Snowflake cursor,
``hf_hub_download``…). Reaching into each library for retry config is
messy and inconsistent. Wrapping the whole ``fetch()`` call from the
ConnectionManager gives us one knob, one log line, and one place to
tune the policy as we learn what fails in production.
"""
from __future__ import annotations

import logging
import random
import socket
import time
from typing import Callable, TypeVar

import requests as _requests

_log = logging.getLogger(__name__)

T = TypeVar("T")


# ---------------------------------------------------------------------------
# Policy knobs — keep these importable so tests can monkeypatch them down to
# zero without touching internal behaviour.
# ---------------------------------------------------------------------------
MAX_ATTEMPTS = 3
INITIAL_BACKOFF_SECONDS = 0.4
BACKOFF_MULTIPLIER = 2.0
MAX_BACKOFF_SECONDS = 4.0
JITTER_FRACTION = 0.25  # ±25% of computed backoff
DEADLINE_SECONDS = 30.0  # hard wall-clock cap across all attempts


# ---------------------------------------------------------------------------
# Error classification
# ---------------------------------------------------------------------------
# Network / server-side flakiness — worth retrying.
_TRANSIENT_EXC_TYPES: tuple[type[BaseException], ...] = (
    _requests.exceptions.Timeout,
    _requests.exceptions.ConnectionError,
    _requests.exceptions.ChunkedEncodingError,
    socket.timeout,
    ConnectionError,
    TimeoutError,
)

# Things we never retry, even if they wrap a network error: bad
# credentials, missing config, missing optional dependency.
_FATAL_EXC_TYPES: tuple[type[BaseException], ...] = (
    ImportError,
    ValueError,
    KeyError,
    NotImplementedError,
)

# HTTP status codes worth a retry. 408 / 429 / 5xx are the standard
# "try again" responses; everything else (401/403/404/422) is fatal.
_RETRYABLE_HTTP_STATUSES = frozenset({408, 425, 429, 500, 502, 503, 504})


def _http_status_of(exc: BaseException) -> int | None:
    """Pull the HTTP status off a requests.HTTPError-style exception, or None."""
    response = getattr(exc, "response", None)
    if response is None:
        return None
    return getattr(response, "status_code", None)


def is_transient(exc: BaseException) -> bool:
    """Return True if ``exc`` is worth retrying.

    Decision order:
    1. Fatal types (auth, config, missing deps) → never retry, even if
       the underlying class also matches a transient type.
    2. ``requests.HTTPError`` → retry only on the documented retryable
       status codes.
    3. Anything matching ``_TRANSIENT_EXC_TYPES`` → retry.
    4. Otherwise → fatal.
    """
    if isinstance(exc, _FATAL_EXC_TYPES):
        return False
    if isinstance(exc, _requests.exceptions.HTTPError):
        status = _http_status_of(exc)
        return status in _RETRYABLE_HTTP_STATUSES
    if isinstance(exc, _TRANSIENT_EXC_TYPES):
        return True
    # Some cloud SDKs raise their own ConnectionError-ish classes that
    # don't subclass the standard ones. Match by name as a last resort.
    name = type(exc).__name__.lower()
    if any(token in name for token in ("timeout", "throttl", "unavailable")):
        return True
    return False


def _compute_backoff(attempt: int) -> float:
    """Backoff for the *failed* ``attempt`` (1-indexed) with jitter."""
    base = min(
        INITIAL_BACKOFF_SECONDS * (BACKOFF_MULTIPLIER ** (attempt - 1)),
        MAX_BACKOFF_SECONDS,
    )
    jitter = base * JITTER_FRACTION * (2 * random.random() - 1)
    return max(0.0, base + jitter)


def with_retry(
    fn: Callable[..., T],
    *args,
    description: str = "fetch",
    max_attempts: int | None = None,
    deadline_seconds: float | None = None,
    sleep: Callable[[float], None] = time.sleep,
    **kwargs,
) -> T:
    """Call ``fn(*args, **kwargs)`` with the connector retry policy.

    Parameters
    ----------
    fn : callable
        The function to invoke. The signature is opaque to this helper —
        it just forwards args/kwargs unchanged.
    description : str
        Used in the log line on retry so the user can see *which* fetch
        is being retried (``"snowflake fetch"``, ``"s3 fetch"``…). Has no
        effect on behaviour.
    max_attempts, deadline_seconds : optional overrides
        Per-call overrides for the module-level defaults. Tests use
        ``max_attempts=1`` to disable retries entirely.
    sleep : callable
        Override for ``time.sleep`` so tests can run instantly and
        assert the requested backoff durations.

    Returns
    -------
    Whatever ``fn`` returns. On terminal failure, re-raises the last
    exception untouched so callers see the original traceback.

    Raises
    ------
    The last seen exception. Fatal errors (auth, config, ImportError)
    are raised on the first attempt — no retries are performed.
    """
    attempts_cap = max_attempts if max_attempts is not None else MAX_ATTEMPTS
    deadline = deadline_seconds if deadline_seconds is not None else DEADLINE_SECONDS
    started = time.monotonic()
    last_exc: BaseException | None = None

    for attempt in range(1, attempts_cap + 1):
        try:
            return fn(*args, **kwargs)
        except Exception as exc:  # noqa: BLE001 — re-raised below
            last_exc = exc
            if not is_transient(exc):
                raise
            if attempt >= attempts_cap:
                break
            elapsed = time.monotonic() - started
            if elapsed >= deadline:
                _log.warning(
                    "%s gave up after %.1fs (deadline %.1fs): %s",
                    description, elapsed, deadline, exc,
                )
                break
            backoff = _compute_backoff(attempt)
            # Don't sleep past the deadline.
            backoff = min(backoff, max(0.0, deadline - elapsed))
            _log.info(
                "%s attempt %d/%d failed (%s); retrying in %.2fs",
                description, attempt, attempts_cap, exc, backoff,
            )
            if backoff > 0:
                sleep(backoff)

    assert last_exc is not None  # narrowed by the loop above
    raise last_exc


__all__ = [
    "MAX_ATTEMPTS",
    "INITIAL_BACKOFF_SECONDS",
    "BACKOFF_MULTIPLIER",
    "MAX_BACKOFF_SECONDS",
    "DEADLINE_SECONDS",
    "is_transient",
    "with_retry",
]
