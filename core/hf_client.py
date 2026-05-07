"""HuggingFace Inference API client with fallback to mock responses."""
import json
import re
import requests
import time
from config import HF_API_TOKEN, HF_API_URL, MODELS


def _extract_numbers(prompt):
    """Pull labelled numeric context out of a prompt so fallback narratives can
    reference the actual figures each agent computed (rather than canned text)."""
    nums = {}
    patterns = {
        "scope1": r"Scope 1[:\s]+([\d,.]+)",
        "scope2": r"Scope 2[:\s]+([\d,.]+)",
        "scope3": r"Scope 3[:\s]+([\d,.]+)",
        "yoy": r"[Yy]ear[- ]over[- ]year change[:\s]+(-?[\d.]+)",
        "intensity": r"[Cc]arbon intensity[:\s]+([\d.]+)",
        "risk_score": r"risk score[:\s]+([\d.]+)/100",
        "physical": r"[Pp]hysical risk[:\s]+([\d.]+)",
        "transition": r"[Tt]ransition risk[:\s]+([\d.]+)",
        "rating_curr": r"[Cc]urrent ESG rating[:\s]+([A-Z+\-]+)",
        "rating_pred": r"[Pp]redicted[:\s]+([A-Z+\-]+)",
        "high_risk_suppliers": r"[Hh]igh-risk suppliers[:\s]+(\d+)",
        "compliance": r"compliance[:\s]+([\d.]+)%",
        "roi_pct": r"ROI[:\s]+([\d.]+)%",
        "iqs_grade": r"investment quality[^:]*:\s*([A-Z+\-]+)",
        "total_actions": r"[Tt]otal actions[:\s]+(\d+)",
        "critical": r"[Cc]ritical[:\s]+(\d+)",
        "total_emissions": r"(?:[Tt]otal emissions|[Cc]arbon emissions|total_emissions|[Cc]arbon)[:=\s]+(\d[\d,.]*\d|\d)",
    }
    for k, pat in patterns.items():
        m = re.search(pat, prompt)
        if m:
            nums[k] = m.group(1)
    company = re.search(r"for ([A-Z][\w &.]+?)(?:'s|\.|,)", prompt)
    if company:
        nums["company"] = company.group(1).strip()
    return nums


