"""Connection Manager — tracks configured real data sources during a session.

Stores source configurations in memory only (session-scoped).
Orchestrates fetching from real connectors and applying column mappings.
Per-source config signatures enable selective re-fetch so an unchanged
Snowflake query doesn't re-execute on every page Run.
"""
import hashlib
import json

import pandas as pd
from datetime import datetime
from utils.real_connectors import get_connector
from utils.schema_mapper import apply_column_mapping


def _signature(*parts) -> str:
    """Return a stable SHA-256 digest for arbitrary JSON-able values.

    Bytes are hashed with full SHA-256 (no truncation) so upload collisions
    are astronomically unlikely.
    """
    def _coerce(value):
        if isinstance(value, (bytes, bytearray)):
            return f"bytes:{len(value)}:{hashlib.sha256(bytes(value)).hexdigest()}"
        if isinstance(value, dict):
            return {k: _coerce(v) for k, v in sorted(value.items())}
        if isinstance(value, (list, tuple)):
            return [_coerce(v) for v in value]
        try:
            json.dumps(value)
            return value
        except TypeError:
            return repr(value)

    coerced = [_coerce(p) for p in parts]
    try:
        serialised = json.dumps(coerced, sort_keys=True, default=str)
    except Exception:
        serialised = repr(coerced)
    return hashlib.sha256(serialised.encode("utf-8")).hexdigest()


