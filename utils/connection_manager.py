"""Connection Manager — tracks configured real data sources during a session.

Stores source configurations in memory only (session-scoped).
Orchestrates fetching from real connectors and applying column mappings.
"""
import pandas as pd
from datetime import datetime
from utils.real_connectors import get_connector
from utils.schema_mapper import apply_column_mapping


class ConnectionManager:
    """Manages real data source connections for a user session."""

    def __init__(self):
        self._sources: dict[str, dict] = {}

    def add_source(self, source_id: str, connector_type: str, config: dict,
                   target_schema: str, column_mapping: dict,
                   display_name: str = "") -> None:
        """Register a configured data source."""
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
        }

    def remove_source(self, source_id: str) -> bool:
        """Remove a data source. Returns True if it existed."""
        return self._sources.pop(source_id, None) is not None

    def get_source(self, source_id: str) -> dict | None:
        return self._sources.get(source_id)

    def list_sources(self) -> list[dict]:
        """Return all registered sources with their metadata."""
        return [
            {"id": sid, **meta}
            for sid, meta in self._sources.items()
        ]

    def has_sources(self) -> bool:
        return len(self._sources) > 0

    def fetch_source(self, source_id: str) -> pd.DataFrame:
        """Fetch data from one source, apply column mapping, return mapped DataFrame."""
        source = self._sources.get(source_id)
        if source is None:
            raise KeyError(f"Unknown source: {source_id}")

        connector = get_connector(source["connector_type"])
        raw_df = connector.fetch(**source["config"])

        # Apply column mapping
        mapped_df = apply_column_mapping(
            raw_df,
            source["column_mapping"],
            source["target_schema"],
        )

        # Update metadata
        source["last_fetch"] = datetime.now().isoformat()
        source["last_row_count"] = len(mapped_df)
        source["status"] = "active"

        return mapped_df

    def fetch_all(self) -> dict[str, pd.DataFrame]:
        """Fetch from all registered sources.

        Returns {source_id: mapped_DataFrame}.
        If a source fails, its value is an empty DataFrame and status is set to 'error'.
        """
        results = {}
        for source_id in list(self._sources):
            try:
                results[source_id] = self.fetch_source(source_id)
            except Exception as e:
                self._sources[source_id]["status"] = "error"
                self._sources[source_id]["error"] = str(e)
                results[source_id] = pd.DataFrame()
        return results

    def fetch_all_by_schema(self) -> dict[str, pd.DataFrame]:
        """Fetch all sources and group by target schema.

        Returns {schema_name: concatenated_DataFrame}.
        Multiple sources targeting the same schema are concatenated.
        """
        all_data = self.fetch_all()
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
