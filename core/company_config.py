"""Dynamic company configuration — the single source of truth for all agents.

Usage:
    from core.company_config import company_cfg

    company_cfg.company_name          # "Acme Corp"
    company_cfg.revenue("current")    # 462  (USD millions)
    company_cfg.thresholds            # ThresholdConfig(...)
    company_cfg.risk_weights          # RiskWeightConfig(...)

Per-user personalisation
------------------------
``company_cfg`` is exposed as a thread-local proxy. Streamlit pages call
:func:`set_active_company_config` (via :func:`utils.session.get_session_company_config`)
at the top of each rerun to swap the proxy to the signed-in user's
profile *for the current thread only*. Other concurrent sessions on the
same Space replica continue to see their own user's config.

Guests (and any code path that doesn't set an active config) fall back
to the bundled ``data/company_profile.json``.
"""
from __future__ import annotations

import contextvars
import json
import logging
import os
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Iterator, Optional


# ── Nested config dataclasses ───────────────────────────────────────────────

@dataclass
class ThresholdConfig:
    """All scoring / grading thresholds used across agents."""
    # Data quality (data_collector)
    completeness_warning: float = 80.0
    completeness_pass: float = 90.0
    confidence_high: float = 80.0
    confidence_medium: float = 60.0
    confidence_audit_ready: float = 75.0
    quality_issue_completeness: float = 90.0
    low_confidence_alert: float = 75.0

    # Source trust bonuses (data_collector)
    source_bonus_real: float = 25.0
    source_bonus_connector: float = 20.0
    source_bonus_sample: float = 10.0
    freshness_bonus: float = 18.0

    # Audit readiness (audit_agent)
    audit_completeness_pass: float = 90.0
    audit_completeness_warning: float = 70.0
    audit_compliance_pass: float = 80.0
    audit_compliance_warning: float = 60.0
    audit_evidence_verifiable: float = 0.8
    audit_grade_a: float = 90.0
    audit_grade_b: float = 75.0
    audit_grade_c: float = 60.0

    # Risk levels (risk_predictor)
    risk_low: float = 30.0
    risk_medium: float = 60.0

    # ESG rating thresholds (risk_predictor)
    rating_a: float = 90.0
    rating_a_minus: float = 80.0
    rating_bbb_plus: float = 70.0
    rating_bbb: float = 60.0

    # Action triggers (action_agent)
    transition_risk_trigger: float = 50.0
    evidence_score_trigger: float = 80.0
    renewable_low_trigger: float = 50.0
    yoy_reduction_insufficient: float = -10.0


@dataclass
class RiskWeightConfig:
    """Weights for the composite climate risk score."""
    physical: float = 0.25
    transition: float = 0.45
    emission: float = 0.30


@dataclass
class AuditWeightConfig:
    """Weights for the audit readiness composite score."""
    completeness: float = 0.30
    compliance: float = 0.40
    evidence: float = 0.30


@dataclass
class ConfidenceWeightConfig:
    """Weights for the dataset confidence composite score."""
    completeness: float = 0.4
    raw_confidence: float = 0.4
    freshness: float = 0.2


@dataclass
class ScenarioConfig:
    """Parameters for the three risk scenarios."""
    best_reduction_pct: float = 35.0
    best_rating: str = "A"
    best_investment: str = "High"
    best_timeline: str = "18-24 months"

    base_reduction_pct: float = 18.0
    base_rating: str = "A-"
    base_investment: str = "Medium"
    base_timeline: str = "12-18 months"

    worst_reduction_pct: float = 5.0
    worst_rating: str = "BBB"
    worst_investment: str = "Low"
    worst_timeline: str = "24+ months"


@dataclass
class SectorRiskDefaults:
    """Default risk scores — override per sector / company."""
    physical_risk: float = 28.0
    physical_risk_detail: str = "Low exposure — primarily office-based operations"
    transition_risk_base: float = 52.0
    emission_risk_base: float = 35.0
    emission_risk_max: float = 80.0
    emission_risk_min: float = 15.0
    emission_risk_midpoint: float = 50.0
    reputational_risk: float = 35.0
    reputational_detail: str = "Strong ESG reporting track record, improving scores"
    supply_chain_risk: float = 55.0
    supply_chain_detail: str = "Exposure through high-emission tier 2/3 suppliers"
    compliance_baseline: float = 75.0
    confidence_cap: float = 95.0
    confidence_boost: float = 10.0


@dataclass
class ActionCostTemplate:
    """Cost / duration templates for action recommendations.

    All cost values are in the company's configured currency unit
    (default: INR lakhs).
    """
    supplier_engagement_cost: float = 50.0
    supplier_engagement_weeks: int = 12
    overdue_audit_cost: float = 25.0
    overdue_audit_weeks: int = 8
    transition_risk_cost: float = 100.0
    transition_risk_weeks: int = 16
    compliance_remediation_cost: float = 15.0
    compliance_remediation_weeks: int = 6
    evidence_documentation_cost: float = 10.0
    evidence_documentation_weeks: int = 8
    renewable_energy_cost: float = 150.0
    renewable_energy_weeks: int = 20
    scope3_supplier_cost: float = 40.0
    scope3_supplier_weeks: int = 16
    solar_installation_cost: float = 200.0
    solar_installation_weeks: int = 24
    regulatory_gap_cost: float = 30.0
    regulatory_gap_weeks: int = 10


