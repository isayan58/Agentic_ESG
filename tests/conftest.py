"""Pytest fixtures shared across the data-freshness / pipeline-refresh tests.

Streamlit is imported but not *run* in a ScriptRunContext during these
tests, which means ``st.session_state`` and the message helpers would
raise. We install a ``FakeStreamlit`` into the relevant module slots so
production code can call ``st.session_state[…]``, ``st.warning(…)`` etc.
normally while tests assert on the captured calls.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

# Make the repo root importable so ``from utils.x import y`` works when
# pytest is invoked from any working directory.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class FakeSessionState(dict):
    """dict-backed stand-in for ``st.session_state`` with attribute access."""

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError as exc:  # pragma: no cover - defensive
            raise AttributeError(name) from exc

    def __setattr__(self, name, value):
        self[name] = value


class FakeStreamlit:
    """Minimal recorder that mimics the Streamlit surface used by the
    refresh helpers. Every call appends to an in-memory log so tests can
    assert on warnings, captions, toasts, etc."""

    def __init__(self):
        self.session_state = FakeSessionState()
        self.warnings: list[dict] = []
        self.captions: list[str] = []
        self.toasts: list[dict] = []
        self.infos: list[str] = []
        self.errors: list[str] = []

    # ── message helpers ───────────────────────────────────────────
    def warning(self, body, icon=None):
        self.warnings.append({"body": body, "icon": icon})

    def caption(self, body):
        self.captions.append(body)

    def toast(self, body, icon=None):
        self.toasts.append({"body": body, "icon": icon})

    def info(self, body, icon=None):
        self.infos.append(body)

    def error(self, body):
        self.errors.append(body)

    # ── no-ops used by production code we don't care about ────────
    def spinner(self, *_a, **_kw):
        class _Ctx:
            def __enter__(self_inner):
                return self_inner
            def __exit__(self_inner, *a):
                return False
        return _Ctx()


@pytest.fixture
def fake_st(monkeypatch):
    """Install a FakeStreamlit into ``utils.pipeline_refresh.st``.

    Returns the fake so tests can read its recorded messages and
    session_state. Also resets the global ``state_manager`` between
    tests so stale-channel tests don't leak into each other.
    """
    fake = FakeStreamlit()

    # Import late so the module is available to patch.
    import utils.pipeline_refresh as pipeline_refresh
    monkeypatch.setattr(pipeline_refresh, "st", fake)

    # Reset the real state_manager singleton so prior tests don't leak.
    from core.state_manager import state_manager
    state_manager.clear()

    yield fake

    state_manager.clear()


class InMemoryConnector:
    """Fake connector used to drive the ConnectionManager tests.

    Instances are registered into ``utils.real_connectors.REAL_CONNECTORS``
    under a unique type so real networking never happens.
    """

    def __init__(self, df: pd.DataFrame, should_fail: bool = False,
                 fail_with: str = "simulated failure"):
        self.df = df
        self.should_fail = should_fail
        self.fail_with = fail_with
        self.fetch_calls = 0

    connector_type = "_fake_inmem"
    display_name = "Fake In-Memory"
    icon = "🧪"

    def test_connection(self, **_config):
        if self.should_fail:
            return {"success": False, "message": self.fail_with}
        return {"success": True, "message": "ok"}

    def fetch(self, **_config):
        self.fetch_calls += 1
        if self.should_fail:
            raise RuntimeError(self.fail_with)
        return self.df.copy()


@pytest.fixture
def register_fake_connector(monkeypatch):
    """Register a fresh ``InMemoryConnector`` into REAL_CONNECTORS and
    return a factory that yields (connector_type, connector_instance)
    tuples so tests can register multiple fakes per test.
    """
    import utils.real_connectors as rc

    created: list[InMemoryConnector] = []
    original = dict(rc.REAL_CONNECTORS)

    def _factory(df: pd.DataFrame | None = None, *,
                 should_fail: bool = False,
                 connector_type: str | None = None) -> tuple[str, InMemoryConnector]:
        conn = InMemoryConnector(
            df if df is not None else pd.DataFrame({"a": [1, 2, 3]}),
            should_fail=should_fail,
        )
        ctype = connector_type or f"_fake_{len(created)}"
        conn.connector_type = ctype

        # ``get_connector(ctype)`` calls the callable — for a class it would
        # instantiate. Our connector is an instance but its class behaves
        # correctly when "called" as ``instance()`` only if __call__ is
        # implemented; instead, shove a lambda that returns the instance.
        class _Wrapper:
            def __call__(self_inner):
                return conn
        rc.REAL_CONNECTORS[ctype] = _Wrapper()
        created.append(conn)
        return ctype, conn

    yield _factory

    # Restore original registry (drops test-only entries)
    rc.REAL_CONNECTORS.clear()
    rc.REAL_CONNECTORS.update(original)


@pytest.fixture
def identity_mapping(monkeypatch):
    """Short-circuit ``apply_column_mapping`` so tests focus on caching
    semantics rather than schema coercion. The fixture returns the
    original function unchanged so tests can opt out by reassigning.
    """
    import utils.connection_manager as cm

    def _passthrough(raw_df, column_mapping, target_schema):
        return raw_df

    monkeypatch.setattr(cm, "apply_column_mapping", _passthrough)
    return _passthrough
