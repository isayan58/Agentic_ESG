"""Roll the ESG metric set up from business-unit rows to reportable metrics.

``esg_metrics`` stores one row per metric *per business unit* — 75 base
metrics across 99 units, ~7,400 rows. Those rows are correct in aggregate
but meaningless individually: values are apportioned across units, so a
single row reads "Board Size — Refinery Hazira = 0.053". Anything that
shows metrics to a human has to roll them up first.

The one thing a roll-up must not get wrong is how it combines the rows,
and the honest answer depends on how the source apportions them.

In this dataset every metric is apportioned additively across units —
percentages included. Per-unit renewable share reads 0.07–0.62, i.e.
*shares of* the 31% company figure, not each unit's own percentage. So
summing reconstructs the entity value and averaging divides it by 99,
which is how "31% renewable" becomes "0.31%".

A real client export usually does the opposite for bounded metrics: each
unit reports its own true percentage, and summing 99 units at 40% gives
3,960%. Neither rule is safe alone, so bounded units carry a natural
ceiling: sum first, and fall back to the mean only when the sum breaks
that ceiling — the signal that the source reports true per-unit values
rather than shares. Unbounded units (tCO2e, headcount, rupees) always sum.
"""
from __future__ import annotations

import pandas as pd

# Units with no natural upper bound — these always sum.
ADDITIVE_UNITS = {
    "tCO2e", "MT", "ML", "MWh", "kg", "ha", "count", "hrs",
    "INR_Cr", "INR_Lakhs",
}

# Bounded units and the ceiling a single entity's value cannot exceed.
# Sum unless the total breaks the ceiling; then the rows are per-unit
# readings rather than apportioned shares, and the mean is correct.
UNIT_CEILINGS = {
    "%": 100.0,
    "0-100": 100.0,
    "ratio": 10.0,
    "per_mn_hrs": 50.0,
    "meetings/yr": 52.0,
    "MWh/Cr": 5_000.0,
    "tCO2e/Cr": 5_000.0,
}

_VALUE_COLS = ("value_2023", "value_2024", "target_2024")

# Share of business units that must hit target for the rolled-up metric to
# read as Met / On Track. Stated as constants so the thresholds behind a
# colour are visible in the UI rather than implied.
ATTAINMENT_MET = 75.0
ATTAINMENT_ON_TRACK = 50.0


def is_additive(unit: object) -> bool:
    """True when a metric's values have no bound and always sum."""
    return str(unit or "").strip() in ADDITIVE_UNITS


def aggregate_values(series: pd.Series, unit: object) -> tuple[float | None, str]:
    """Combine per-business-unit values. Returns ``(value, how)``."""
    clean = series.dropna()
    if clean.empty:
        return None, "none"
    unit = str(unit or "").strip()
    total = float(clean.sum())
    if unit in ADDITIVE_UNITS or unit not in UNIT_CEILINGS:
        return total, "sum"
    ceiling = UNIT_CEILINGS[unit]
    if total <= ceiling:
        return total, "sum"
    return float(clean.mean()), "average"


def base_metric_name(name: object) -> str:
    """Strip the ' — <business unit>' suffix from a metric name."""
    return str(name or "").split("—")[0].strip()