# ── Main config class ───────────────────────────────────────────────────────

class CompanyConfig:
    """Loads company_profile.json once and exposes every configurable value.

    Any key missing from the JSON file falls back to a sensible default so
    the platform works out of the box.
    """

    def __init__(self, profile_path: str | None = None,
                 profile_data: dict[str, Any] | None = None):
        """Build a config from either a JSON file path or an in-memory dict.

        ``profile_data`` takes precedence — used by the per-user profile
        store to instantiate a config from JSON loaded out of HF Dataset.
        """
        if profile_data is not None:
            self._raw = dict(profile_data)
        else:
            if profile_path is None:
                profile_path = os.path.join(
                    os.path.dirname(os.path.dirname(__file__)), "data", "company_profile.json"
                )
            self._raw = {}
            if os.path.exists(profile_path):
                with open(profile_path, "r") as f:
                    self._raw = json.load(f)

        # ── Company identity ────────────────────────────────────────────
        self.company_name: str = self._raw.get("company_name", "Your Company")
        self.sector: str = self._raw.get("sector", "General")
        self.sub_sector: str = self._raw.get("sub_sector", "")
        self.headquarters: str = self._raw.get("headquarters", "")
        self.founded: int = self._raw.get("founded", 0)
        self.employees: int = self._raw.get("employees", 0)
        self.offices: list[str] = self._raw.get("offices", [])
        self.operating_countries: list[str] = self._raw.get("operating_countries", [])
        self.listed_exchanges: list[str] = self._raw.get("listed_exchanges", [])

        # ── Financials ──────────────────────────────────────────────────
        self.currency_unit: str = self._raw.get("currency_unit", "INR lakhs")
        rev = self._raw.get("revenue", {})
        self._revenue: dict[str, float] = {
            "current_usd_millions": rev.get("current_usd_millions",
                                            self._raw.get("revenue_usd_millions", 0)),
            "previous_usd_millions": rev.get("previous_usd_millions", 0),
            "current_local": rev.get("current_local",
                                     self._raw.get("revenue_inr_crores", 0)),
            "previous_local": rev.get("previous_local", 0),
        }
        self.market_cap_local: float = self._raw.get("market_cap_inr_crores", 0)

        # ── ESG posture ─────────────────────────────────────────────────
        self.esg_rating_current: str = self._raw.get("esg_rating_current", "NR")
        self.esg_rating_target: str = self._raw.get("esg_rating_target", "")
        self.frameworks_adopted: list[str] = self._raw.get("frameworks_adopted", [])
        self.frameworks_planned: list[str] = self._raw.get("frameworks_planned", [])
        self.key_commitments: list[str] = self._raw.get("key_commitments", [])
        self.material_topics: list[str] = self._raw.get("material_topics", [])

        # ── Reporting years ─────────────────────────────────────────────
        self.report_years: list[int] = self._raw.get(
            "sustainability_report_years", []
        )
        self.current_fy: int = self._raw.get("current_fy", max(self.report_years) if self.report_years else 0)
        self.previous_fy: int = self._raw.get("previous_fy", self.current_fy - 1 if self.current_fy else 0)

        # ── Tunable parameters (nested dataclasses) ─────────────────────
        self.thresholds = self._load_dataclass(ThresholdConfig, "thresholds")
        self.risk_weights = self._load_dataclass(RiskWeightConfig, "risk_weights")
        self.audit_weights = self._load_dataclass(AuditWeightConfig, "audit_weights")
        self.confidence_weights = self._load_dataclass(ConfidenceWeightConfig, "confidence_weights")
        self.scenarios = self._load_dataclass(ScenarioConfig, "scenarios")
        self.sector_risk = self._load_dataclass(SectorRiskDefaults, "sector_risk_defaults")
        self.action_costs = self._load_dataclass(ActionCostTemplate, "action_cost_templates")

    # ── Helper methods ──────────────────────────────────────────────────

    def revenue(self, which: str = "current") -> float:
        """Return revenue in USD millions.  which = 'current' | 'previous'."""
        key = f"{which}_usd_millions"
        return self._revenue.get(key, 0)

    def revenue_local(self, which: str = "current") -> float:
        """Return revenue in local currency."""
        key = f"{which}_local"
        return self._revenue.get(key, 0)

    def commitments_text(self) -> str:
        """Return commitments as a comma-separated string for AI prompts."""
        if self.key_commitments:
            return "; ".join(self.key_commitments)
        return "sustainability commitments to be defined"

    def primary_office(self) -> str:
        """Return the first office name (for action item templates)."""
        return self.offices[0] if self.offices else "primary facility"

    def as_dict(self) -> dict:
        """Return the full raw profile for serialisation / display."""
        return dict(self._raw)

    def _load_dataclass(self, cls, json_key: str):
        """Instantiate a dataclass from the profile JSON, falling back to defaults."""
        overrides = self._raw.get(json_key, {})
        if not isinstance(overrides, dict):
            overrides = {}
        return cls(**{k: v for k, v in overrides.items()
                      if k in cls.__dataclass_fields__})


