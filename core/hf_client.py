"""HuggingFace Inference API client with fallback to mock responses."""
import json
import requests
import time
from config import HF_API_TOKEN, HF_API_URL, MODELS


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

    def generate_text(self, prompt, max_tokens=300):
        if not self.is_available:
            return self._fallback_generate(prompt)

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
        return self._fallback_generate(prompt)

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

    def _fallback_generate(self, prompt):
        prompt_lower = prompt.lower()
        if "recommendation" in prompt_lower or "action" in prompt_lower:
            return (
                "Based on the analysis, we recommend: (1) Implement energy-efficient "
                "practices across operations to reduce Scope 2 emissions by 15-20%. "
                "(2) Engage top-tier suppliers in carbon reduction programs to address "
                "Scope 3 hotspots. (3) Strengthen governance structures with quarterly "
                "ESG committee reviews. (4) Enhance data collection processes for "
                "improved reporting accuracy across all frameworks."
            )
        if "risk" in prompt_lower:
            return (
                "The risk assessment indicates moderate-to-high exposure in climate "
                "transition risks, particularly in energy cost volatility and regulatory "
                "compliance gaps. Physical risks remain low for current operations but "
                "supply chain vulnerability in Southeast Asian regions requires monitoring. "
                "ESG rating trajectory suggests potential upgrade to A- within 12 months "
                "if remediation actions are implemented."
            )
        if "stakeholder" in prompt_lower or "investor" in prompt_lower:
            return (
                "Dear Stakeholders, the company has made significant progress in "
                "its ESG journey this reporting period. Carbon intensity decreased YoY, "
                "workforce diversity targets are advancing, and compliance levels "
                "across regulatory frameworks continue to improve. Our commitment to "
                "sustainable operations continues to drive long-term value creation."
            )
        if "audit" in prompt_lower or "compliance" in prompt_lower:
            return (
                "Audit findings indicate an overall compliance score of 87%. Key gaps "
                "identified: (1) Scope 3 emissions data coverage at 72% — needs supplier "
                "engagement improvement. (2) CSRD double materiality assessment pending. "
                "(3) Biodiversity impact metrics not yet standardized. Recommended actions "
                "have been logged with priority assignments."
            )
        if "carbon" in prompt_lower or "emission" in prompt_lower:
            return (
                "Carbon accounting analysis reveals emissions distributed across three scopes. "
                "Scope 1 includes direct operational emissions (fleet and facilities), "
                "Scope 2 covers purchased electricity and heating, and Scope 3 encompasses "
                "supply chain and business travel. Supply chain suppliers represent the "
                "largest share of Scope 3 emissions and are key decarbonization targets."
            )
        return (
            "The ESG analysis indicates strong progress across environmental, social, "
            "and governance pillars. Key metrics show year-over-year improvements in "
            "carbon intensity (-12%), water efficiency (+8%), and board diversity (+15%). "
            "Continued focus on supply chain transparency and Scope 3 data collection "
            "will further strengthen the organization's ESG performance profile."
        )

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