def rollup_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """Collapse per-business-unit rows into one row per metric.

    Returns a frame with the aggregated values plus the context a reader
    needs to trust them: how many business units contributed, how many met
    their target, the frameworks the metric feeds, and mean confidence.
    """
    if df is None or df.empty:
        return pd.DataFrame()

    work = df.copy()
    if "metric_name" not in work.columns:
        return pd.DataFrame()
    work["base_metric"] = work["metric_name"].map(base_metric_name)

    for col in _VALUE_COLS:
        if col in work.columns:
            work[col] = pd.to_numeric(work[col], errors="coerce")

    rows: list[dict] = []
    group_keys = ["pillar", "metric_id", "base_metric"]
    group_keys = [k for k in group_keys if k in work.columns]
    if not group_keys:
        return pd.DataFrame()

    for keys, grp in work.groupby(group_keys, dropna=False):
        keys = keys if isinstance(keys, tuple) else (keys,)
        record = dict(zip(group_keys, keys))
        unit = grp["unit"].dropna().iloc[0] if "unit" in grp and grp["unit"].notna().any() else ""

        # Pick the method once, from the current-year column, then apply it to
        # every column. Letting each column choose independently could average
        # one year and sum another, which would make the YoY change and the
        # comparison against target meaningless.
        how = "sum"
        if "value_2024" in grp.columns:
            _, how_probe = aggregate_values(grp["value_2024"], unit)
            if how_probe != "none":
                how = how_probe

        for col in _VALUE_COLS:
            if col in grp.columns:
                clean = pd.to_numeric(grp[col], errors="coerce").dropna()
                if clean.empty:
                    record[col] = None
                else:
                    record[col] = float(clean.mean() if how == "average" else clean.sum())

        record["unit"] = unit
        record["aggregation"] = how
        record["category"] = (grp["category"].dropna().iloc[0]
                              if "category" in grp and grp["category"].notna().any() else "")
        record["business_units"] = int(grp.shape[0])

        # Status is computed per business unit upstream, and already accounts
        # for whether higher or lower is better on that metric. Counting those
        # verdicts is more trustworthy than re-deriving direction here.
        if "status" in grp.columns:
            counts = grp["status"].dropna().value_counts()
            record["met_count"] = int(counts.get("Met", 0))
            record["on_track_count"] = int(counts.get("On Track", 0))
            record["not_met_count"] = int(counts.get("Not Met", 0))
        else:
            record["met_count"] = record["on_track_count"] = record["not_met_count"] = 0

        # Roll the per-unit verdicts up on how *widely* the target is met.
        #
        # The obvious rule — take the most common verdict — is quietly wrong.
        # Across a three-way split "Met" takes the plurality at about 46%, so
        # every metric came out "Met" even where fewer than half the units hit
        # target: a solid green dashboard over mediocre performance. Grading on
        # the share that actually met it keeps the summary honest and matches
        # what the ranked chart shows.
        total_units = int(grp.shape[0]) or 1
        attainment = 100.0 * record["met_count"] / total_units
        record["attainment"] = round(attainment, 1)
        if "status" not in grp.columns or grp["status"].dropna().empty:
            record["status"] = "—"
        elif attainment >= ATTAINMENT_MET:
            record["status"] = "Met"
        elif attainment >= ATTAINMENT_ON_TRACK:
            record["status"] = "On Track"
        else:
            record["status"] = "Not Met"

        prev, cur = record.get("value_2023"), record.get("value_2024")
        record["yoy_change_pct"] = (
            round(100 * (cur - prev) / prev, 1)
            if prev not in (None, 0) and cur is not None else None
        )

        if "framework_tags" in grp.columns:
            tags = {
                t.strip()
                for s in grp["framework_tags"].dropna().astype(str)
                for t in s.split(",") if t.strip()
            }
            record["frameworks"] = ", ".join(sorted(tags))
        else:
            record["frameworks"] = ""

        if "confidence" in grp.columns:
            conf = pd.to_numeric(grp["confidence"], errors="coerce").dropna()
            record["confidence"] = round(float(conf.mean()), 2) if not conf.empty else None
        else:
            record["confidence"] = None

        rows.append(record)

    out = pd.DataFrame(rows)
    if "metric_id" in out.columns:
        out = out.sort_values("metric_id").reset_index(drop=True)
    return out


def display_table(rolled: pd.DataFrame) -> pd.DataFrame:
    """Rename a rolled-up frame to the columns a reader should see."""
    if rolled is None or rolled.empty:
        return pd.DataFrame()
    cols = {
        "metric_id": "ID",
        "base_metric": "Metric",
        "category": "Category",
        "unit": "Unit",
        "value_2023": "FY23",
        "value_2024": "FY24",
        "target_2024": "Target",
        "yoy_change_pct": "YoY %",
        "status": "Status",
        "met_count": "BUs met",
        "business_units": "BUs",
        "frameworks": "Feeds frameworks",
        "confidence": "Confidence",
    }
    present = {k: v for k, v in cols.items() if k in rolled.columns}
    out = rolled[list(present)].rename(columns=present)
    for c in ("FY23", "FY24", "Target"):
        if c in out.columns:
            out[c] = out[c].map(lambda v: round(v, 2) if isinstance(v, (int, float)) else v)
    return out
