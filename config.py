"""ESG Pilot Configuration — loads company data from company_profile.json."""
import os

# HuggingFace API — narrative polish only (per-agent text generation)
HF_API_TOKEN = os.environ.get("HF_API_TOKEN", "")
HF_API_URL = "https://api-inference.huggingface.co/models"

# Model assignments
MODELS = {
    "text_generation": "mistralai/Mistral-7B-Instruct-v0.3",
    "summarization": "facebook/bart-large-cnn",
    "zero_shot_classification": "facebook/bart-large-mnli",
    "sentiment_analysis": "distilbert/distilbert-base-uncased-finetuned-sst-2-english",
}

# Anthropic API — orchestrator agent loop (tool-use, planning, decisions)
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-opus-4-7")
ANTHROPIC_EFFORT = os.environ.get("ANTHROPIC_EFFORT", "high")  # low|medium|high|xhigh|max
ANTHROPIC_MAX_TOKENS = int(os.environ.get("ANTHROPIC_MAX_TOKENS", "16000"))

# ── ESG Pilot chatbot (LangGraph + MCP) ──────────────────────────────────
# When enabled, the chat drawer drives the conversation through a LangGraph
# create_react_agent backed by the esg-data / esg-pipeline / esg-charts MCP
# servers, with a SQLite checkpointer for durable per-user memory. Falls back
# to the legacy in-file tool-use loop when disabled or when the LangGraph /
# MCP stack is unavailable. Toggle off with PILOT_USE_LANGGRAPH=0.
PILOT_USE_LANGGRAPH = os.environ.get("PILOT_USE_LANGGRAPH", "1") not in ("0", "false", "False")
# Checkpointer DB — keyed by thread_id = username for cross-session,
# cross-device conversation memory in place of st.session_state.
PILOT_CHECKPOINT_DB = os.environ.get(
    "PILOT_CHECKPOINT_DB",
    os.path.join(os.path.expanduser("~"), ".cache", "esg", "pilot_memory.sqlite"),
)

# Ports
STREAMLIT_PORT = int(os.environ.get("STREAMLIT_PORT", 8501))
GRADIO_PORT = int(os.environ.get("GRADIO_PORT", 7860))

# Data paths
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

# ── Company-level values (loaded from data/company_profile.json) ─────────
from core.company_config import company_cfg  # noqa: E402

COMPANY_NAME = company_cfg.company_name
COMPANY_SECTOR = company_cfg.sector
COMPANY_COUNTRY = (company_cfg.headquarters.split(",")[-1].strip()
                   if company_cfg.headquarters else "")

# ESG Frameworks = adopted + planned (deduplicated, order-preserved)
_seen: set[str] = set()
FRAMEWORKS: list[str] = []
for _fw in company_cfg.frameworks_adopted + company_cfg.frameworks_planned:
    if _fw not in _seen:
        FRAMEWORKS.append(_fw)
        _seen.add(_fw)

# Agent names and colors (UI only — not company-specific)
AGENT_CONFIG = {
    "data_collector": {"name": "Data Collector", "icon": "📊", "color": "#2196F3"},
    "regulatory_tracker": {"name": "Regulatory Tracker", "icon": "📋", "color": "#FF9800"},
    "carbon_accountant": {"name": "Carbon Accountant", "icon": "🌱", "color": "#4CAF50"},
    "report_generator": {"name": "Report Generator", "icon": "📄", "color": "#9C27B0"},
    "risk_predictor": {"name": "Risk Predictor", "icon": "⚠️", "color": "#F44336"},
    "audit_agent": {"name": "Audit Agent", "icon": "🔍", "color": "#607D8B"},
    "roi_agent": {"name": "ESG ROI Agent", "icon": "⭐", "color": "#FD5108"},
    "action_agent": {"name": "Action Agent", "icon": "🎯", "color": "#E91E63"},
    "stakeholder_agent": {"name": "Stakeholder Agent", "icon": "👥", "color": "#00BCD4"},
}
