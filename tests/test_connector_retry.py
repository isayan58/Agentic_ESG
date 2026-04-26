"""Tests for the shared connector retry/timeout policy.

These pin the *contract* of :mod:`utils.connector_retry`:
  * fatal errors fail fast (no retries),
  * transient errors retry up to ``MAX_ATTEMPTS``,
  * the deadline caps total wall-clock cost,
  * HTTP retries follow the documented status-code allow-list.
"""
from __future__ import annotations

import socket
from unittest.mock import MagicMock

import pytest
import requests

from utils import connector_retry


# ---------------------------------------------------------------------------
# is_transient classification
# ---------------------------------------------------------------------------
class TestIsTransient:
    def test_timeout_is_transient(self):
        assert connector_retry.is_transient(requests.exceptions.Timeout("slow"))

    def test_connection_error_is_transient(self):
        assert connector_retry.is_transient(requests.exceptions.ConnectionError("nope"))

    def test_socket_timeout_is_transient(self):
        assert connector_retry.is_transient(socket.timeout("slow"))

    def test_value_error_is_fatal(self):
        assert not connector_retry.is_transient(ValueError("bad config"))

    def test_import_error_is_fatal(self):
        assert not connector_retry.is_transient(ImportError("missing driver"))

    def test_key_error_is_fatal(self):
        assert not connector_retry.is_transient(KeyError("missing key"))

    @pytest.mark.parametrize("status", [408, 425, 429, 500, 502, 503, 504])
    def test_retryable_http_status(self, status):
        exc = requests.exceptions.HTTPError("server unhappy")
        exc.response = MagicMock(status_code=status)
        assert connector_retry.is_transient(exc)

    @pytest.mark.parametrize("status", [400, 401, 403, 404, 422])
    def test_fatal_http_status(self, status):
        exc = requests.exceptions.HTTPError("client error")
        exc.response = MagicMock(status_code=status)
        assert not connector_retry.is_transient(exc)

    def test_class_name_heuristic_matches_throttling(self):
        class S3Throttled(Exception):
            pass

        assert connector_retry.is_transient(S3Throttled("slow down"))

    def test_class_name_heuristic_matches_unavailable(self):
        class ServiceUnavailable(Exception):
            pass

        assert connector_retry.is_transient(ServiceUnavailable("come back later"))

    def test_unknown_runtime_error_is_fatal(self):
        # Anything that isn't a known transient class and doesn't match
        # the name heuristic is treated as fatal — we'd rather fail
        # loudly than retry forever on a programming bug.
        assert not connector_retry.is_transient(RuntimeError("logic bomb"))


# ---------------------------------------------------------------------------
# with_retry behaviour
# ---------------------------------------------------------------------------
class TestWithRetry:
    def test_returns_value_on_success(self):
        fn = MagicMock(return_value="ok")
        assert connector_retry.with_retry(fn) == "ok"
        assert fn.call_count == 1

    def test_no_retry_on_fatal_error(self):
        fn = MagicMock(side_effect=ValueError("bad"))
        with pytest.raises(ValueError):
            connector_retry.with_retry(fn)
        assert fn.call_count == 1

    def test_retries_transient_then_succeeds(self):
        # Fail twice, then succeed. With MAX_ATTEMPTS=3 this should
        # return cleanly without raising.
        fn = MagicMock(side_effect=[
            requests.exceptions.ConnectionError("net glitch"),
            requests.exceptions.Timeout("slow"),
            "ok",
        ])
        sleeps: list[float] = []
        result = connector_retry.with_retry(fn, sleep=sleeps.append)
        assert result == "ok"
        assert fn.call_count == 3
        # Two failures means two sleeps. Both must be non-negative.
        assert len(sleeps) == 2
        assert all(s >= 0 for s in sleeps)

    def test_gives_up_after_max_attempts(self):
        fn = MagicMock(side_effect=requests.exceptions.Timeout("slow"))
        with pytest.raises(requests.exceptions.Timeout):
            connector_retry.with_retry(fn, sleep=lambda _s: None)
        assert fn.call_count == connector_retry.MAX_ATTEMPTS

    def test_max_attempts_one_disables_retries(self):
        fn = MagicMock(side_effect=requests.exceptions.Timeout("slow"))
        with pytest.raises(requests.exceptions.Timeout):
            connector_retry.with_retry(fn, max_attempts=1, sleep=lambda _s: None)
        assert fn.call_count == 1

    def test_deadline_caps_total_time(self, monkeypatch):
        # Fake monotonic clock: starts at 0, jumps past the deadline
        # by the time the second attempt's elapsed-check happens. The
        # loop runs attempt 1, fails, sees 100s elapsed against a 1s
        # deadline, and breaks before issuing attempt 2 — even though
        # MAX_ATTEMPTS would allow up to 5.
        clock = iter([0.0, 0.0, 100.0, 100.0, 100.0])
        monkeypatch.setattr(connector_retry.time, "monotonic", lambda: next(clock))

        fn = MagicMock(side_effect=requests.exceptions.Timeout("slow"))
        with pytest.raises(requests.exceptions.Timeout):
            connector_retry.with_retry(
                fn, max_attempts=5, deadline_seconds=1.0, sleep=lambda _s: None,
            )
        # Stops well below MAX_ATTEMPTS — proves the deadline is what
        # capped the loop, not the attempt count. (Exact count depends
        # on how many monotonic() reads happen per attempt; cap is the
        # contract that matters.)
        assert fn.call_count < 5

    def test_forwards_args_and_kwargs(self):
        fn = MagicMock(return_value=42)
        assert connector_retry.with_retry(fn, 1, 2, foo="bar") == 42
        fn.assert_called_once_with(1, 2, foo="bar")

    def test_http_5xx_retries_then_propagates(self):
        # Simulate a 503 that never recovers — must retry up to the cap
        # and then re-raise the original exception unchanged.
        exc = requests.exceptions.HTTPError("upstream down")
        exc.response = MagicMock(status_code=503)
        fn = MagicMock(side_effect=exc)
        with pytest.raises(requests.exceptions.HTTPError):
            connector_retry.with_retry(fn, sleep=lambda _s: None)
        assert fn.call_count == connector_retry.MAX_ATTEMPTS

    def test_http_401_does_not_retry(self):
        exc = requests.exceptions.HTTPError("auth")
        exc.response = MagicMock(status_code=401)
        fn = MagicMock(side_effect=exc)
        with pytest.raises(requests.exceptions.HTTPError):
            connector_retry.with_retry(fn, sleep=lambda _s: None)
        assert fn.call_count == 1
