"""Regression tests for the Data Collector page's session-state init.

Production bug (2026-04-20): users hitting ESG Command Center or the ESG ROI
page first caused ``utils/pipeline_refresh.py`` to seed
``st.session_state["data_collector"]``. When the user later navigated to
the Data Collector page, the page's combined init guard:

    if "data_collector" not in st.session_state:
        st.session_state.data_collector = DataCollectorAgent()
        st.session_state.data_collector_results = None

short-circuited because ``data_collector`` was already present, leaving
``data_collector_results`` un-initialised. Line 626 then exploded with::

    AttributeError: st.session_state has no attribute "data_collector_results"

The fix splits the two checks so each key is initialised independently.
This test pins both:

* the *behavioural* invariant — both keys must be initialised regardless
  of whether ``data_collector`` was pre-populated by another page; and
* the *structural* invariant — the page file must NOT nest the
  ``data_collector_results`` initialisation inside the
  ``data_collector`` guard, so a future refactor that re-merges the two
  guards is caught at CI time rather than in production.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest


PAGE_PATH = Path(__file__).resolve().parent.parent / "pages" / "2_Data_Collector.py"


# ---------------------------------------------------------------------------
# Behavioural test — simulates the production page-navigation order.
# ---------------------------------------------------------------------------
class _DummyAgent:
    """Stand-in for ``DataCollectorAgent`` used in the simulated page run.

    The real agent imports a tree of HF clients and connectors; we don't
    need any of that to verify the init pattern.
    """


def _run_page_init(fake_st) -> None:
    """Replicate the page's session-state init guards verbatim.

    Kept in sync with ``pages/2_Data_Collector.py`` lines 29-37. If the
    page is refactored, mirror the change here so this regression test
    stays meaningful.
    """
    if "data_collector" not in fake_st.session_state:
        fake_st.session_state["data_collector"] = _DummyAgent()
    if "data_collector_results" not in fake_st.session_state:
        fake_st.session_state["data_collector_results"] = None


def test_init_when_data_collector_pre_populated_by_pipeline_refresh(monkeypatch):
    """Reproduce the exact production failure mode.

    Order of events:
      1. User opens ESG Command Center → ``utils/pipeline_refresh.refresh_real_data``
         runs and stashes its DataCollectorAgent in
         ``st.session_state["data_collector"]``.
      2. User clicks the Data Collector page in the sidebar.
      3. Page top-level init runs.
      4. Page tries to read ``st.session_state.data_collector_results``.

    Without the fix, step (4) raises ``AttributeError``.
    """
    from tests.conftest import FakeStreamlit  # local import — avoids module-load order issues
    fake_st = FakeStreamlit()
    monkeypatch.setitem(sys.modules, "streamlit", fake_st)

    # Step 1 — pipeline_refresh seeds the agent (simulated).
    fake_st.session_state["data_collector"] = _DummyAgent()
    assert "data_collector_results" not in fake_st.session_state

    # Step 3 — page init runs.
    _run_page_init(fake_st)

    # Step 4 — both keys must now be present.
    assert "data_collector" in fake_st.session_state
    assert "data_collector_results" in fake_st.session_state
    assert fake_st.session_state["data_collector_results"] is None


def test_init_when_nothing_pre_populated(monkeypatch):
    """Sanity check: cold start (no prior page navigation) must also work."""
    from tests.conftest import FakeStreamlit
    fake_st = FakeStreamlit()
    monkeypatch.setitem(sys.modules, "streamlit", fake_st)

    _run_page_init(fake_st)

    assert "data_collector" in fake_st.session_state
    assert "data_collector_results" in fake_st.session_state
    assert fake_st.session_state["data_collector_results"] is None


def test_init_idempotent_under_streamlit_rerun(monkeypatch):
    """Streamlit re-runs page top-level on every interaction. The init
    must not clobber an existing ``data_collector_results`` value (e.g. a
    prior pipeline run's output the user is currently viewing).
    """
    from tests.conftest import FakeStreamlit
    fake_st = FakeStreamlit()
    monkeypatch.setitem(sys.modules, "streamlit", fake_st)

    # Simulate a previous run having stashed real results.
    sentinel_results = {"datasets_loaded": 7, "total_records": 12345}
    fake_st.session_state["data_collector"] = _DummyAgent()
    fake_st.session_state["data_collector_results"] = sentinel_results

    # The next Streamlit re-run hits the page top-level again.
    _run_page_init(fake_st)

    # The user's last results must be preserved.
    assert fake_st.session_state["data_collector_results"] is sentinel_results


# ---------------------------------------------------------------------------
# Structural test — guards against a future refactor re-introducing the bug.
# ---------------------------------------------------------------------------
def _find_assign_targets_in_block(block: list[ast.stmt]) -> set[str]:
    """Return ``st.session_state.<name>`` / ``st.session_state["<name>"]``
    targets assigned inside ``block`` (recursively into ``If`` bodies)."""
    targets: set[str] = set()
    for stmt in block:
        if isinstance(stmt, ast.Assign):
            for tgt in stmt.targets:
                # st.session_state.<name> = ...
                if (
                    isinstance(tgt, ast.Attribute)
                    and isinstance(tgt.value, ast.Attribute)
                    and tgt.value.attr == "session_state"
                    and isinstance(tgt.value.value, ast.Name)
                    and tgt.value.value.id == "st"
                ):
                    targets.add(tgt.attr)
                # st.session_state["<name>"] = ...
                if (
                    isinstance(tgt, ast.Subscript)
                    and isinstance(tgt.value, ast.Attribute)
                    and tgt.value.attr == "session_state"
                ):
                    if isinstance(tgt.slice, ast.Constant) and isinstance(tgt.slice.value, str):
                        targets.add(tgt.slice.value)
        if isinstance(stmt, ast.If):
            targets |= _find_assign_targets_in_block(stmt.body)
            targets |= _find_assign_targets_in_block(stmt.orelse)
    return targets


def test_data_collector_results_init_not_nested_inside_data_collector_guard():
    """Pin the structural fix.

    The page must initialise ``data_collector_results`` in its OWN
    top-level guard (``if "data_collector_results" not in st.session_state``),
    not as a side-effect of the ``data_collector`` guard. If a future
    refactor re-merges them, this test fails before the bug ships.
    """
    tree = ast.parse(PAGE_PATH.read_text())

    # Find every top-level ``if "<key>" not in st.session_state:`` block.
    data_collector_guard_targets: set[str] = set()
    saw_dedicated_results_guard = False

    for stmt in tree.body:
        if not isinstance(stmt, ast.If):
            continue
        test = stmt.test
        # Match: "<literal>" not in st.session_state
        if not (isinstance(test, ast.Compare)
                and len(test.ops) == 1
                and isinstance(test.ops[0], ast.NotIn)
                and isinstance(test.left, ast.Constant)
                and isinstance(test.left.value, str)):
            continue
        guard_key = test.left.value
        targets_in_block = _find_assign_targets_in_block(stmt.body)

        if guard_key == "data_collector":
            data_collector_guard_targets = targets_in_block
        elif guard_key == "data_collector_results":
            saw_dedicated_results_guard = True

    assert saw_dedicated_results_guard, (
        "pages/2_Data_Collector.py must contain a dedicated "
        "`if \"data_collector_results\" not in st.session_state:` guard. "
        "This was the original 2026-04-20 production bug — do not remove."
    )
    assert "data_collector_results" not in data_collector_guard_targets, (
        "data_collector_results must NOT be initialised inside the "
        "`if \"data_collector\" not in st.session_state:` guard. When "
        "another page (ESG Command Center, ESG ROI) seeds `data_collector` "
        "via utils/pipeline_refresh, the guard short-circuits and "
        "`data_collector_results` stays undefined → AttributeError on "
        "first use. See test_init_when_data_collector_pre_populated_by_"
        "pipeline_refresh for the runtime reproducer."
    )
