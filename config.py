"""ESG CoPilot Configuration"""
import os

# HuggingFace API
HF_API_TOKEN = os.environ.get("HF_API_TOKEN", "")
HF_API_URL = "https://api-inference.huggingface.co/models"

# Model assignments
MODELS = {
    "text_generation": "mistralai/Mistral-7B-Instruct-v0.3",
    "summarization": "facebook/bart-large-cnn",
    "zero_shot_classification": "facebook/bart-large-mnli",
    "sentiment_analysis": "distilbert/distilbert-base-uncased-finetuned-sst-2-english",
}

# Ports
STREAMLIT_PORT = 8501
GRADIO_PORT = 7860

# Data paths
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

# Company profile
COMPANY_NAME = "GreenTech Solutions Pvt. Ltd."
COMPANY_SECTOR = "Information Technology"
COMPANY_COUNTRY = "India"

# ESG Frameworks
FRAMEWORKS = ["BRSR", "CSRD", "GRI", "SASB"]

# Agent names and colors
AGENT_CONFIG = {
    "data_collector": {"name": "Data Collector", "icon": "📊", "color": "#2196F3"},
    "regulatory_tracker": {"name": "Regulatory Tracker", "icon": "📋", "color": "#FF9800"},
    "carbon_accountant": {"name": "Carbon Accountant", "icon": "🌱", "color": "#4CAF50"},
    "report_generator": {"name": "Report Generator", "icon": "📄", "color": "#9C27B0"},
    "risk_predictor": {"name": "Risk Predictor", "icon": "⚠️", "color": "#F44336"},
    "audit_agent": {"name": "Audit Agent", "icon": "🔍", "color": "#607D8B"},
    "action_agent": {"name": "Action Agent", "icon": "🎯", "color": "#E91E63"},
    "stakeholder_agent": {"name": "Stakeholder Agent", "icon": "👥", "color": "#00BCD4"},
}
