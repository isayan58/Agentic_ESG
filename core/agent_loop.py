"""Anthropic Claude tool-use loop driving the ESG orchestrator.

Each domain agent's ``execute()`` method is exposed as a Claude tool
(``run_<agent_key>``). Claude decides which tools to call, in what order,
and when the goal is satisfied — sequential or parallel calls are both
supported. Calculations stay deterministic (Python does the arithmetic);
orchestration decisions are LLM-driven.
"""
from __future__ import annotations

import os
from typing import Any, Callable

import anthropic

import config


SYSTEM_PROMPT = """You are the orchestration agent for an ESG analytics pipeline.

Your job: given a goal, decide which domain tools to call, in what order, and
when the goal is satisfied. You have nine ESG domain tools — each wraps a
specialist agent that computes deterministic ESG metrics (Scope 1/2/3
emissions, BRSR/CSRD coverage, climate-risk scores, ROI, audit readiness, and
so on).

How to operate:
- Call tools to make progress. Call multiple tools in parallel in the same
  turn whenever their inputs are independent (for example carbon_accountant
  and regulatory_tracker both only need data_collector — run them together).
- Respect dependencies. Each tool's description lists its prerequisites;
  calling a tool before its prerequisites returns an error.
- Do not re-run a tool that has already completed successfully.
- Compute, then conclude. When the goal is met (or no further tools can
  productively run), stop calling tools and reply with a short summary of
  what you accomplished and any notable findings.
- Keep your reasoning concise and your decisions concrete. The end user
  sees the tool results and your final summary, not your intermediate
  thinking."""


def _summarize_result(agent_key: str, result: Any) -> str:
    if not isinstance(result, dict):
        return f"{agent_key}: completed."
    if "error" in result:
        return f"{agent_key}: ERROR — {result['error']}"
    summarizers = {
        "data_collector": lambda r: (
            f"Ingested {r.get('total_records', 0)} records across "
            f"{len(r.get('datasets') or r.get('quality_scores') or {})} datasets."
        ),
        "regulatory_tracker": lambda r: (
            f"Coverage {r.get('overall_coverage_pct', r.get('coverage_pct', 'n/a'))}%, "
            f"{len(r.get('gaps', []))} gaps identified."
        ),
        "carbon_accountant": lambda r: (
            f"Total emissions {r.get('total_emissions_current', 0)} tCO2e, "
            f"YoY {r.get('yoy_change_pct', r.get('yoy_change', 0))}%."
        ),
        "risk_predictor": lambda r: (
            f"Overall risk score {r.get('overall_risk_score', 0)}/100, "
            f"predicted rating {r.get('predicted_rating', 'n/a')}."
        ),
        "audit_agent": lambda r: (
            f"Readiness grade {(r.get('readiness_score') or {}).get('grade', 'n/a')}."
        ),
        "roi_agent": lambda r: (
            f"Financial ROI {(r.get('financial_roi') or {}).get('roi_pct', 0)}%, "
            f"investment grade {(r.get('investment_quality') or {}).get('grade', 'n/a')}."
        ),
        "report_generator": lambda r: (
            f"Report assembled with {len(r.get('sections', []))} sections "
            f"covering {len(r.get('frameworks', []))} frameworks."
        ),
        "action_agent": lambda r: (
            f"{len(r.get('actions', []))} prioritized actions generated."
        ),
        "stakeholder_agent": lambda r: (
            f"Tailored views generated for {len(r.get('audiences', r.get('views', [])))} audiences."
        ),
    }
    fn = summarizers.get(agent_key)
    if fn:
        try:
            return f"{agent_key}: {fn(result)}"
        except Exception:
            return f"{agent_key}: completed."
    return f"{agent_key}: completed."


