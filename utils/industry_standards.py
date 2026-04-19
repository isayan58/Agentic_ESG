"""Industry-standard benchmark values for ESG-financial metrics.

The Peer Benchmarking section of the ESG ROI Agent compares the user's
company against whatever peer dataset has been uploaded — but peer
comparisons are only as representative as the peer list. A company
whose peer list happens to be underperforming can look like a sector
leader even when it's lagging absolute industry benchmarks.

This module plugs the gap by providing generic, source-cited industry
benchmarks (SBTi 1.5°C pathway, NSE/BSE median, GRI 305-style targets)
that stay constant regardless of the peer upload. The ROI agent
attaches these to each benchmark dict so the UI can render them
alongside the peer-median card.

The values are illustrative defaults — a company with sector-specific
targets set in its profile (``industry_benchmarks`` key) overrides them.
"""
from __future__ import annotations

from typing import Any


# ---------------------------------------------------------------------------
# Generic defaults — broadly-used Indian listed-entity benchmarks. Each
# entry names the metric as it appears on ``benchmarks`` in the ROI
# agent payload.
# ---------------------------------------------------------------------------
_DEFAULT_INDUSTRY_STANDARDS: dict[str, dict[str, Any]] = {
    "esg_score": {
        "value": 70.0,
        "unit": "/100",
        "higher_is_better": True,
        "source": "CRISIL / Sustainalytics median for BSE-100 constituents",
        "interpretation": (
            "Companies rated 70+ are treated as ESG leaders by most "
            "institutional investors and qualify for ESG-themed funds."
        ),
    },
    "ebitda_margin": {
        "value": 18.0,
        "unit": "%",
        "higher_is_better": True,
        "source": "NSE 500 median EBITDA margin (2023, CMIE Prowess)",
        "interpretation": (
            "18% is the broad cross-sector median; capital-light sectors "
            "(IT services, pharma) trend above, heavy-asset sectors below."
        ),
    },
    "roa": {
        "value": 8.0,
        "unit": "%",
        "higher_is_better": True,
        "source": "NSE 500 median RoA (2023, CMIE Prowess)",
        "interpretation": (
            "8% is a healthy cross-sector benchmark; banks and utilities "
            "are structurally below, consumer and tech above."
        ),
    },
    "scope1_2_emissions": {
        # SBTi 1.5°C aligned trajectory expects ~4.2% absolute reduction
        # YoY from a 2019 base; this surfaces the *target direction*, not
        # an absolute cap, so the UI can display a "lower is better"
        # anchor. We keep the value at 0 to communicate "zero is the
        # destination" while the source line explains the path.
        "value": 0.0,
        "unit": " kt",
        "higher_is_better": False,
        "source": "SBTi 1.5°C pathway — ~4.2% YoY absolute reduction",
        "interpretation": (
            "Absolute Scope 1+2 must fall ~4.2% every year to stay aligned "
            "with the 1.5°C pathway. Net-zero by 2050 is the endpoint."
        ),
    },
    "esg_capex_pct": {
        "value": 10.0,
        "unit": "%",
        "higher_is_better": True,
        "source": "CDP 2023 — median ESG-linked CapEx share (large-cap EM)",
        "interpretation": (
            "10% of CapEx earmarked for ESG / climate transition is the "
            "emerging-market large-cap median; 20%+ signals committed leaders."
        ),
    },
}


def get_industry_standard(metric_key: str,
                          overrides: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """Return the industry-standard benchmark for a metric, or ``None``.

    ``overrides`` is an optional dict (typically
    ``company_cfg.industry_benchmarks``) keyed by the same metric names.
    Values in ``overrides`` win over the module defaults — letting a
    company plug in sector-specific targets without editing code.
    """
    overrides = overrides or {}
    user = overrides.get(metric_key)
    if user:
        # Merge on top of the default so unspecified fields (source,
        # interpretation) don't vanish when the user only sets ``value``.
        base = dict(_DEFAULT_INDUSTRY_STANDARDS.get(metric_key, {}))
        base.update({k: v for k, v in user.items() if v is not None})
        return base or None
    return dict(_DEFAULT_INDUSTRY_STANDARDS[metric_key]) \
        if metric_key in _DEFAULT_INDUSTRY_STANDARDS else None


def compute_gap_vs_standard(metric_key: str,
                            company_value: float,
                            overrides: dict[str, Any] | None = None
                            ) -> dict[str, Any] | None:
    """Return a rich comparison of ``company_value`` vs the industry standard.

    ``None`` when no standard is known for this metric.
    """
    std = get_industry_standard(metric_key, overrides)
    if std is None:
        return None
    value = float(std.get("value", 0) or 0)
    gap = round(company_value - value, 2)
    higher = bool(std.get("higher_is_better", True))
    if gap == 0:
        position = "Meets the industry standard"
    elif (gap > 0 and higher) or (gap < 0 and not higher):
        position = f"**Above** the industry standard by {abs(gap):g}{std.get('unit','')}"
    else:
        position = f"**Below** the industry standard by {abs(gap):g}{std.get('unit','')}"
    return {
        "value":           value,
        "unit":            std.get("unit", ""),
        "source":          std.get("source", ""),
        "interpretation":  std.get("interpretation", ""),
        "gap":             gap,
        "position":        position,
        "higher_is_better": higher,
    }
