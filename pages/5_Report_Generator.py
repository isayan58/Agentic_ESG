"""Streamlit page for the Report Generator — with embedded charts and HTML export."""
import streamlit as st
import pandas as pd
from agents.report_generator import ReportGeneratorAgent
from utils.charts import (
    emissions_donut, compliance_radar, emissions_trend,
    chart_unavailable_message, apply_chart_theme,
)
from core.channels import Channel
from core.state_manager import state_manager
from utils.streamlit_compat import safe_dataframe
from utils.auth import current_user, require_login, sidebar_auth_widget
from utils.feedback_store import save_feedback
from utils.ui import (
    inject_global_css, page_agent_header_live, pwc_header, section_picker,
    section_header, callout, verdict_kpi, insight_group, score_bars, glossary,
)
from utils.pipeline_refresh import data_freshness_caption

try:
    import plotly.graph_objects as go
    _PLOTLY = True
except ImportError:  # pragma: no cover - charts degrade to notices
    _PLOTLY = False

st.set_page_config(page_title="Report Generator | ESG Intelligence Hub", page_icon="📄", layout="wide")
inject_global_css()
pwc_header()
sidebar_auth_widget()
require_login("Sign in to access the Report Generator agent.")

# Top-of-page status strip — shows the signed-in user, the current
# agent, and the agent's LIVE status (auto-refreshes while running).
page_agent_header_live(
    agent_key="report_generator",
    agent_icon="📄",
)

st.title("📄 Report Generator Agent")
st.markdown("*Multi-framework audit-ready reports with AI narratives and embedded visual charts*")
data_freshness_caption(can_refresh=False)
st.markdown("---")

if "report_agent" not in st.session_state:
    st.session_state.report_agent = ReportGeneratorAgent()
    st.session_state.report_results = None

agent = st.session_state.report_agent


def render_chart(fig):
    if fig is None:
        st.info(chart_unavailable_message())
    else:
        st.plotly_chart(fig, use_container_width=True)

st.info("For best results, run Data Collector, Regulatory Tracker, Carbon Accountant, and Audit Agent first.")

if st.button("📝 Generate ESG Report", type="primary"):
    with st.spinner("Generating comprehensive ESG report with embedded charts..."):
        results = agent.run()
        st.session_state.report_results = results
    st.success("Report generated!")

