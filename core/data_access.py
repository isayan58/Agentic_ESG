"""Helpers for retrieving canonical datasets from shared state.

Downstream agents should prefer datasets published by the Data Collector
so the pipeline uses collected / mapped data first, while still falling
back to bundled sample files when agents are run in isolation.
"""
from __future__ import annotations

import pandas as pd

from core.state_manager import state_manager
from utils.data_processing import _norm_cols


def _to_dataframe(data) -> pd.DataFrame:
    """Best-effort conversion from shared-state payloads to DataFrame.

    Column names are normalised to lowercase snake_case so payloads
    stored with any capitalisation are always readable by agent code.
    """
    if isinstance(data, pd.DataFrame):
        return _norm_cols(data.copy())
    if isinstance(data, dict):
        try:
            return _norm_cols(pd.DataFrame(data))
        except Exception:
            return pd.DataFrame()
    if isinstance(data, list):
        try:
            return _norm_cols(pd.DataFrame(data))
        except Exception:
            return pd.DataFrame()
    return pd.DataFrame()


def get_dataset(schema_name: str, fallback_loader=None) -> pd.DataFrame:
    """Return a canonical dataset for a schema from shared state if present."""
    for channel in (
        f"dataset_{schema_name}",
        f"validated_{schema_name}",
        f"validated_real_{schema_name}",
    ):
        payload = state_manager.subscribe(channel)
        if payload is None:
            continue
        df = _to_dataframe(payload)
        if not df.empty:
            return df

    if fallback_loader is not None:
        return fallback_loader()
    return pd.DataFrame()
