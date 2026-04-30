"""Tests for the background job runner.

These exercise the public contract: submit returns a job_id, polling
reflects the worker's actual state, ``list_jobs`` is per-user, and the
retention cap evicts only finished jobs.
"""
from __future__ import annotations

import threading
import time

import pytest

from core import jobs


@pytest.fixture(autouse=True)
def _isolate_state():
    """Each test gets a clean job table so order/retention assertions hold."""
    jobs.reset()
    yield
    jobs.reset()


def _wait_until(predicate, timeout=2.0, interval=0.01):
    """Poll predicate until True or timeout — keeps tests fast and stable."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return False


class TestSubmitAndPoll:
    def test_completed_job_returns_result(self):
        jid = jobs.submit_job(lambda x, y: x + y, 2, 3, user_id="alice")
        assert _wait_until(lambda: jobs.get_job_status(jid)[0] == "completed")
        status, payload = jobs.get_job_status(jid)
        assert status == "completed"
        assert payload == 5

    def test_failed_job_returns_exception_message(self):
        def boom():
            raise RuntimeError("kaboom")
        jid = jobs.submit_job(boom, user_id="alice")
        assert _wait_until(lambda: jobs.get_job_status(jid)[0] == "failed")
        status, payload = jobs.get_job_status(jid)
        assert status == "failed"
        assert "kaboom" in payload

    def test_running_status_observable(self):
        gate = threading.Event()

        def slow():
            gate.wait(timeout=2.0)
            return "done"

        jid = jobs.submit_job(slow, user_id="alice")
        # Worker may take a tick to pick up; wait up to 1s for "running".
        assert _wait_until(lambda: jobs.get_job_status(jid)[0] == "running")
        gate.set()
        assert _wait_until(lambda: jobs.get_job_status(jid)[0] == "completed")

    def test_unknown_job_id(self):
        status, payload = jobs.get_job_status("does-not-exist")
        assert status == "not_found"
        assert payload is None

    def test_user_id_required(self):
        with pytest.raises(ValueError):
            jobs.submit_job(lambda: 1, user_id="")


class TestListJobsByUser:
    def test_only_returns_caller_user_jobs(self):
        a = jobs.submit_job(lambda: 1, user_id="alice", label="alice's run")
        b = jobs.submit_job(lambda: 2, user_id="bob", label="bob's run")
        _wait_until(lambda: jobs.get_job_status(a)[0] == "completed")
        _wait_until(lambda: jobs.get_job_status(b)[0] == "completed")

        alice_rows = jobs.list_jobs("alice")
        assert {r["job_id"] for r in alice_rows} == {a}
        assert alice_rows[0]["label"] == "alice's run"

        bob_rows = jobs.list_jobs("bob")
        assert {r["job_id"] for r in bob_rows} == {b}

    def test_newest_first_ordering(self):
        first = jobs.submit_job(lambda: 1, user_id="alice")
        # Submitted_at is ISO-string with microseconds — sleep just enough
        # to guarantee a distinct timestamp without slowing the test much.
        time.sleep(0.005)
        second = jobs.submit_job(lambda: 2, user_id="alice")
        rows = jobs.list_jobs("alice")
        assert [r["job_id"] for r in rows] == [second, first]

    def test_list_does_not_leak_future_objects(self):
        jid = jobs.submit_job(lambda: 1, user_id="alice")
        _wait_until(lambda: jobs.get_job_status(jid)[0] == "completed")
        rows = jobs.list_jobs("alice")
        assert "future" not in rows[0]


class TestRetention:
    def test_finished_jobs_evicted_past_cap(self, monkeypatch):
        # Shrink the cap so the test stays fast.
        monkeypatch.setattr(jobs, "_JOBS_PER_USER_CAP", 3)
        ids = []
        for i in range(5):
            jid = jobs.submit_job(lambda v=i: v, user_id="alice")
            ids.append(jid)
            _wait_until(lambda j=jid: jobs.get_job_status(j)[0] == "completed")
        # One more submit triggers eviction down to the cap.
        ids.append(jobs.submit_job(lambda: 99, user_id="alice"))
        rows = jobs.list_jobs("alice")
        assert len(rows) <= 3
        # The newest submission survives.
        assert rows[0]["job_id"] == ids[-1]

    def test_running_jobs_never_evicted(self, monkeypatch):
        monkeypatch.setattr(jobs, "_JOBS_PER_USER_CAP", 1)
        gate = threading.Event()

        def slow():
            gate.wait(timeout=2.0)

        long_running = jobs.submit_job(slow, user_id="alice", label="long")
        _wait_until(lambda: jobs.get_job_status(long_running)[0] == "running")

        # Pile on more jobs that finish immediately. The running one must
        # stay in the table — losing its job_id loses the only handle.
        for _ in range(3):
            jid = jobs.submit_job(lambda: 1, user_id="alice")
            _wait_until(lambda j=jid: jobs.get_job_status(j)[0] == "completed")

        rows = jobs.list_jobs("alice")
        ids = {r["job_id"] for r in rows}
        assert long_running in ids

        gate.set()  # let the worker free up


class TestCancel:
    def test_cancel_unknown_returns_false(self):
        assert jobs.cancel_job("nope") is False