results = st.session_state.report_results
if results and "error" not in results:
    # ── Shared data, hoisted above the section branches ───────────────────
    # Every branch (including Export) reads these, and only the selected
    # branch runs, so they must be resolved before the dropdown splits.
    carbon = results.get("carbon_highlights", {})
    sections = results.get("sections", {})
    fw_sections = results.get("framework_sections", {})
    compliance_data = results.get("compliance_summary", {})
    fw_scores = compliance_data.get("frameworks", {})
    carbon_data = state_manager.subscribe(Channel.CARBON) or {}

    recommended_reports = results.get("recommended_reports", [])
    actionable_insights = results.get("actionable_insights", [])
    data_quality_summary = results.get("data_quality_summary", [])
    regulatory_action_plan = results.get("regulatory_action_plan", [])
    carbon_insights = results.get("carbon_insights", [])
    risk_recommendations = results.get("risk_recommendations", [])
    audit_recommendations = results.get("audit_recommendations", [])
    roi_recommendations = results.get("roi_recommendations", [])
    distribution_plan = results.get("distribution_plan", "")
    dashboard_templates = results.get("dashboard_templates", {})

    def _num(value, default=None):
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    st.markdown("---")
    st.markdown(f"## {results.get('report_title', 'ESG Report')}")
    st.caption(f"Generated: {results.get('generated_at', '')[:19]}")

    _rg_section = section_picker([
        "📋 Executive Summary",
        "🌍 Carbon Performance",
        "✅ Framework Compliance",
        "🧠 Findings & Recommendations",
        "📑 Full Report Sections",
        "⬇️ Export & Audit Trail",
    ], key="report_generator_sec1")

    # ══════════════════════════════════════════════════════════════════════
    # EXECUTIVE SUMMARY
    # ══════════════════════════════════════════════════════════════════════
    if _rg_section == "📋 Executive Summary":
        _overall = _num(compliance_data.get("overall"))
        _yoy = _num(carbon.get("yoy_change"))

        # Lead with the verdict so a reader who stops here still leaves
        # knowing whether the report is good news.
        if _overall is not None and _yoy is not None:
            _dir = "down" if _yoy < 0 else "up"
            _tone = "success" if (_overall >= 75 and _yoy < 0) else (
                "warn" if (_overall < 60 or _yoy > 0) else "default")
            callout(
                f"Compliance across all frameworks averages **{_overall:.0f}%** and "
                f"emissions are **{_dir} {abs(_yoy):.1f}%** year on year. "
                + ("That is the combination auditors want to see."
                   if _tone == "success" else
                   "The sections below show exactly where the gaps are."),
                title="The short version",
                tone=_tone, icon="✅" if _tone == "success" else "📊",
            )
        st.markdown(results.get("executive_summary", ""))

        st.markdown("")
        section_header("Headline Numbers",
                       "The three figures a board will ask about first.")
        e1, e2, e3 = st.columns(3)
        with e1:
            _em = carbon.get("total_emissions", "N/A")
            verdict_kpi(
                "Total Emissions",
                f"{_em} tCO₂e" if _em != "N/A" else "N/A",
                "Everything the company emitted this year, across all three scopes.",
                verdict="neutral", verdict_label="",
                term="tCO₂e = tonnes of CO₂ equivalent, the standard unit.",
            )
        with e2:
            verdict_kpi(
                "Year-on-Year Change",
                f"{carbon.get('yoy_change', 'N/A')}%",
                ("Emissions fell versus last year." if (_yoy or 0) < 0
                 else "Emissions rose versus last year."),
                verdict=("good" if (_yoy or 0) < 0 else "poor"),
                verdict_label=("Improving" if (_yoy or 0) < 0 else "Rising"),
                term="Negative is good — it means you emitted less than last year.",
            )
        with e3:
            verdict_kpi(
                "Carbon Intensity",
                f"{carbon.get('carbon_intensity', 'N/A')}",
                "Emissions per $M of revenue — lets you compare fairly against "
                "bigger or smaller companies.",
                verdict="neutral", verdict_label="",
                term="Falling intensity means growth is decoupling from emissions.",
            )

        # ── Report completeness ───────────────────────────────────────────
        _built = [
            ("Executive summary", bool(results.get("executive_summary"))),
            ("Environmental section", bool(sections.get("environmental"))),
            ("Social section", bool(sections.get("social"))),
            ("Governance section", bool(sections.get("governance"))),
            ("Framework mapping", bool(fw_scores)),
            ("Audit trail", bool(results.get("audit_trail"))),
        ]
        _done = sum(1 for _, ok in _built if ok)
        section_header("Report Completeness",
                       f"{_done} of {len(_built)} parts of this report were "
                       f"produced from live pipeline data.")
        score_bars([{
            "name": name,
            "score": 100 if ok else 0,
            "status": "good" if ok else "poor",
            "meta": "Included" if ok else "Missing",
        } for name, ok in _built])

    # ══════════════════════════════════════════════════════════════════════
    # CARBON PERFORMANCE
    # ══════════════════════════════════════════════════════════════════════
    elif _rg_section == "🌍 Carbon Performance":
        section_header("Where the Emissions Come From",
                       "Split by scope — the standard way emissions are grouped.")
        callout(
            "**Scope 1** is what you burn directly (boilers, company vehicles). "
            "**Scope 2** is the electricity you buy. **Scope 3** is everything "
            "else in your value chain — suppliers, travel, product use. Scope 3 "
            "is usually the biggest and the hardest to measure.",
            icon="🧭", tone="info",
        )

        cur = carbon_data.get("scope_totals_current") or {}
        prev = carbon_data.get("scope_totals_previous") or {}

        c1, c2 = st.columns(2)
        with c1:
            if cur:
                render_chart(emissions_donut(cur))
                st.caption("Share of this year's total emissions by scope.")
            else:
                st.caption("Run the Carbon Accountant to populate this chart.")
        with c2:
            # This year vs last year, per scope — the single most useful
            # carbon chart for a non-specialist: it shows direction of travel
            # per scope rather than one blended number.
            if cur and prev and _PLOTLY:
                scopes = list(cur.keys())
                fig = go.Figure()
                fig.add_trace(go.Bar(
                    name="Last year", x=scopes,
                    y=[prev.get(s, 0) for s in scopes],
                    marker_color="#c7cdd6",
                    hovertemplate="<b>%{x}</b><br>Last year: %{y:,.0f} tCO₂e<extra></extra>",
                ))
                fig.add_trace(go.Bar(
                    name="This year", x=scopes,
                    y=[cur.get(s, 0) for s in scopes],
                    marker_color="#FD5108",
                    hovertemplate="<b>%{x}</b><br>This year: %{y:,.0f} tCO₂e<extra></extra>",
                ))
                fig.update_layout(
                    barmode="group", height=380,
                    plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                    font=dict(family="Inter, sans-serif", size=12),
                    yaxis=dict(title="tCO₂e", gridcolor="rgba(0,0,0,0.07)"),
                    xaxis=dict(title=None),
                    legend=dict(orientation="h", yanchor="bottom", y=1.02,
                                xanchor="right", x=1),
                    margin=dict(l=50, r=20, t=40, b=40),
                )
                st.plotly_chart(apply_chart_theme(fig), use_container_width=True)
                st.caption(
                    "Orange is this year, grey is last year. A shorter orange "
                    "bar means that scope improved."
                )
            else:
                st.caption("Prior-year scope data not available for comparison.")

        # ── Which scope moved most ────────────────────────────────────────
        if cur and prev:
            deltas = []
            for s in cur:
                c, p = _num(cur.get(s), 0) or 0, _num(prev.get(s), 0) or 0
                if p:
                    deltas.append((s, 100 * (c - p) / p, c - p))
            if deltas:
                deltas.sort(key=lambda d: d[1])
                best, worst = deltas[0], deltas[-1]
                callout(
                    f"**{best[0]}** improved the most ({best[1]:+.1f}%). "
                    f"**{worst[0]}** moved the wrong way the most "
                    f"({worst[1]:+.1f}%). Percentages are relative to that "
                    f"scope's own total last year.",
                    title="Biggest movers", icon="📈",
                )

        # ── Quarterly trend ───────────────────────────────────────────────
        trends = carbon_data.get("quarterly_trends") or []
        if trends:
            section_header("Emissions Over Time",
                           "Quarter-by-quarter, so seasonal swings are visible.")
            try:
                render_chart(emissions_trend(pd.DataFrame(trends)))
                st.caption(
                    "A steadily falling line is the goal. Spikes usually track "
                    "production volume or a cold/hot quarter."
                )
            except Exception:
                st.caption("Trend data could not be charted for this run.")

        if carbon_insights:
            insight_group("What the Carbon Accountant concluded",
                          carbon_insights[:6], icon="🌱")

    # ══════════════════════════════════════════════════════════════════════
    # FRAMEWORK COMPLIANCE
    # ══════════════════════════════════════════════════════════════════════
    elif _rg_section == "✅ Framework Compliance":
        section_header("How Ready You Are, Framework by Framework",
                       "Each bar is the share of that framework's disclosure "
                       "requirements you can currently evidence.")
        if not fw_scores:
            callout(
                "No framework scores yet. Run the **Regulatory Tracker** first "
                "and it will map your data against each disclosure standard.",
                title="Nothing to score yet", icon="📭",
            )
        else:
            _avg = sum(fw_scores.values()) / len(fw_scores)
            _ready = sum(1 for v in fw_scores.values() if v >= 75)
            callout(
                f"You average **{_avg:.0f}%** across **{len(fw_scores)}** "
                f"frameworks, and **{_ready}** of them are at 75% or better — "
                f"the level where a filing is usually defensible. The shortest "
                f"bars below are where to put effort first.",
                title="Where you stand",
                tone="success" if _avg >= 75 else "warn",
                icon="✅" if _avg >= 75 else "📊",
            )
            score_bars([
                {
                    "name": fw,
                    "score": _num(pct, 0) or 0,
                    "status": ("good" if (_num(pct, 0) or 0) >= 75
                               else "watch" if (_num(pct, 0) or 0) >= 50
                               else "poor"),
                    "meta": f"{_num(pct, 0) or 0:.0f}% ready",
                    "meta_sub": f"{100 - (_num(pct, 0) or 0):.0f}% to close",
                }
                for fw, pct in sorted(fw_scores.items(),
                                      key=lambda kv: -(_num(kv[1], 0) or 0))
            ])

            with st.expander("📖 What these frameworks are", expanded=False):
                glossary([
                    ("BRSR", "India's mandatory sustainability report for listed companies (SEBI)."),
                    ("CSRD", "EU directive requiring detailed, audited sustainability disclosure."),
                    ("GRI", "The most widely used voluntary global reporting standard."),
                    ("SASB", "Industry-specific standards focused on financially material issues."),
                    ("SOX", "US law on internal controls and the integrity of reported figures."),
                    ("SEC", "US securities regulator's climate and disclosure rules."),
                ])

            st.markdown("")
            rc1, rc2 = st.columns([1, 1])
            with rc1:
                render_chart(compliance_radar(fw_scores))
                st.caption(
                    "The same scores as a shape — a balanced hexagon means "
                    "even readiness; a dent shows one framework lagging."
                )
            with rc2:
                if regulatory_action_plan:
                    insight_group("How to close the gaps",
                                  regulatory_action_plan[:6], icon="⚖️")

    # ══════════════════════════════════════════════════════════════════════
    # FINDINGS & RECOMMENDATIONS
    # ══════════════════════════════════════════════════════════════════════
    elif _rg_section == "🧠 Findings & Recommendations":
        _groups = [
            ("Reports worth producing", "📄", recommended_reports[:6]),
            ("Key findings", "🔑", actionable_insights[:6]),
            ("Data quality", "🗄️", data_quality_summary[:6]),
            ("Regulatory actions", "⚖️", regulatory_action_plan[:6]),
            ("Carbon insights", "🌱", carbon_insights[:6]),
            ("Risk recommendations", "⚠️", risk_recommendations[:6]),
            ("Audit recommendations", "🔍", audit_recommendations[:6]),
            ("ROI recommendations", "⭐", roi_recommendations[:6]),
        ]
        _live = [(t, i, items) for t, i, items in _groups if items]

        section_header("Everything the Agents Recommended",
                       "Grouped by source so you can see who raised what.")
        if not _live:
            callout(
                "No recommendations were produced for this run. Run the full "
                "pipeline from **ESG Command Center** so each agent can "
                "contribute its findings.",
                title="Nothing to show", icon="📭",
            )
        else:
            _total = sum(len(items) for _, _, items in _live)
            callout(
                f"**{_total} recommendations** from **{len(_live)}** sources. "
                f"The counts on each card show where attention is "
                f"concentrated — the biggest card is usually the area that "
                f"needs the most work.",
                icon="🧠",
            )

            # A count-per-source chart makes the distribution obvious before
            # anyone reads a single line of text.
            if _PLOTLY and len(_live) > 1:
                _names = [t for t, _, _ in _live][::-1]
                _counts = [len(items) for _, _, items in _live][::-1]
                figf = go.Figure(go.Bar(
                    x=_counts, y=_names, orientation="h",
                    marker_color="#FD5108",
                    text=_counts, textposition="outside",
                    hovertemplate="<b>%{y}</b><br>%{x} recommendation(s)<extra></extra>",
                ))
                figf.update_layout(
                    height=max(260, len(_live) * 38 + 80),
                    plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                    font=dict(family="Inter, sans-serif", size=12),
                    xaxis=dict(title="Number of recommendations",
                               gridcolor="rgba(0,0,0,0.07)",
                               range=[0, max(_counts) * 1.25]),
                    yaxis=dict(title=None, automargin=True),
                    margin=dict(l=10, r=30, t=20, b=40), showlegend=False,
                )
                st.plotly_chart(apply_chart_theme(figf), use_container_width=True)

            for row_start in range(0, len(_live), 2):
                cols = st.columns(2)
                for col, (title, icon, items) in zip(cols, _live[row_start:row_start + 2]):
                    with col:
                        insight_group(title, items, icon=icon)
                        st.markdown("")

        if distribution_plan:
            with st.expander("📬 Who should receive this report", expanded=False):
                st.markdown(distribution_plan)

        if dashboard_templates:
            with st.expander("📊 Ready-made BI dashboard templates", expanded=False):
                st.caption("Drop these specs into your BI tool to rebuild this "
                           "analysis where your teams already work.")
                if dashboard_templates.get("summary"):
                    st.markdown(dashboard_templates.get("summary", ""))
                dc1, dc2 = st.columns(2)
                with dc1:
                    if dashboard_templates.get("power_bi"):
                        st.markdown("**Power BI**")
                        st.markdown(dashboard_templates.get("power_bi", ""))
                with dc2:
                    if dashboard_templates.get("quicksight"):
                        st.markdown("**Amazon QuickSight**")
                        st.markdown(dashboard_templates.get("quicksight", ""))

    # ══════════════════════════════════════════════════════════════════════
    # FULL REPORT SECTIONS
    # ══════════════════════════════════════════════════════════════════════
    elif _rg_section == "📑 Full Report Sections":
        section_header("The Report Itself",
                       "Environmental, Social and Governance chapters as they "
                       "will appear in the exported document.")
        callout(
            "This is the narrative an auditor or regulator reads. Each chapter "
            "pairs a written explanation with the underlying numbers, so every "
            "claim can be traced to data.",
            icon="📑",
        )
        for section_key, section_data in sections.items():
            with st.expander(f"📑 {section_data['title']}",
                             expanded=(section_key == "environmental")):
                st.markdown(section_data.get("narrative", ""))
                metrics = section_data.get("metrics", [])
                if metrics:
                    st.markdown("**Supporting figures**")
                    safe_dataframe(pd.DataFrame(metrics),
                                   use_container_width=True, hide_index=True)

    # ══════════════════════════════════════════════════════════════════════
    # EXPORT & AUDIT TRAIL
    # ══════════════════════════════════════════════════════════════════════
    elif _rg_section == "⬇️ Export & Audit Trail":
        section_header("Export This Report",
                       "Three formats — pick the one that matches where it is going.")
        callout(
            "**Markdown** for editing, **HTML** for sharing a link or emailing, "
            "**PDF-ready HTML** opens with the print dialog so you can save a "
            "PDF for the board pack.",
            icon="⬇️",
        )

        with st.expander("🔍 Comprehensive audit trail — how this report was built"):
            st.caption(
                "Every step the agent took, in order. This is what makes the "
                "report defensible: each figure can be traced back to the "
                "stage that produced it."
            )
            trail = results.get("audit_trail", [])
            if trail:
                insight_group(
                    "Generation steps",
                    [f"{e.get('step', '?')} — {e.get('details', '')} "
                     f"({e.get('status', 'unknown')})" for e in trail],
                    icon="🔍",
                )
            else:
                st.caption("No audit trail recorded for this run.")

        report_title = results.get('report_title', 'ESG Report')
        generated_at = results.get('generated_at', '')[:19]

        # ── Markdown ──────────────────────────────────────────────────────────────
        report_md = f"# {report_title}\n\n"
        report_md += f"## Executive Summary\n{results.get('executive_summary', '')}\n\n"
        for section_key, section_data in sections.items():
            report_md += f"## {section_data['title']}\n{section_data.get('narrative', '')}\n\n"

        # ── Shared HTML body fragments ────────────────────────────────────────────
        _metrics_header = (
            f'<div class="kpi-strip">'
            f'<div class="kpi"><div class="kpi-val">{carbon.get("total_emissions","N/A")} tCO2e</div>'
            f'<div class="kpi-lbl">Total Emissions</div></div>'
            f'<div class="kpi"><div class="kpi-val">{carbon.get("yoy_change","N/A")}%</div>'
            f'<div class="kpi-lbl">YoY Change</div></div>'
            f'<div class="kpi"><div class="kpi-val">{compliance_data.get("overall","N/A")}%</div>'
            f'<div class="kpi-lbl">Overall Compliance</div></div>'
            f'</div>'
        )
        _section_body = f"<h2>Executive Summary</h2><p>{results.get('executive_summary','')}</p>\n"
        for section_key, section_data in sections.items():
            _section_body += f"<h2>{section_data['title']}</h2><p>{section_data.get('narrative','')}</p>\n"
            metrics = section_data.get("metrics", [])
            if metrics:
                _section_body += "<table><tr>" + "".join(f"<th>{k}</th>" for k in metrics[0].keys()) + "</tr>"
                for row in metrics:
                    _section_body += "<tr>" + "".join(f"<td>{v}</td>" for v in row.values()) + "</tr>"
                _section_body += "</table>"

        _shared_css = """
          body{font-family:Calibri,Arial,sans-serif;max-width:900px;margin:40px auto;padding:20px;color:#333;}
          h1{color:#1E2761;border-bottom:3px solid #E8453C;padding-bottom:10px;font-size:26px;}
          h2{color:#1E2761;margin-top:30px;font-size:18px;}
          .kpi-strip{display:flex;gap:12px;flex-wrap:wrap;margin:16px 0;}
          .kpi{background:#f8f9fa;border-left:4px solid #1E2761;padding:14px 18px;border-radius:5px;min-width:160px;}
          .kpi-val{font-size:22px;font-weight:bold;color:#1E2761;}
          .kpi-lbl{font-size:11px;color:#666;margin-top:4px;}
          table{border-collapse:collapse;width:100%;margin:15px 0;font-size:13px;}
          th,td{border:1px solid #ddd;padding:7px 10px;text-align:left;}
          th{background:#1E2761;color:#fff;}
          tr:nth-child(even){background:#f8f9fa;}
          .footer{margin-top:40px;padding-top:16px;border-top:1px solid #ddd;color:#999;font-size:11px;}
          .pwc-bar{background:#E8453C;color:#fff;padding:8px 20px;font-size:13px;font-weight:bold;
                   letter-spacing:.5px;margin-bottom:24px;}
        """

        # ── Standard HTML report ──────────────────────────────────────────────────
        report_html = f"""<!DOCTYPE html>
    <html><head><meta charset="utf-8"><title>{report_title}</title>
    <style>{_shared_css}</style></head><body>
    <div class="pwc-bar">ESG Intelligence Hub — PwC</div>
    <h1>{report_title}</h1>
    <p><em>Generated: {generated_at}</em></p>
    {_metrics_header}
    {_section_body}
    <div class="footer">Generated by ESG Intelligence Hub &mdash; Confidential &amp; Proprietary</div>
    </body></html>"""

        # ── Print-to-PDF HTML (auto-triggers browser print dialog on open) ────────
        pdf_html = f"""<!DOCTYPE html>
    <html><head><meta charset="utf-8"><title>{report_title}</title>
    <style>
    {_shared_css}
    @media print {{
      body{{max-width:100%;margin:0;padding:12px;}}
      .no-print{{display:none!important;}}
      h1,h2{{page-break-after:avoid;}}
      table{{page-break-inside:avoid;}}
      .pwc-bar{{-webkit-print-color-adjust:exact;print-color-adjust:exact;}}
    }}
    .print-btn{{
      position:fixed;top:16px;right:20px;padding:10px 20px;
      background:#1E2761;color:#fff;border:none;border-radius:5px;
      cursor:pointer;font-size:14px;z-index:9999;
    }}
    </style>
    </head><body>
    <button class="print-btn no-print" onclick="window.print()">🖨 Print / Save as PDF</button>
    <div class="pwc-bar">ESG Intelligence Hub — PwC</div>
    <h1>{report_title}</h1>
    <p><em>Generated: {generated_at}</em></p>
    {_metrics_header}
    {_section_body}
    <div class="footer">Generated by ESG Intelligence Hub &mdash; Confidential &amp; Proprietary</div>
    <script>
      // Auto-trigger print dialog so the file opens ready to save as PDF.
      window.addEventListener("load", function() {{
        setTimeout(function() {{ window.print(); }}, 600);
      }});
    </script>
    </body></html>"""

        col1, col2, col3 = st.columns(3)
        with col1:
            st.download_button(
                "📥 Download Markdown",
                report_md,
                f"esg_report_{generated_at[:10]}.md",
                "text/markdown",
            )
        with col2:
            st.download_button(
                "📄 Download HTML Report",
                report_html,
                f"esg_report_{generated_at[:10]}.html",
                "text/html",
            )
        with col3:
            st.download_button(
                "🖨 Download PDF-ready HTML",
                pdf_html,
                f"esg_report_{generated_at[:10]}_print.html",
                "text/html",
                help="Opens in browser with print dialog → Save as PDF",
            )

        st.markdown("---")
        st.markdown("### Help the tool learn")
        st.markdown(
            "Your feedback is saved to the feedback store and used to improve future report generation prompts."
        )

        rating = st.radio(
            "How useful was this report?",
            ["Excellent", "Good", "Average", "Poor"],
            index=1,
            horizontal=True,
            key="report_feedback_rating",
        )
        comment = st.text_area(
            "What should improve?",
            key="report_feedback_comment",
            height=120,
        )

        if st.button("Submit feedback", key="report_feedback_submit"):
            user = current_user()
            username = user.get("username") if user else "anonymous"
            save_feedback(
                {
                    "report_title": results.get("report_title"),
                    "company": results.get("company", {}).get("company_name"),
                    "rating": rating,
                    "comment": comment,
                    "report_type": "Streamlit Report Generator",
                    "executive_summary": results.get("executive_summary", ""),
                    "recommended_reports": results.get("recommended_reports", []),
                    "actionable_insights": results.get("actionable_insights", []),
                    "dashboard_templates": results.get("dashboard_templates", {}),
                },
                username=username,
            )
            st.success("Thanks — your feedback has been recorded.")
