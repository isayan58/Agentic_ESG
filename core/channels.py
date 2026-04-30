"""Centralized channel names for the per-user pub/sub state manager.

Agents publish/subscribe by channel name. Spelling mistakes in those names
are silent failures — the publisher writes to one key, the subscriber reads
from another, and the downstream agent quietly receives ``None``. Routing
every reference through this enum makes typos a NameError instead.

Members subclass ``str`` so existing call sites that compare to plain
strings or use channels as dict keys keep working unchanged.
"""
from __future__ import annotations

from enum import Enum


class Channel(str, Enum):
    # Pipeline outputs (one per agent).
    DATA_COLLECTION = "data_collection_results"
    REGULATORY = "regulatory_results"
    CARBON = "carbon_results"
    RISK = "risk_results"
    AUDIT = "audit_results"
    ROI = "roi_results"
    REPORT = "report_results"
    ACTION = "action_results"
    STAKEHOLDER = "stakeholder_results"

    def __str__(self) -> str:
        # Plain-string repr so logs and JSON dumps don't show "Channel.CARBON".
        return self.value


# Dynamic per-dataset channels published by the data collector. These can't
# be enum members because the schema name is runtime data — but centralizing
# the prefixes here keeps the convention discoverable.
def validated_channel(schema_name: str) -> str:
    """Channel name for the validated DataFrame of a single ingested schema."""
    return f"validated_{schema_name}"


def dataset_channel(schema_name: str) -> str:
    """Channel name for the canonicalized dataset payload of a schema."""
    return f"dataset_{schema_name}"
