"""Per-run token and cost guardrail for the orchestrator's LLM loop.

A long-running tool-use loop with Opus can quietly burn through tokens
(and dollars) when the model gets stuck deciding what to do. ``RunBudget``
caps both axes — exceed either and the loop surfaces ``BudgetExceededError``
instead of grinding on indefinitely.

Cost estimation
---------------
Anthropic public list prices are baked in below as a fallback so callers can
just hand in the ``response.usage`` block. Override via the ``ANTHROPIC_*``
environment variables when negotiated rates differ. All prices in USD per
million tokens.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any


class BudgetExceededError(RuntimeError):
    """Raised when a run exceeds its token or cost cap."""


# USD per million tokens. Loosely tracking Anthropic's public list prices —
# cached read is the standard 10% discount, cache-creation the standard 25%
# premium. Override per-deployment via env if you have negotiated rates.
_DEFAULT_RATES_USD_PER_MTOK: dict[str, dict[str, float]] = {
    "claude-opus-4-7":    {"input": 15.0, "output": 75.0},
    "claude-opus-4-6":    {"input": 15.0, "output": 75.0},
    "claude-sonnet-4-6":  {"input": 3.0,  "output": 15.0},
    "claude-sonnet-4-5":  {"input": 3.0,  "output": 15.0},
    "claude-haiku-4-5":   {"input": 1.0,  "output": 5.0},
}
_FALLBACK_RATES = {"input": 3.0, "output": 15.0}  # Sonnet-ish, when model unknown


def _rates_for(model: str) -> dict[str, float]:
    """Return per-Mtok rates for ``model``, honoring env overrides.

    Env keys ``ANTHROPIC_PRICE_INPUT`` / ``ANTHROPIC_PRICE_OUTPUT`` (USD per
    Mtok) globally override every model. Useful for self-hosted or
    negotiated rates.
    """
    env_in = os.environ.get("ANTHROPIC_PRICE_INPUT")
    env_out = os.environ.get("ANTHROPIC_PRICE_OUTPUT")
    if env_in or env_out:
        base = _DEFAULT_RATES_USD_PER_MTOK.get(model, _FALLBACK_RATES)
        return {
            "input":  float(env_in)  if env_in  else base["input"],
            "output": float(env_out) if env_out else base["output"],
        }
    return _DEFAULT_RATES_USD_PER_MTOK.get(model, _FALLBACK_RATES)


def estimate_cost(usage: Any, model: str) -> float:
    """Estimate USD cost for a single ``response.usage`` block.

    Accepts either an Anthropic SDK usage object or a plain dict with the
    same field names. Cache-read tokens are billed at 10% of input, cache-
    creation at 125% — matching Anthropic's published prompt-caching prices.
    """
    def _get(name: str) -> int:
        if isinstance(usage, dict):
            return int(usage.get(name) or 0)
        return int(getattr(usage, name, 0) or 0)

    input_tok = _get("input_tokens")
    output_tok = _get("output_tokens")
    cache_read = _get("cache_read_input_tokens")
    cache_write = _get("cache_creation_input_tokens")

    rates = _rates_for(model)
    in_rate = rates["input"] / 1_000_000
    out_rate = rates["output"] / 1_000_000

    # Plain input + output. The SDK's ``input_tokens`` already excludes
    # cached reads/writes, so we bill cache_* separately.
    cost = input_tok * in_rate + output_tok * out_rate
    cost += cache_read * in_rate * 0.10
    cost += cache_write * in_rate * 1.25
    return cost


@dataclass
class RunBudget:
    """Cumulative token + cost guardrail for one orchestrator run.

    Default caps are conservative enough to fail fast on a runaway loop
    without hampering a real ESG run on Opus. Tune per workload.
    """

    max_tokens: int = 200_000
    max_cost_usd: float = 5.0
    tokens_used: int = field(default=0, init=False)
    cost_usd: float = field(default=0.0, init=False)
    iterations: int = field(default=0, init=False)

    def add_usage(self, usage: Any, model: str) -> None:
        """Account a single LLM response toward the budget; raise if exceeded.

        Caller hands in the SDK's ``response.usage`` and the model name —
        we compute the dollar cost in one place so call sites stay
        provider-agnostic.
        """
        def _get(name: str) -> int:
            if isinstance(usage, dict):
                return int(usage.get(name) or 0)
            return int(getattr(usage, name, 0) or 0)

        self.tokens_used += _get("input_tokens") + _get("output_tokens")
        self.tokens_used += _get("cache_read_input_tokens")
        self.tokens_used += _get("cache_creation_input_tokens")
        self.cost_usd += estimate_cost(usage, model)
        self.iterations += 1

        if self.tokens_used > self.max_tokens:
            raise BudgetExceededError(
                f"Token budget exceeded: {self.tokens_used:,} > "
                f"{self.max_tokens:,} after {self.iterations} iterations."
            )
        if self.cost_usd > self.max_cost_usd:
            raise BudgetExceededError(
                f"Cost budget exceeded: ${self.cost_usd:.2f} > "
                f"${self.max_cost_usd:.2f} after {self.iterations} iterations."
            )

    def snapshot(self) -> dict[str, float | int]:
        return {
            "tokens_used": self.tokens_used,
            "cost_usd": round(self.cost_usd, 4),
            "iterations": self.iterations,
            "max_tokens": self.max_tokens,
            "max_cost_usd": self.max_cost_usd,
        }