class ConnectionManager:
    """Manages real data source connections for a user session.

    Supports optional persistence via an ``on_change`` callback. When set,
    the callback is invoked (with ``self`` as the only argument) after
    every ``add_source`` / ``remove_source`` so a store can snapshot the
    registry to durable storage. The callback is *best-effort*: failures
    are swallowed so a transient Hub outage can't break a user's session.
    """

    def __init__(self, on_change=None):
        self._sources: dict[str, dict] = {}
        self._on_change = on_change

    # ── Persistence hooks ──────────────────────────────────────────

    def set_on_change(self, callback) -> None:
        """Install or replace the change-callback after construction."""
        self._on_change = callback

    def _fire_change(self) -> None:
        cb = self._on_change
        if cb is None:
            return
        try:
            cb(self)
        except Exception:
            # Never let a persistence failure surface into the UI path.
            pass

    def hydrate_sources(self, records: list[dict]) -> None:
        """Replace the in-memory registry with ``records`` from a store.

        Deliberately bypasses the on_change callback — we're loading *from*
        the store, not writing back to it. Missing / malformed fields get
        permissive defaults so a schema change can't brick a user's saved
        sources.
        """
        self._sources = {}
        for rec in records or []:
            sid = rec.get("id") or rec.get("source_id")
            if not sid or not rec.get("connector_type"):
                continue
            self._sources[sid] = {
                "connector_type": rec["connector_type"],
                "config": rec.get("config") or {},
                "target_schema": rec.get("target_schema") or "emissions",
                "column_mapping": rec.get("column_mapping") or {},
                "display_name": rec.get("display_name") or f"{rec['connector_type']}:{sid}",
                "added_at": rec.get("added_at") or datetime.now().isoformat(),
                "last_fetch": None,
                "last_row_count": 0,
                "status": "configured",
                "_cached_signature": None,
                "_cached_df": None,
            }

    # ── Source registration ────────────────────────────────────────

    def add_source(self, source_id: str, connector_type: str, config: dict,
                   target_schema: str, column_mapping: dict,
                   display_name: str = "") -> None:
        """Register (or overwrite) a configured data source.

        Overwriting an existing source clears its cached DataFrame so the
        next fetch sees the new config. Fires the persistence callback.
        """
        self._sources[source_id] = {
            "connector_type": connector_type,
            "config": config,
            "target_schema": target_schema,
            "column_mapping": column_mapping,
            "display_name": display_name or f"{connector_type}:{source_id}",
            "added_at": datetime.now().isoformat(),
            "last_fetch": None,
            "last_row_count": 0,
            "status": "configured",
            # Per-source cache
            "_cached_signature": None,
            "_cached_df": None,
        }
        self._fire_change()

    def remove_source(self, source_id: str) -> bool:
        """Remove a data source. Returns True if it existed.

        Fires the persistence callback when something was actually removed.
        """
        removed = self._sources.pop(source_id, None) is not None
        if removed:
            self._fire_change()
        return removed

    def get_source(self, source_id: str) -> dict | None:
        return self._sources.get(source_id)

    def list_sources(self) -> list[dict]:
        """Return all registered sources with their metadata (cache fields stripped)."""
        return [
            {"id": sid, **{k: v for k, v in meta.items() if not k.startswith("_")}}
            for sid, meta in self._sources.items()
        ]

    def has_sources(self) -> bool:
        return len(self._sources) > 0

    # ── Signatures ────────────────────────────────────────────────

    def source_signature(self, source_id: str) -> str:
        """Hash of the source's connector + target schema + mapping + config."""
        src = self._sources.get(source_id)
        if src is None:
            return ""
        return _signature(
            src["connector_type"],
            src["target_schema"],
            src["column_mapping"],
            src["config"],
        )

    def sources_signature(self) -> str:
        """Hash across every registered source (order-independent)."""
        return _signature(sorted(
            (sid, self.source_signature(sid)) for sid in self._sources
        ))

    # ── Fetching ──────────────────────────────────────────────────

    def fetch_source(self, source_id: str, use_cache: bool = False) -> pd.DataFrame:
        """Fetch data from one source, apply column mapping, return mapped DataFrame.

        When ``use_cache=True`` and the source's config signature matches the
        last successful fetch, the cached DataFrame is returned without
        round-tripping to the remote system.
        """
        source = self._sources.get(source_id)
        if source is None:
            raise KeyError(f"Unknown source: {source_id}")

        sig = self.source_signature(source_id)
        if (use_cache
                and source.get("_cached_signature") == sig
                and source.get("_cached_df") is not None):
            return source["_cached_df"].copy()

        connector = get_connector(source["connector_type"])
        raw_df = connector.fetch(**source["config"])

        # Apply column mapping
        mapped_df = apply_column_mapping(
            raw_df,
            source["column_mapping"],
            source["target_schema"],
        )

        # Update metadata + cache
        source["last_fetch"] = datetime.now().isoformat()
        source["last_row_count"] = len(mapped_df)
        source["status"] = "active"
        source["_cached_signature"] = sig
        source["_cached_df"] = mapped_df.copy()

        return mapped_df

    def fetch_all(self, use_cache: bool = False) -> dict[str, pd.DataFrame]:
        """Fetch from all registered sources.

        Returns {source_id: mapped_DataFrame}.
        If a source fails, its value is an empty DataFrame and status is set to 'error'.
        ``use_cache`` is forwarded to :meth:`fetch_source`.
        """
        results = {}
        for source_id in list(self._sources):
            try:
                results[source_id] = self.fetch_source(source_id, use_cache=use_cache)
            except Exception as e:
                self._sources[source_id]["status"] = "error"
                self._sources[source_id]["error"] = str(e)
                results[source_id] = pd.DataFrame()
        return results

    def fetch_all_by_schema(self, use_cache: bool = False) -> dict[str, pd.DataFrame]:
        """Fetch all sources and group by target schema.

        Returns {schema_name: concatenated_DataFrame}.
        Multiple sources targeting the same schema are concatenated.
        When ``use_cache=True``, unchanged sources reuse their last fetched
        DataFrame instead of re-executing against the remote system.
        """
        all_data = self.fetch_all(use_cache=use_cache)
        by_schema: dict[str, list[pd.DataFrame]] = {}

        for source_id, df in all_data.items():
            if df.empty:
                continue
            schema = self._sources[source_id]["target_schema"]
            by_schema.setdefault(schema, []).append(df)

        return {
            schema: pd.concat(dfs, ignore_index=True)
            for schema, dfs in by_schema.items()
        }

    def source_errors(self) -> dict[str, str]:
        """Return {source_id: error_message} for every source that last errored."""
        return {
            sid: meta.get("error", "unknown error")
            for sid, meta in self._sources.items()
            if meta.get("status") == "error"
        }

    def invalidate_cache(self, source_id: str | None = None) -> None:
        """Drop cached DataFrames so the next fetch hits the remote system."""
        targets = [source_id] if source_id else list(self._sources)
        for sid in targets:
            src = self._sources.get(sid)
            if src:
                src["_cached_signature"] = None
                src["_cached_df"] = None