class HFClient:
    """Wrapper around HuggingFace Inference API with graceful fallback."""

    def __init__(self):
        self.token = HF_API_TOKEN
        self.headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}
        self._available = None

    @property
    def is_available(self):
        if self._available is None:
            if not self.token:
                self._available = False
            else:
                try:
                    resp = requests.post(
                        f"{HF_API_URL}/{MODELS['sentiment_analysis']}",
                        headers=self.headers,
                        json={"inputs": "test"},
                        timeout=10,
                    )
                    self._available = resp.status_code == 200
                except Exception:
                    self._available = False
        return self._available

    def _call_api(self, model_key, payload, retries=2):
        model = MODELS.get(model_key, model_key)
        url = f"{HF_API_URL}/{model}"

        for attempt in range(retries + 1):
            try:
                resp = requests.post(
                    url, headers=self.headers, json=payload, timeout=30
                )
                if resp.status_code == 200:
                    return resp.json()
                if resp.status_code == 503:
                    time.sleep(2 ** attempt)
                    continue
                return None
            except Exception:
                if attempt < retries:
                    time.sleep(1)
                    continue
                return None
        return None

    def generate_text(self, prompt, max_tokens=300, agent=None):
        if not self.is_available:
            return self._fallback_generate(prompt, agent=agent)

        payload = {
            "inputs": prompt,
            "parameters": {
                "max_new_tokens": max_tokens,
                "temperature": 0.7,
                "return_full_text": False,
            },
        }
        result = self._call_api("text_generation", payload)
        if result and isinstance(result, list) and len(result) > 0:
            return result[0].get("generated_text", "").strip()
        return self._fallback_generate(prompt, agent=agent)

    def summarize(self, text, max_length=150):
        if not self.is_available:
            return self._fallback_summarize(text)

        payload = {
            "inputs": text[:1024],
            "parameters": {"max_length": max_length, "min_length": 30},
        }
        result = self._call_api("summarization", payload)
        if result and isinstance(result, list) and len(result) > 0:
            return result[0].get("summary_text", "").strip()
        return self._fallback_summarize(text)

    def classify(self, text, labels):
        if not self.is_available:
            return self._fallback_classify(text, labels)

        payload = {
            "inputs": text,
            "parameters": {"candidate_labels": labels},
        }
        result = self._call_api("zero_shot_classification", payload)
        if result and "labels" in result:
            return {
                label: score
                for label, score in zip(result["labels"], result["scores"])
            }
        return self._fallback_classify(text, labels)

    def analyze_sentiment(self, text):
        if not self.is_available:
            return self._fallback_sentiment(text)

        payload = {"inputs": text[:512]}
        result = self._call_api("sentiment_analysis", payload)
        if result and isinstance(result, list) and len(result) > 0:
            top = result[0]
            if isinstance(top, list):
                top = top[0]
            return {"label": top.get("label", "NEUTRAL"), "score": top.get("score", 0.5)}
        return self._fallback_sentiment(text)

    # --- Fallback methods (rule-based / pre-computed) ---

    def _fallback_generate(self, prompt, agent=None):
        """Agent-specific fallback that pulls real numbers from the prompt so
        each agent's narrative reflects its own computation, not boilerplate."""
        ctx = _extract_numbers(prompt)
        prompt_lower = prompt.lower()

        if agent is None:
            if "carbon accounting" in prompt_lower or "scope 1" in prompt_lower:
                agent = "carbon_accountant"
            elif "risk assessment" in prompt_lower:
                agent = "risk_predictor"
            elif "stakeholder" in prompt_lower or "investor" in prompt_lower:
                agent = "stakeholder_agent"
            elif "audit" in prompt_lower:
                agent = "audit_agent"
            elif "regulatory" in prompt_lower or "compliance gap" in prompt_lower:
                agent = "regulatory_tracker"
            elif "implementation" in prompt_lower or "roadmap" in prompt_lower or "action item" in prompt_lower:
                agent = "action_agent"
            elif "executive summary" in prompt_lower or "annual report" in prompt_lower:
                agent = "report_generator"
            elif "roi" in prompt_lower or "investment quality" in prompt_lower:
                agent = "roi_agent"
            elif "environmental" in prompt_lower or "social" in prompt_lower or "governance" in prompt_lower:
                agent = "report_section"

        company = ctx.get("company", "the company")
        builder_name = self._FALLBACK_BUILDERS.get(agent, "_fallback_generic")
        return getattr(self, builder_name)(prompt, ctx, company)

    def _fallback_carbon(self, prompt, ctx, company):
        s1, s2, s3 = ctx.get("scope1", "?"), ctx.get("scope2", "?"), ctx.get("scope3", "?")
        yoy = ctx.get("yoy", "0")
        intensity = ctx.get("intensity", "?")
        try:
            yoy_f = float(yoy)
            direction = "increase" if yoy_f > 0 else "reduction"
            yoy_disp = f"{abs(yoy_f)}"
        except ValueError:
            direction, yoy_disp = "shift", yoy
        return (
            f"Carbon Accountant — {company}: Scope 1 stands at {s1} tCO2e (direct operations), "
            f"Scope 2 at {s2} tCO2e (purchased energy), and Scope 3 at {s3} tCO2e (value chain). "
            f"YoY footprint shows a {yoy_disp}% {direction}, with carbon intensity of {intensity} tCO2e per $M revenue. "
            f"Scope 3 is the dominant lever — supplier engagement and renewable PPA expansion are the highest-impact next moves."
        )

    def _fallback_risk(self, prompt, ctx, company):
        score = ctx.get("risk_score", "?")
        phys = ctx.get("physical", "?")
        trans = ctx.get("transition", "?")
        cur, pred = ctx.get("rating_curr", "?"), ctx.get("rating_pred", "?")
        sup = ctx.get("high_risk_suppliers", "0")
        return (
            f"Risk Predictor — {company}: composite ESG risk score is {score}/100, "
            f"with physical risk at {phys} and transition risk at {trans}. "
            f"Current MSCI-style rating: {cur}; trajectory points to {pred} as remediation actions land. "
            f"{sup} supplier(s) sit in the high-risk tier and warrant prioritised audits within the next quarter."
        )

    def _fallback_stakeholder(self, prompt, ctx, company):
        return (
            f"Stakeholder Note — {company}: the most recent reporting cycle shows measurable "
            f"progress across environmental, social, and governance pillars, with carbon intensity "
            f"moving favourably and compliance posture strengthening across BRSR, GRI, and SASB. "
            f"We continue to engage suppliers, employees, regulators, and investors with transparent, "
            f"audit-grade disclosures aligned to long-term value creation."
        )

    def _fallback_audit(self, prompt, ctx, company):
        comp = ctx.get("compliance", "?")
        return (
            f"Audit Agent — {company}: overall compliance posture sits at {comp}%. "
            f"Evidence completeness and traceability are the leading gating items for assurance readiness. "
            f"Scope 3 coverage and supplier audit closure remain the highest-leverage remediation tracks "
            f"ahead of the next assurance cycle."
        )

    def _fallback_regulatory(self, prompt, ctx, company):
        comp = ctx.get("compliance", "?")
        return (
            f"Regulatory Tracker — {company}: aggregate framework coverage is {comp}%. "
            f"BRSR (India) and CSRD (EU) drive the largest residual gap set; GRI and SASB are "
            f"comparatively well-served by existing disclosures. Sequencing critical gaps first "
            f"protects the next reporting deadline."
        )

    def _fallback_action(self, prompt, ctx, company):
        total = ctx.get("total_actions", "?")
        crit = ctx.get("critical", "0")
        return (
            f"Action Agent — {company}: roadmap consolidates {total} prioritised initiatives, "
            f"of which {crit} are flagged Critical and require sponsorship in the current quarter. "
            f"Phased rollout is recommended where implementation friction is high; accelerated rollout "
            f"is reserved for low-friction, high-net-value items."
        )

    def _fallback_action_item(self, prompt, ctx, company):
        m = re.search(r"action item:\s*'([^']+)'", prompt)
        title = m.group(1) if m else "this initiative"
        cat = re.search(r"Category:\s*([\w &]+)", prompt)
        weeks = re.search(r"Duration:\s*(\d+)", prompt)
        net = re.search(r"Net ROI[^:]*:\s*([\d.\-]+)", prompt)
        return (
            f"Initiative '{title}' (category: {cat.group(1) if cat else 'ESG'}) is a "
            f"{weeks.group(1) if weeks else 'multi'}-week programme with a projected net ROI of "
            f"{net.group(1) if net else 'positive'}% after implementation friction. "
            f"Sequence with cross-functional ownership across sustainability, finance, and operations."
        )

    def _fallback_report(self, prompt, ctx, company):
        emis = ctx.get("total_emissions")
        yoy = ctx.get("yoy")
        comp = ctx.get("compliance", "—")
        roi = ctx.get("roi_pct", "—")
        iqs = ctx.get("iqs_grade", "N/A")
        if emis:
            yoy_clause = f" ({yoy}% YoY)" if yoy else ""
            emissions_clause = f"total emissions of {emis} tCO2e{yoy_clause}"
        else:
            emissions_clause = "emissions data still being consolidated"
        return (
            f"{company} closed the reporting period with {emissions_clause} "
            f"and aggregate regulatory compliance at {comp}%. "
            f"ESG-linked financial ROI delivered {roi}% with an investment-quality grade of {iqs}, "
            f"signalling that sustainability spend is creating measurable enterprise value. "
            f"The forward agenda prioritises Scope 3 visibility, BRSR readiness, and capital-efficient decarbonisation."
        )

    def _fallback_roi(self, prompt, ctx, company):
        roi = ctx.get("roi_pct", "?")
        iqs = ctx.get("iqs_grade", "?")
        return (
            f"ROI Agent — {company}: ESG-linked financial ROI is {roi}% with an investment-quality "
            f"grade of {iqs}. Capital efficiency, growth-channel, and downside-protection signals "
            f"together support a constructive view on continued ESG capex deployment."
        )

    def _fallback_section(self, prompt, ctx, company):
        section = "environmental"
        for s in ("environmental", "social", "governance"):
            if s in prompt.lower():
                section = s
                break
        m = re.search(r"(\d+)/(\d+)\s+targets met", prompt)
        met = f"{m.group(1)} of {m.group(2)} targets are on track" if m else "targets are progressing"
        return (
            f"On the {section} pillar, {met}. The data shows steady delivery against committed "
            f"baselines, with the headline metrics in this section forming the evidence base "
            f"for stakeholder disclosures and assurance review."
        )

    def _fallback_generic(self, prompt, ctx, company):
        return (
            f"Analysis for {company} indicates measurable progress against ESG commitments, "
            f"with the figures shown above forming the evidence base for next-cycle planning."
        )

    _FALLBACK_BUILDERS = {
        "carbon_accountant": "_fallback_carbon",
        "risk_predictor": "_fallback_risk",
        "stakeholder_agent": "_fallback_stakeholder",
        "audit_agent": "_fallback_audit",
        "regulatory_tracker": "_fallback_regulatory",
        "action_agent": "_fallback_action",
        "action_item": "_fallback_action_item",
        "report_generator": "_fallback_report",
        "roi_agent": "_fallback_roi",
        "report_section": "_fallback_section",
    }

    def _fallback_summarize(self, text):
        sentences = text.replace("\n", " ").split(". ")
        if len(sentences) <= 3:
            return text
        return ". ".join(sentences[:3]) + "."

    def _fallback_classify(self, text, labels):
        import hashlib
        seed = int(hashlib.md5(text.encode()).hexdigest()[:8], 16)
        import random
        rng = random.Random(seed)
        scores = [rng.random() for _ in labels]
        total = sum(scores)
        return {label: score / total for label, score in zip(labels, scores)}

    def _fallback_sentiment(self, text):
        positive_words = {"good", "great", "improved", "strong", "excellent", "progress", "achieved"}
        negative_words = {"risk", "gap", "poor", "decline", "weak", "concern", "failure"}
        words = set(text.lower().split())
        pos = len(words & positive_words)
        neg = len(words & negative_words)
        if pos > neg:
            return {"label": "POSITIVE", "score": 0.75 + min(pos * 0.05, 0.2)}
        elif neg > pos:
            return {"label": "NEGATIVE", "score": 0.65 + min(neg * 0.05, 0.2)}
        return {"label": "NEUTRAL", "score": 0.55}


# Singleton
hf_client = HFClient()
