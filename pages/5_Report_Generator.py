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
from core.data_access import get_dataset
from utils.data_processing import load_esg_metrics
from utils.frameworks import (
    friendly as fw_friendly, glossary_pairs as fw_glossary, issuer as fw_issuer,
)
from utils.metric_rollup import (
    rollup_metrics, display_table, ATTAINMENT_MET, ATTAINMENT_ON_TRACK,
)

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
        "🌱 Environmental Metrics",
        "🤝 Social Metrics",
        "⚖️ Governance Metrics",
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
    # ESG METRICS — the full E/S/G metric set
    # ══════════════════════════════════════════════════════════════════════
    elif _rg_section in ("🌱 Environmental Metrics",
                         "🤝 Social Metrics",
                         "⚖️ Governance Metrics"):
        _pillar = {"🌱 Environmental Metrics": "Environmental",
                   "🤝 Social Metrics": "Social",
                   "⚖️ Governance Metrics": "Governance"}[_rg_section]
        _pillar_blurb = {
            "Environmental": "Emissions, energy, water, waste, pollution and "
                             "the money tied to climate.",
            "Social": "People — workforce, safety, human rights, community "
                      "and customers.",
            "Governance": "How the company is run and controlled — board, "
                          "ethics, controls, assurance and compliance.",
        }[_pillar]

        raw_metrics = get_dataset("esg_metrics", load_esg_metrics)
        rolled_all = rollup_metrics(raw_metrics)
        rolled = (rolled_all[rolled_all["pillar"] == _pillar]
                  if not rolled_all.empty and "pillar" in rolled_all.columns
                  else rolled_all.iloc[0:0])

        if rolled.empty:
            callout(
                "No ESG metric data is loaded. Connect an `esg_metrics` source "
                "on the **Data Collector** page, or run the pipeline to load "
                "the built-in reference set.",
                title="No metrics yet", icon="📭",
            )
        else:
            # ══════════════════════════════════════════════════════════════
            # CROSS-FILTER
            # ══════════════════════════════════════════════════════════════
            # Selections made on the charts below are read here, at the top
            # of the run, because Streamlit surfaces a chart's selection on
            # the *next* rerun via its widget key. Filtering `rolled` in
            # place means every chart further down narrows automatically —
            # there is no second code path for the filtered state to drift
            # from.
            pillar_all = rolled.copy()
            _genome_key = f"genome_{_pillar}"
            _quad_key = f"quad_{_pillar}"
            _fkey = f"rg_focus_{_pillar}"

            def _selected_points(state_key):
                """Points from a chart selection, tolerant of shape changes."""
                state = st.session_state.get(state_key)
                if not state:
                    return []
                try:
                    sel = state.get("selection") if isinstance(state, dict) else state.selection
                    return list((sel or {}).get("points", []) or [])
                except Exception:
                    return []

            # A click on the genome picks a category; a click on the quadrant
            # picks one metric. Newer selection wins.
            _picked_cat, _picked_metric = None, None
            for _pt in _selected_points(_genome_key):
                _ylab = str(_pt.get("y", "") or "")
                if _ylab:
                    _picked_cat = _ylab.split("  (")[0].strip()
            for _pt in _selected_points(_quad_key):
                _cd = _pt.get("customdata") or []
                if _cd:
                    _picked_metric = str(_cd[0])

            _focus = st.session_state.get(_fkey) or {}
            if _picked_metric:
                _focus = {"metric": _picked_metric}
            elif _picked_cat:
                _focus = {"category": _picked_cat}
            st.session_state[_fkey] = _focus

            # Explicit controls as well as chart clicks: a dropdown always
            # works, and it keeps the filter discoverable for anyone who
            # doesn't think to click a chart.
            fc1, fc2, fc3 = st.columns([2, 2, 1])
            _cat_options = ["All categories"] + sorted(pillar_all["category"].unique())
            _cur_cat = _focus.get("category")
            if _focus.get("metric"):
                _m_row = pillar_all[pillar_all["base_metric"] == _focus["metric"]]
                if not _m_row.empty:
                    _cur_cat = _m_row.iloc[0]["category"]
            with fc1:
                _sel_cat = st.selectbox(
                    "Category", _cat_options,
                    index=_cat_options.index(_cur_cat) if _cur_cat in _cat_options else 0,
                    key=f"rg_cat_{_pillar}",
                )
            _scope = (pillar_all if _sel_cat == "All categories"
                      else pillar_all[pillar_all["category"] == _sel_cat])
            with fc2:
                _m_options = ["All metrics"] + sorted(_scope["base_metric"].tolist())
                _cur_m = _focus.get("metric")
                _sel_metric = st.selectbox(
                    "Metric", _m_options,
                    index=_m_options.index(_cur_m) if _cur_m in _m_options else 0,
                    key=f"rg_met_{_pillar}",
                )
            with fc3:
                st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
                if st.button("Clear", key=f"rg_clear_{_pillar}",
                             use_container_width=True):
                    for _k in (_genome_key, _quad_key, f"rg_cat_{_pillar}",
                               f"rg_met_{_pillar}"):
                        st.session_state.pop(_k, None)
                    st.session_state[_fkey] = {}
                    st.rerun()

            # The dropdowns are the source of truth once touched, so a chart
            # click and a manual choice can never disagree on screen.
            if _sel_metric != "All metrics":
                rolled = _scope[_scope["base_metric"] == _sel_metric].copy()
                _focus_label = f"{_sel_metric}"
            elif _sel_cat != "All categories":
                rolled = _scope.copy()
                _focus_label = f"{_sel_cat} ({len(rolled)} metrics)"
            else:
                rolled = pillar_all.copy()
                _focus_label = ""

            if _focus_label:
                callout(
                    f"Showing **{_focus_label}** only. Every chart below is "
                    f"filtered to this selection — press **Clear** to see all "
                    f"{len(pillar_all)} {_pillar.lower()} metrics again.",
                    title="Filtered view", tone="info", icon="🔍",
                )
            _n_bu = int(rolled["business_units"].max())
            _met = int((rolled["status"] == "Met").sum())
            _track = int((rolled["status"] == "On Track").sum())
            _miss = int((rolled["status"] == "Not Met").sum())
            _total = len(rolled)

            # `attainment` comes from the roll-up: the share of business units
            # hitting target. Direction-safe, because the per-unit verdicts
            # already know whether high or low is good on each metric — so one
            # number ranks every metric in the pillar on the same scale.
            rolled = rolled.copy()

            section_header(f"{_pillar} Performance", _pillar_blurb)
            _share = 100 * _met / _total if _total else 0
            callout(
                f"**{_total} metrics** tracked across **{_n_bu} business units**. "
                f"**{_met}** are meeting target, **{_track}** are on track and "
                f"**{_miss}** are behind. "
                + ("This pillar is in good shape."
                   if _share >= 50 else
                   "The charts below rank every metric so you can see which "
                   "ones to pick up first."),
                title=f"{_pillar} at a glance",
                tone="success" if _share >= 50 else "warn",
                icon="✅" if _share >= 50 else "📊",
            )

            k1, k2, k3, k4 = st.columns(4)
            with k1:
                verdict_kpi("Metrics", str(_total),
                            f"Tracked in the {_pillar.lower()} pillar.",
                            verdict="neutral", verdict_label="")
            with k2:
                verdict_kpi("Meeting Target", str(_met),
                            "Most business units hit the target.",
                            verdict="good" if _share >= 50 else "watch",
                            verdict_label=f"{_share:.0f}%")
            with k3:
                verdict_kpi("On Track", str(_track),
                            "Heading the right way, not there yet.",
                            verdict="watch", verdict_label="")
            with k4:
                verdict_kpi("Behind", str(_miss),
                            "Need an owner and a date.",
                            verdict="poor" if _miss else "good",
                            verdict_label="Action" if _miss else "None")

            _C_MET, _C_TRACK, _C_MISS = "#2E8540", "#FFB600", "#C8102E"
            _status_colour = {"Met": _C_MET, "On Track": _C_TRACK,
                              "Not Met": _C_MISS}

            # A genome of one tile, a sunburst of one wedge and a Sankey of
            # one ribbon are not charts, they are noise. Below a handful of
            # metrics those views are dropped and the space goes to a detail
            # panel that is actually readable at that size.
            _rich_enough = len(rolled) >= 4

            if _PLOTLY and _rich_enough:
                # ══════════════════════════════════════════════════════════
                # 1 — THE ESG GENOME
                # ══════════════════════════════════════════════════════════
                # Every metric in the pillar as one tile, grouped into its
                # category row. A bar chart of 167 metrics is 4,000px of
                # scrolling; the same 167 as tiles is one glance, and the
                # eye finds the red bands before it reads a single label.
                section_header(
                    f"The {_pillar} Genome",
                    f"All {_total} metrics at once. One tile per metric, "
                    f"grouped by category. Red is where targets are being "
                    f"missed — look for the bands, not the tiles.",
                )
                cats_ordered = (rolled.groupby("category")["attainment"]
                                .mean().sort_values().index.tolist())
                width = int(rolled.groupby("category").size().max())
                z, hover, ytick = [], [], []
                for cat in cats_ordered:
                    sub = rolled[rolled["category"] == cat].sort_values("attainment")
                    row_z = sub["attainment"].tolist()
                    row_h = [f"<b>{m}</b><br>{a:.0f}% of units on target<br>"
                             f"Status: {s}"
                             for m, a, s in zip(sub["base_metric"],
                                                sub["attainment"], sub["status"])]
                    pad = width - len(row_z)
                    z.append(row_z + [None] * pad)
                    hover.append(row_h + [""] * pad)
                    ytick.append(f"{cat}  ({len(sub)})")

                figg = go.Figure(go.Heatmap(
                    z=z, customdata=hover, y=ytick,
                    colorscale=[[0.0, "#8B0000"], [0.25, "#C8102E"],
                                [0.5, "#FFB600"], [0.75, "#7CB342"],
                                [1.0, "#1B5E20"]],
                    zmin=0, zmax=100, xgap=3, ygap=3,
                    hovertemplate="%{customdata}<extra></extra>",
                    colorbar=dict(title="% of units<br>on target", thickness=14,
                                  len=0.85, tickfont=dict(size=10),
                                  title_font=dict(size=10)),
                ))
                figg.update_layout(
                    height=max(300, len(cats_ordered) * 46 + 110),
                    plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                    font=dict(family="Inter, sans-serif", size=12),
                    xaxis=dict(showticklabels=False, showgrid=False,
                               zeroline=False, title="each tile is one metric"),
                    yaxis=dict(autorange="reversed", tickfont=dict(size=11)),
                    margin=dict(l=10, r=10, t=16, b=40),
                )
                st.plotly_chart(apply_chart_theme(figg), use_container_width=True,
                                on_select="rerun", key=_genome_key)
                st.caption(
                    "Categories are ordered worst-performing at the top. "
                    "**Click any tile to filter every chart on this page to "
                    "that category.** Hover for the metric behind it."
                )

                # ══════════════════════════════════════════════════════════
                # 2 — RADIAL DRILL-DOWN
                # ══════════════════════════════════════════════════════════
                # Click a wedge to zoom into a category; click the middle to
                # come back. Carries the whole hierarchy without a table.
                st.markdown("")
                cs1, cs2 = st.columns([1, 1])
                with cs1:
                    section_header("Click to Explore",
                                   "Inner ring is categories, outer ring is "
                                   "metrics. Click any wedge to zoom in.")
                    labels = list(cats_ordered)
                    parents = [""] * len(cats_ordered)
                    values = [int((rolled["category"] == c).sum()) for c in cats_ordered]
                    colours = [float(rolled[rolled["category"] == c]["attainment"].mean())
                               for c in cats_ordered]
                    # Only the category ring is labelled. Printing 167 metric
                    # names around the rim renders them as unreadable radial
                    # slivers; the outer ring stays a clean colour band and
                    # gives up its names on hover and on click-to-zoom.
                    shown_text = list(cats_ordered)
                    for _, m in rolled.iterrows():
                        labels.append(m["base_metric"])
                        parents.append(m["category"])
                        values.append(1)
                        colours.append(float(m["attainment"]))
                        shown_text.append("")
                    figs = go.Figure(go.Sunburst(
                        labels=labels, parents=parents, values=values,
                        text=shown_text, textinfo="text",
                        branchvalues="total", maxdepth=2,
                        marker=dict(colors=colours, colorscale="RdYlGn",
                                    cmin=0, cmax=100,
                                    line=dict(color="white", width=1)),
                        hovertemplate="<b>%{label}</b><br>%{value} metric(s)<br>"
                                      "%{color:.0f}% on target<extra></extra>",
                        insidetextorientation="radial",
                    ))
                    figs.update_layout(
                        height=460, paper_bgcolor="rgba(0,0,0,0)",
                        font=dict(family="Inter, sans-serif", size=11),
                        margin=dict(l=0, r=0, t=10, b=10),
                    )
                    st.plotly_chart(apply_chart_theme(figs), use_container_width=True)

                with cs2:
                    # ══════════════════════════════════════════════════════
                    # 3 — RISK vs MOMENTUM QUADRANT
                    # ══════════════════════════════════════════════════════
                    # Two questions at once: how widely is the target met,
                    # and is it improving? The bottom-left quadrant is the
                    # answer to "what do we fix first".
                    section_header("Where to Act First",
                                   "Attainment against momentum. Bottom-left "
                                   "is failing and getting worse.")
                    q = rolled.dropna(subset=["yoy_change_pct"]).copy()
                    q["momentum"] = q["yoy_change_pct"].clip(-60, 60)
                    figq = go.Figure(go.Scatter(
                        x=q["momentum"], y=q["attainment"], mode="markers",
                        marker=dict(
                            size=9,
                            color=q["attainment"], colorscale="RdYlGn",
                            cmin=0, cmax=100, opacity=0.85,
                            line=dict(width=0.5, color="white")),
                        customdata=list(zip(q["base_metric"], q["category"],
                                            q["status"])),
                        hovertemplate="<b>%{customdata[0]}</b><br>"
                                      "%{customdata[1]}<br>"
                                      "%{y:.0f}% on target<br>"
                                      "%{x:+.1f}% vs last year<extra></extra>",
                    ))
                    figq.add_hline(y=ATTAINMENT_ON_TRACK, line_dash="dot",
                                   line_color="rgba(0,0,0,0.35)")
                    figq.add_vline(x=0, line_dash="dot",
                                   line_color="rgba(0,0,0,0.35)")
                    figq.add_annotation(x=-45, y=12, text="fix first",
                                        showarrow=False,
                                        font=dict(size=11, color="#C8102E"))
                    figq.add_annotation(x=42, y=94, text="protect",
                                        showarrow=False,
                                        font=dict(size=11, color="#2E8540"))
                    figq.update_layout(
                        height=460, plot_bgcolor="rgba(0,0,0,0)",
                        paper_bgcolor="rgba(0,0,0,0)",
                        font=dict(family="Inter, sans-serif", size=11),
                        xaxis=dict(title="change vs last year (%)",
                                   gridcolor="rgba(0,0,0,0.07)"),
                        yaxis=dict(title="% of units on target",
                                   gridcolor="rgba(0,0,0,0.07)", range=[-5, 105]),
                        margin=dict(l=10, r=10, t=10, b=40), showlegend=False,
                    )
                    st.plotly_chart(apply_chart_theme(figq), use_container_width=True,
                                    on_select="rerun", key=_quad_key)

                st.caption(
                    "Each dot is one metric. Left of the vertical line means "
                    "it moved down this year; below the dotted line means "
                    "fewer than half the business units are on target. "
                    "**Click a dot to focus the page on that single metric.**"
                )

                # ══════════════════════════════════════════════════════════
                # 4 — METRICS → DISCLOSURES FLOW
                # ══════════════════════════════════════════════════════════
                # The chart nobody expects: which categories actually feed
                # which filings. A weak category here is traceable straight
                # to the report it puts at risk.
                flows = {}
                for _, m in rolled.iterrows():
                    for tag in str(m["frameworks"]).split(","):
                        tag = tag.strip()
                        if tag:
                            flows[(m["category"], tag)] = flows.get(
                                (m["category"], tag), 0) + 1
                if flows:
                    section_header(
                        "Which Filings Depend on This Pillar",
                        "Every metric feeds one or more disclosure standards. "
                        "Thicker ribbons carry more metrics.",
                    )
                    srcs = sorted({c for c, _ in flows})
                    dsts = sorted({f for _, f in flows})
                    nodes = srcs + [fw_friendly(f) for f in dsts]
                    idx = {n: i for i, n in enumerate(srcs)}
                    idx.update({f: len(srcs) + i for i, f in enumerate(dsts)})
                    cat_attain = {c: float(rolled[rolled["category"] == c]["attainment"].mean())
                                  for c in srcs}

                    def _band(a):
                        return ("rgba(200,16,46,0.45)" if a < ATTAINMENT_ON_TRACK
                                else "rgba(255,182,0,0.45)" if a < ATTAINMENT_MET
                                else "rgba(46,133,64,0.45)")

                    figk = go.Figure(go.Sankey(
                        arrangement="snap",
                        node=dict(
                            label=nodes, pad=14, thickness=16,
                            line=dict(color="rgba(0,0,0,0.15)", width=0.5),
                            color=[_band(cat_attain[c]).replace("0.45", "0.85")
                                   for c in srcs] + ["#5b6473"] * len(dsts),
                            hovertemplate="<b>%{label}</b><br>%{value} links"
                                          "<extra></extra>",
                        ),
                        link=dict(
                            source=[idx[c] for c, _ in flows],
                            target=[idx[f] for _, f in flows],
                            value=list(flows.values()),
                            color=[_band(cat_attain[c]) for c, _ in flows],
                            hovertemplate="<b>%{source.label}</b> feeds "
                                          "<b>%{target.label}</b><br>"
                                          "%{value} metrics<extra></extra>",
                        ),
                    ))
                    figk.update_layout(
                        height=max(380, len(dsts) * 30 + 160),
                        paper_bgcolor="rgba(0,0,0,0)",
                        font=dict(family="Inter, sans-serif", size=11),
                        margin=dict(l=10, r=10, t=16, b=16),
                    )
                    st.plotly_chart(apply_chart_theme(figk), use_container_width=True)
                    st.caption(
                        "Ribbon colour is the category's health, so a red "
                        "ribbon shows a weak area flowing into a live filing "
                        "obligation."
                    )

                # ── The short actionable list ────────────────────────────
                worst = rolled.nsmallest(10, "attainment")
                if not worst.empty:
                    section_header("The Ten to Fix First",
                                   "Lowest attainment in this pillar.")
                    figw = go.Figure(go.Bar(
                        x=worst["attainment"].tolist()[::-1],
                        y=worst["base_metric"].tolist()[::-1],
                        orientation="h",
                        marker=dict(color=[_status_colour.get(s, "#8b949e")
                                           for s in worst["status"]][::-1]),
                        text=[f"{v:.0f}%" for v in worst["attainment"]][::-1],
                        textposition="outside", textfont=dict(size=11),
                        hovertemplate="<b>%{y}</b><br>%{x:.0f}% of units on "
                                      "target<extra></extra>",
                    ))
                    figw.update_layout(
                        height=360, plot_bgcolor="rgba(0,0,0,0)",
                        paper_bgcolor="rgba(0,0,0,0)",
                        font=dict(family="Inter, sans-serif", size=12),
                        xaxis=dict(title="% of business units on target",
                                   range=[0, 115], gridcolor="rgba(0,0,0,0.07)"),
                        yaxis=dict(title=None, automargin=True),
                        margin=dict(l=10, r=40, t=10, b=40), showlegend=False,
                    )
                    st.plotly_chart(apply_chart_theme(figw), use_container_width=True)


            elif _PLOTLY:
                # ══════════════════════════════════════════════════════════
                # FOCUSED VIEW — one metric (or a couple)
                # ══════════════════════════════════════════════════════════
                # At this size the interesting question changes: not "which
                # metric is worst" but "who inside the company is dragging
                # this one down".
                for _, _m in rolled.iterrows():
                    section_header(_m["base_metric"],
                                   f"{_m['category']} · reported by "
                                   f"{int(_m['business_units'])} business units")
                    d1, d2, d3, d4 = st.columns(4)
                    _unit_txt = f" {_m['unit']}" if _m["unit"] else ""
                    with d1:
                        verdict_kpi("This Year",
                                    f"{_m['value_2024']:,.1f}{_unit_txt}"
                                    if _m["value_2024"] is not None else "—",
                                    "Company-wide figure for the current year.",
                                    verdict="neutral", verdict_label="")
                    with d2:
                        verdict_kpi("Target",
                                    f"{_m['target_2024']:,.1f}{_unit_txt}"
                                    if _m["target_2024"] is not None else "—",
                                    "What the company committed to.",
                                    verdict="neutral", verdict_label="")
                    with d3:
                        _yoy = _m["yoy_change_pct"]
                        verdict_kpi("Vs Last Year",
                                    f"{_yoy:+.1f}%" if _yoy is not None else "—",
                                    "Direction of travel — check the metric "
                                    "before reading this as good or bad.",
                                    verdict="neutral", verdict_label="")
                    with d4:
                        verdict_kpi("Units On Target",
                                    f"{int(_m['met_count'])}/{int(_m['business_units'])}",
                                    "How widely the target is actually met.",
                                    verdict=("good" if _m["attainment"] >= ATTAINMENT_MET
                                             else "watch" if _m["attainment"] >= ATTAINMENT_ON_TRACK
                                             else "poor"),
                                    verdict_label=f"{_m['attainment']:.0f}%")

                    _det = raw_metrics[raw_metrics["metric_id"] == _m["metric_id"]].copy()
                    if not _det.empty and "business_unit" in _det.columns:
                        _det = _det.sort_values("value_2024", ascending=False).head(30)
                        _cols = {"Met": "#2E8540", "On Track": "#FFB600",
                                 "Not Met": "#C8102E"}
                        figd = go.Figure(go.Bar(
                            x=_det["business_unit"], y=_det["value_2024"],
                            marker=dict(color=[_cols.get(s, "#8b949e")
                                               for s in _det.get("status", [])]),
                            customdata=list(zip(_det.get("status", []),
                                                _det.get("target_2024", []))),
                            hovertemplate="<b>%{x}</b><br>Value: %{y:,.2f}<br>"
                                          "Target: %{customdata[1]:,.2f}<br>"
                                          "Status: %{customdata[0]}<extra></extra>",
                        ))
                        figd.update_layout(
                            height=340, plot_bgcolor="rgba(0,0,0,0)",
                            paper_bgcolor="rgba(0,0,0,0)",
                            font=dict(family="Inter, sans-serif", size=11),
                            xaxis=dict(title="business unit", tickangle=-45,
                                       gridcolor="rgba(0,0,0,0.07)"),
                            yaxis=dict(title=f"value{_unit_txt}",
                                       gridcolor="rgba(0,0,0,0.07)"),
                            margin=dict(l=10, r=10, t=16, b=90), showlegend=False,
                        )
                        st.plotly_chart(apply_chart_theme(figd),
                                        use_container_width=True)
                        st.caption(
                            f"Each bar is one business unit's contribution, "
                            f"coloured by whether it met its own target. "
                            f"Showing the {len(_det)} largest of "
                            f"{int(_m['business_units'])}."
                        )

                    _tags = [t.strip() for t in str(_m["frameworks"]).split(",")
                             if t.strip()]
                    if _tags:
                        st.markdown("**This metric feeds:**")
                        glossary(fw_glossary(_tags))
            # ── Which disclosures this pillar feeds ──────────────────────
            tags = {}
            for s in rolled["frameworks"].dropna().astype(str):
                for t in (x.strip() for x in s.split(",") if x.strip()):
                    tags[t] = tags.get(t, 0) + 1
            if tags:
                section_header("Disclosures This Pillar Feeds",
                               "Which reporting standards depend on these "
                               "metrics.")
                score_bars([
                    {"name": fw_friendly(tag),
                     "subtitle": fw_issuer(tag),
                     "score": 100 * count / _total,
                     "status": "good" if count >= 6 else "watch" if count >= 3 else "poor",
                     "meta": f"{count} metrics"}
                    for tag, count in sorted(tags.items(), key=lambda kv: -kv[1])
                ])

            # ── Numbers, for anyone who wants them ───────────────────────
            with st.expander(f"🔢 See the {_total} {_pillar.lower()} metrics as a table",
                             expanded=False):
                safe_dataframe(display_table(rolled),
                               use_container_width=True, hide_index=True)

            with st.expander("🔬 Drill into one metric by business unit",
                             expanded=False):
                st.caption("Company figures hide variation. Pick a metric to "
                           "see how each business unit contributed.")
                pick = st.selectbox(
                    "Metric",
                    rolled["metric_id"] + " — " + rolled["base_metric"],
                    key=f"rg_drill_{_pillar}",
                )
                pick_id = str(pick).split("—")[0].strip()
                detail = raw_metrics[raw_metrics["metric_id"] == pick_id]
                if not detail.empty:
                    cols = [c for c in ["business_unit", "unit", "value_2023",
                                        "value_2024", "target_2024", "status",
                                        "data_source", "confidence"]
                            if c in detail.columns]
                    st.caption(f"{len(detail)} business units report this metric. "
                               f"Values are that unit's share of the company total.")
                    safe_dataframe(detail[cols], use_container_width=True,
                                   hide_index=True)


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