def build_tools(orchestrator) -> list[dict]:
    tools: list[dict] = []
    for key in orchestrator.agent_order:
        deps = orchestrator.agent_dependencies.get(key, [])
        deps_text = (
            f" Prerequisites that must complete first: {', '.join(deps)}."
            if deps else " No prerequisites — safe to run first."
        )
        tools.append({
            "name": f"run_{key}",
            "description": f"{orchestrator.agent_descriptions[key]}{deps_text}",
            "input_schema": {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
        })
    return tools


class AnthropicAgentLoop:
    """Drive the orchestrator using a Claude tool-use loop with prompt caching."""

    def __init__(self, orchestrator, model: str | None = None,
                 effort: str | None = None, max_tokens: int | None = None):
        api_key = config.ANTHROPIC_API_KEY or os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not set. The agentic orchestrator requires "
                "an Anthropic API key — set it in the environment before running "
                "the pipeline."
            )
        self.client = anthropic.Anthropic(api_key=api_key)
        self.orchestrator = orchestrator
        self.model = model or config.ANTHROPIC_MODEL
        self.effort = effort or config.ANTHROPIC_EFFORT
        self.max_tokens = max_tokens or config.ANTHROPIC_MAX_TOKENS

    def _execute_tool(self, tool_name: str, tool_input: dict, results: dict,
                      data_collector_kwargs: dict | None,
                      progress_callback: Callable | None, step: int) -> dict:
        if not tool_name.startswith("run_"):
            return {"is_error": True, "content": f"Unknown tool: {tool_name}"}
        agent_key = tool_name[len("run_"):]
        if agent_key not in self.orchestrator.agents:
            return {"is_error": True, "content": f"Unknown agent: {agent_key}"}

        if agent_key in results and "error" not in (results.get(agent_key) or {}):
            return {
                "is_error": False,
                "content": (
                    f"{agent_key} already completed earlier this run — "
                    f"reusing prior result. {_summarize_result(agent_key, results[agent_key])}"
                ),
            }

        if not self.orchestrator._can_run_agent(agent_key, results):
            missing = [
                d for d in self.orchestrator.agent_dependencies.get(agent_key, [])
                if d not in results or "error" in (results.get(d) or {})
            ]
            self.orchestrator.execution_log.append({
                "agent": agent_key, "status": "skipped", "step": step,
                "details": f"Dependencies not met: {', '.join(missing) or 'unknown'}",
            })
            return {
                "is_error": True,
                "content": (
                    f"Cannot run {agent_key} yet — missing prerequisites: "
                    f"{', '.join(missing) or 'unknown'}. Run those first."
                ),
            }

        # Incremental cache: if every upstream input fingerprints to
        # the same value as last time we ran this agent, reuse the
        # cached output instead of paying the runtime again. Falls
        # through cleanly when the cache is empty.
        dep_fingerprint = self.orchestrator.compute_dep_fingerprint(
            agent_key, results, data_collector_kwargs=data_collector_kwargs,
        )
        hit, cached_result = self.orchestrator.lookup_incremental_cache(
            agent_key, dep_fingerprint,
        )
        if hit:
            results[agent_key] = cached_result
            self.orchestrator.record_cache_hit(agent_key)
            self.orchestrator.execution_log.append({
                "agent": agent_key, "status": "cached", "step": step,
                "details": "Inputs unchanged — reused cached result.",
            })
            if progress_callback:
                progress_callback(agent_key, "completed", step,
                                  len(self.orchestrator.agent_order))
            return {
                "is_error": False,
                "content": (
                    f"{agent_key}: reused cached result (inputs unchanged). "
                    f"{_summarize_result(agent_key, cached_result)}"
                ),
            }

        if progress_callback:
            progress_callback(agent_key, "running", step,
                              len(self.orchestrator.agent_order))

        run_kwargs = (data_collector_kwargs or {}) if agent_key == "data_collector" else {}
        agent_results = self.orchestrator.agents[agent_key].run(
            orchestrator=self.orchestrator, **run_kwargs
        )
        results[agent_key] = agent_results
        status = ("completed" if self.orchestrator.agents[agent_key].status == "completed"
                  else "error")
        if status == "completed":
            self.orchestrator.store_incremental_cache(
                agent_key, dep_fingerprint, agent_results,
            )
        self.orchestrator.execution_log.append({
            "agent": agent_key, "status": status, "step": step,
        })
        if progress_callback:
            progress_callback(agent_key, status, step,
                              len(self.orchestrator.agent_order))

        return {
            "is_error": status == "error",
            "content": _summarize_result(agent_key, agent_results),
        }

    def run(self, goal: str, results: dict,
            data_collector_kwargs: dict | None = None,
            progress_callback: Callable | None = None,
            max_iterations: int = 20) -> dict:
        tools = build_tools(self.orchestrator)
        # Cache the tool list and system prompt — they're stable across the
        # entire loop. cache_control on the last tool caches tools+system
        # together (render order: tools → system → messages).
        if tools:
            tools[-1] = {**tools[-1], "cache_control": {"type": "ephemeral"}}
        system = [{
            "type": "text",
            "text": SYSTEM_PROMPT,
            "cache_control": {"type": "ephemeral"},
        }]

        messages: list[dict] = [{
            "role": "user",
            "content": (
                f"Goal: {goal}\n\n"
                "Decide which tools to call to achieve this goal. Call tools "
                "in parallel when their inputs are independent. When the goal "
                "is satisfied, stop calling tools and summarize what you did."
            ),
        }]

        for iteration in range(1, max_iterations + 1):
            with self.client.messages.stream(
                model=self.model,
                max_tokens=self.max_tokens,
                thinking={"type": "adaptive"},
                output_config={"effort": self.effort},
                system=system,
                tools=tools,
                messages=messages,
            ) as stream:
                response = stream.get_final_message()

            tool_use_blocks = [
                b for b in response.content if getattr(b, "type", None) == "tool_use"
            ]
            text_blocks = [
                b.text for b in response.content if getattr(b, "type", None) == "text"
            ]
            tool_names = [b.name for b in tool_use_blocks]
            if tool_names:
                agent_label = ", ".join(n[len("run_"):] if n.startswith("run_") else n
                                        for n in tool_names)
                reason_text = (
                    f"Called {len(tool_names)} tool(s) "
                    f"{'in parallel' if len(tool_names) > 1 else 'sequentially'}."
                )
            else:
                agent_label = "claude-orchestrator"
                reason_text = (" ".join(text_blocks).strip()[:240]
                               or f"Stopped: {response.stop_reason}")
            self.orchestrator.planning_log.append({
                "step": iteration,
                "agent": agent_label,
                "reason": reason_text,
                "stop_reason": response.stop_reason,
                "tool_calls": tool_names,
                "usage": {
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens,
                    "cache_read_input_tokens": getattr(
                        response.usage, "cache_read_input_tokens", 0),
                    "cache_creation_input_tokens": getattr(
                        response.usage, "cache_creation_input_tokens", 0),
                },
            })

            if response.stop_reason == "end_turn" or not tool_use_blocks:
                break

            messages.append({"role": "assistant", "content": response.content})

            tool_results = []
            for block in tool_use_blocks:
                outcome = self._execute_tool(
                    block.name, block.input, results,
                    data_collector_kwargs, progress_callback, iteration,
                )
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": outcome["content"],
                    "is_error": outcome.get("is_error", False),
                })

            messages.append({"role": "user", "content": tool_results})

        return results
