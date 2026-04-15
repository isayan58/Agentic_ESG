"""ESG CoPilot — Main Streamlit Dashboard."""
import streamlit as st

st.set_page_config(
    page_title="ESG CoPilot",
    page_icon="🌍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 700;
        color: #1E2761;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        font-size: 1.1rem;
        color: #666;
        margin-bottom: 1.5rem;
    }
    .stMetric > div {
        background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
        padding: 1rem;
        border-radius: 10px;
        border-left: 4px solid #1E2761;
    }
    .agent-card {
        background: #fff;
        border: 1px solid #e0e0e0;
        border-radius: 10px;
        padding: 1rem;
        margin: 0.5rem 0;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    div[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #1E2761 0%, #2a3a7a 100%);
    }
    div[data-testid="stSidebar"] .stMarkdown p,
    div[data-testid="stSidebar"] .stMarkdown h1,
    div[data-testid="stSidebar"] .stMarkdown h2,
    div[data-testid="stSidebar"] .stMarkdown h3 {
        color: white;
    }
</style>
""", unsafe_allow_html=True)

# Sidebar
with st.sidebar:
    st.markdown("# 🌍 ESG CoPilot")
    st.markdown("*Autonomous ESG Intelligence*")
    st.markdown("---")
    st.markdown("### Navigation")
    st.markdown("""
    Use the sidebar pages to access:
    - **Mission Control** — Overview dashboard
    - **9 Specialized Agents** — Each with full functionality
    """)
    st.markdown("---")
    st.markdown("### HuggingFace API")
    hf_token = st.text_input("HF API Token (optional)", type="password", key="hf_token_input")
    if hf_token:
        import os
        os.environ["HF_API_TOKEN"] = hf_token
        st.success("Token set!")
    else:
        st.info("Running in fallback mode (no API token)")

    st.markdown("---")
    st.markdown("**GreenTech Solutions Pvt. Ltd.**")
    st.caption("Sample company for demonstration")

# Main content
st.markdown('<p class="main-header">ESG CoPilot</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-header">Autonomous ESG Intelligence — From Manual Compliance to Continuous Excellence</p>', unsafe_allow_html=True)

st.markdown("---")

st.markdown("### Welcome to the ESG CoPilot Platform")
st.markdown("""
This platform orchestrates **9 specialized AI agents** that work together to autonomously collect,
analyze, report, and predict ESG performance. Each agent uses HuggingFace AI models for
intelligent analysis.
""")

# Quick overview cards
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("AI Agents", "9", help="Specialized ESG agents")
with col2:
    st.metric("Frameworks", "4", help="BRSR, CSRD, GRI, SASB")
with col3:
    st.metric("Data Sources", "7", help="Sample datasets loaded")
with col4:
    st.metric("AI Models", "4", help="HuggingFace models")

st.markdown("---")

# Agent fleet overview
st.markdown("### Agent Fleet")
agents_info = [
    ("📊", "Data Collector", "Auto-discovers and validates ESG data with quality scoring"),
    ("📋", "Regulatory Tracker", "Monitors BRSR, CSRD, GRI, SASB compliance"),
    ("🌱", "Carbon Accountant", "Tracks Scope 1/2/3 emissions and supply chain hotspots"),
    ("📄", "Report Generator", "Creates multi-framework audit-ready reports"),
    ("⚠️", "Risk Predictor", "Forecasts climate risks and predicts ESG ratings"),
    ("🔍", "Audit Agent", "Verifies compliance and manages audit trails"),
    ("⭐", "ESG ROI Agent", "Quantifies ESG-linked financial and strategic return"),
    ("🎯", "Action Agent", "Generates prioritized recommendations"),
    ("👥", "Stakeholder Agent", "Tailors communications for each audience"),
]

cols = st.columns(4)
for i, (icon, name, desc) in enumerate(agents_info):
    with cols[i % 4]:
        st.markdown(f"""
        <div class="agent-card">
            <h4>{icon} {name}</h4>
            <p style="font-size:0.85rem;color:#666;">{desc}</p>
        </div>
        """, unsafe_allow_html=True)

st.markdown("---")
st.markdown("### Getting Started")
st.markdown("""
1. Navigate to **Mission Control** to run the full agent pipeline
2. Or visit individual agent pages for focused analysis, including ESG ROI
3. Optionally set your HuggingFace API token in the sidebar for AI-powered analysis
""")
st.caption("Navigate using the sidebar pages →")
