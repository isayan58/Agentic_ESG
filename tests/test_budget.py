import pytest

from core.budget import BudgetExceededError, RunBudget, estimate_cost


def _usage(input_tokens=0, output_tokens=0,
           cache_read_input_tokens=0, cache_creation_input_tokens=0):
    """Plain-dict usage stub matching the SDK's attribute shape."""
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cache_read_input_tokens": cache_read_input_tokens,
        "cache_creation_input_tokens": cache_creation_input_tokens,
    }


class TestEstimateCost:
    def test_known_model_uses_table_rates(self):
        # Sonnet 4.6: $3/Mtok in, $15/Mtok out — 1k in + 1k out = $0.003 + $0.015
        c = estimate_cost(_usage(input_tokens=1000, output_tokens=1000),
                          model="claude-sonnet-4-6")
        assert c == pytest.approx(0.018, rel=1e-3)

    def test_unknown_model_uses_fallback(self):
        c = estimate_cost(_usage(input_tokens=1_000_000), model="gpt-something")
        # Fallback in-rate $3/Mtok → $3 for 1M input.
        assert c == pytest.approx(3.0, rel=1e-3)

    def test_cache_read_billed_at_10_pct(self):
        c = estimate_cost(
            _usage(cache_read_input_tokens=1_000_000),
            model="claude-sonnet-4-6",
        )
        # 1M cache-read at 10% of $3/Mtok = $0.30
        assert c == pytest.approx(0.30, rel=1e-3)

    def test_cache_write_billed_at_125_pct(self):
        c = estimate_cost(
            _usage(cache_creation_input_tokens=1_000_000),
            model="claude-sonnet-4-6",
        )
        # 1M cache-write at 125% of $3/Mtok = $3.75
        assert c == pytest.approx(3.75, rel=1e-3)

    def test_env_override_wins(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_PRICE_INPUT", "10")
        monkeypatch.setenv("ANTHROPIC_PRICE_OUTPUT", "50")
        c = estimate_cost(_usage(input_tokens=1_000_000, output_tokens=1_000_000),
                          model="claude-sonnet-4-6")
        assert c == pytest.approx(60.0, rel=1e-3)


class TestRunBudget:
    def test_under_cap_does_not_raise(self):
        b = RunBudget(max_tokens=100, max_cost_usd=1.0)
        b.add_usage(_usage(input_tokens=10, output_tokens=10),
                    model="claude-sonnet-4-6")
        assert b.tokens_used == 20
        assert b.iterations == 1

    def test_token_cap_raises(self):
        b = RunBudget(max_tokens=50, max_cost_usd=1000.0)
        with pytest.raises(BudgetExceededError, match="Token budget"):
            b.add_usage(_usage(input_tokens=100), model="claude-sonnet-4-6")

    def test_cost_cap_raises(self):
        b = RunBudget(max_tokens=10**12, max_cost_usd=0.01)
        # 1M output tokens on Sonnet = $15, well over $0.01.
        with pytest.raises(BudgetExceededError, match="Cost budget"):
            b.add_usage(_usage(output_tokens=1_000_000),
                        model="claude-sonnet-4-6")

    def test_cumulative_across_calls(self):
        b = RunBudget(max_tokens=300, max_cost_usd=1000.0)
        b.add_usage(_usage(input_tokens=100), model="claude-sonnet-4-6")
        b.add_usage(_usage(input_tokens=100), model="claude-sonnet-4-6")
        with pytest.raises(BudgetExceededError):
            b.add_usage(_usage(input_tokens=200), model="claude-sonnet-4-6")
        # State after the breach reflects the over-cap accounting.
        assert b.tokens_used == 400
        assert b.iterations == 3

    def test_snapshot_shape(self):
        b = RunBudget(max_tokens=1000, max_cost_usd=1.0)
        b.add_usage(_usage(input_tokens=100, output_tokens=50),
                    model="claude-sonnet-4-6")
        snap = b.snapshot()
        assert set(snap.keys()) == {
            "tokens_used", "cost_usd", "iterations", "max_tokens", "max_cost_usd",
        }
        assert snap["iterations"] == 1
        assert snap["tokens_used"] == 150