# ── Context-var proxy + helpers ─────────────────────────────────────────────

_default_cfg = CompanyConfig()
_log = logging.getLogger(__name__)

# ContextVar is preferred over threading.local because:
#   (1) It propagates automatically across asyncio tasks spawned via
#       ``asyncio.create_task`` / ``asyncio.gather``.
#   (2) It can be explicitly propagated into worker threads via
#       ``contextvars.copy_context().run(fn, *args)`` — which
#       ``ThreadPoolExecutor.submit`` does for each submitted task.
#   (3) Nested ``set()`` returns a token that ``reset(token)`` restores,
#       giving clean scoped overrides that threading.local can't express.
_active_cfg: contextvars.ContextVar[Optional[CompanyConfig]] = contextvars.ContextVar(
    "company_cfg_active", default=None,
)

# Set to True in tests / dev to get a log line whenever a thread or
# async task accesses ``company_cfg`` without a binding and falls back
# to the bundled default. Helps catch the "signed-in user silently sees
# default profile" class of regression.
_WARN_ON_DEFAULT_FALLTHROUGH = os.getenv("ESG_COMPANY_CFG_WARN", "").lower() in (
    "1", "true", "yes", "on",
)


class _CompanyConfigProxy:
    """Attribute-forwarding proxy backed by a :class:`contextvars.ContextVar`.

    Every attribute access on ``company_cfg`` resolves to the active
    ``CompanyConfig`` for *this logical execution context* (Streamlit
    script run, asyncio task, thread with an explicitly-copied context).
    Two concurrently-signed-in users on the same Space replica each see
    their own profile without stomping on each other.

    Falls back to the bundled default profile when no active config has
    been set (guests, background jobs, scripts that import an agent
    directly without going through a page). Set ``ESG_COMPANY_CFG_WARN=1``
    to log every fallthrough so regressions that spawn unbound threads
    surface immediately.
    """

    @staticmethod
    def _resolve() -> "CompanyConfig":
        cfg = _active_cfg.get()
        if cfg is None:
            if _WARN_ON_DEFAULT_FALLTHROUGH:
                _log.warning(
                    "company_cfg accessed without an active binding — "
                    "falling back to bundled default profile. If this is a "
                    "signed-in user's code path, the per-user profile will "
                    "NOT be applied."
                )
            return _default_cfg
        return cfg

    def __getattr__(self, name: str) -> Any:
        # __getattr__ is only consulted when the attribute is NOT on the
        # proxy itself, so this safely forwards everything to the active
        # CompanyConfig instance.
        return getattr(self._resolve(), name)

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        cfg = self._resolve()
        return f"<CompanyConfigProxy active={cfg.company_name!r}>"


company_cfg = _CompanyConfigProxy()


def set_active_company_config(cfg: "CompanyConfig | None") -> None:
    """Bind ``cfg`` as the active config for the current context.

    Pass ``None`` to clear the override and revert to the bundled default.
    Safe to call on every Streamlit rerun — cheap, idempotent.

    Under the hood this calls :meth:`ContextVar.set`. Because Streamlit's
    script runner executes each browser-session rerun inside its own
    ``Context``, one user's ``set`` cannot leak into another user's
    rerun even when both run concurrently on the same replica.
    """
    _active_cfg.set(cfg)


@contextmanager
def company_config_context(cfg: "CompanyConfig | None") -> Iterator[None]:
    """Scoped binding for ``cfg`` — restores the previous value on exit.

    Preferred over a bare :func:`set_active_company_config` when you
    need a short-lived override (e.g. rendering one user's view inside
    a background job). Pair with :func:`contextvars.copy_context` when
    spawning worker threads so the binding propagates::

        ctx = contextvars.copy_context()
        executor.submit(ctx.run, worker_fn, *args)

    Without copy_context the submitted thread sees the default config.
    """
    token = _active_cfg.set(cfg)
    try:
        yield
    finally:
        _active_cfg.reset(token)


def get_active_company_config() -> "CompanyConfig":
    """Return the currently-bound config, or the bundled default.

    Useful when code explicitly wants to inspect what ``company_cfg``
    would resolve to without triggering the proxy (e.g. in tests that
    assert on binding state).
    """
    return _active_cfg.get() or _default_cfg


def get_default_company_config() -> "CompanyConfig":
    """Return the bundled default config (read-only — used as a template)."""
    return _default_cfg
