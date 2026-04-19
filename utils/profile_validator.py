"""Profile schema validation.

Users can paste arbitrary JSON into the Settings "Advanced" tab, which
used to save unconditionally and then crash the next page load when
``CompanyConfig(profile_data=…)`` hit an unexpected shape. This module
gives the Settings page a cheap structural check *before* the write
commits, so a bad paste surfaces a clear error banner instead of being
discovered as a stack trace on an unrelated page.

Design notes
------------
* Not a full JSON-Schema validator — just the keys ``CompanyConfig`` and
  its dataclasses actually read. Keeping this in-house avoids pulling in
  ``pydantic`` / ``jsonschema`` for one form.
* Unknown keys are allowed (forward-compatible). Only known keys are
  type-checked.
* Returns a list of human-readable errors so the UI can render all of
  them at once rather than revealing one at a time.
"""
from __future__ import annotations

from typing import Any


# Keys at the top level of the profile, with their expected Python types.
# ``tuple`` values mean "any of these types is acceptable" (e.g. ints
# that might also arrive as floats via ``st.number_input``).
_TOP_LEVEL_TYPES: dict[str, type | tuple[type, ...]] = {
    "company_name": str,
    "sector": str,
    "sub_sector": str,
    "headquarters": str,
    "founded": (int, float),
    "employees": (int, float),
    "offices": list,
    "operating_countries": list,
    "listed_exchanges": list,
    "currency_unit": str,
    "revenue": dict,
    "market_cap_inr_crores": (int, float),
    "current_fy": (int, float),
    "previous_fy": (int, float),
    "esg_rating_current": str,
    "esg_rating_target": str,
    "frameworks_adopted": list,
    "frameworks_planned": list,
    "key_commitments": list,
    "material_topics": list,
    "sustainability_report_years": list,
    "thresholds": dict,
    "risk_weights": dict,
    "audit_weights": dict,
    "confidence_weights": dict,
    "scenarios": dict,
    "sector_risk_defaults": dict,
    "action_cost_templates": dict,
}

# Keys inside ``revenue`` — each must be numeric if present.
_REVENUE_NUMERIC_KEYS = (
    "current_usd_millions",
    "previous_usd_millions",
    "current_local",
    "previous_local",
)

# Upper bound on the serialised size of a single profile — guards against
# someone pasting a multi-MB blob into the Advanced tab.
MAX_PROFILE_BYTES = 256 * 1024  # 256 KB


def validate_profile(profile: Any) -> list[str]:
    """Return a list of validation errors (empty list == valid).

    The profile is considered valid if:
      1. It's a ``dict``.
      2. Each known top-level key matches its expected type.
      3. ``revenue`` (if present) is a dict of numeric values.
      4. Every list-typed key contains only strings (agents format them
         into narratives — non-string members would break rendering).
      5. Total JSON-serialised size is under :data:`MAX_PROFILE_BYTES`.
    """
    errors: list[str] = []

    if not isinstance(profile, dict):
        return [
            f"Profile must be a JSON object, got {type(profile).__name__}."
        ]

    # Size guard — compute here rather than in the caller so every
    # callsite gets the check for free.
    try:
        import json as _json
        payload = _json.dumps(profile, ensure_ascii=False)
        if len(payload.encode("utf-8")) > MAX_PROFILE_BYTES:
            errors.append(
                f"Profile is too large ({len(payload):,} chars; "
                f"cap {MAX_PROFILE_BYTES:,}). Trim free-text fields or "
                "move bulky lists into external references."
            )
    except (TypeError, ValueError) as exc:
        errors.append(f"Profile is not JSON-serialisable: {exc}")

    # Type check known top-level keys.
    for key, expected in _TOP_LEVEL_TYPES.items():
        if key not in profile:
            continue
        value = profile[key]
        if not isinstance(value, expected):
            exp_name = (
                expected.__name__ if isinstance(expected, type)
                else " | ".join(t.__name__ for t in expected)
            )
            errors.append(
                f"`{key}` must be {exp_name}, got {type(value).__name__}."
            )
            continue
        # Members of list fields must be strings — agents stitch them
        # into prompts unchanged, so a dict in the middle would break
        # rendering in hard-to-debug ways.
        if isinstance(value, list):
            for i, item in enumerate(value):
                if not isinstance(item, str):
                    errors.append(
                        f"`{key}[{i}]` must be str, got "
                        f"{type(item).__name__}."
                    )
                    break  # one complaint per list is enough

    # Revenue sub-keys are numeric if present.
    revenue = profile.get("revenue")
    if isinstance(revenue, dict):
        for rkey in _REVENUE_NUMERIC_KEYS:
            if rkey in revenue and not isinstance(revenue[rkey], (int, float)):
                errors.append(
                    f"`revenue.{rkey}` must be a number, got "
                    f"{type(revenue[rkey]).__name__}."
                )

    return errors
