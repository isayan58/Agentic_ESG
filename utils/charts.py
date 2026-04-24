"""Chart generation utilities using Plotly."""
try:
    import plotly.graph_objects as go
    import plotly.express as px
    from plotly.subplots import make_subplots
    PLOTLY_AVAILABLE = True
except ImportError:
    go = None
    px = None
    make_subplots = None
    PLOTLY_AVAILABLE = False


COLORS = {
    "primary": "#D04A02",      # PwC orange — aligned to design system
    "secondary": "#FFB600",    # PwC amber
    "accent": "#E0301E",       # PwC tomato
    "success": "#2E8540",
    "warning": "#FFB600",
    "danger": "#C8102E",
    "info": "#2563eb",
    "dark": "#0f172a",
    "light": "#fff6ef",
    "muted": "#5b6473",
    "border": "#f1d9c4",
    "scope1": "#D04A02",
    "scope2": "#FFB600",
    "scope3": "#A23A02",
}

# Categorical palette for multi-series charts (warm PwC family)
CATEGORICAL = [
    "#D04A02", "#FFB600", "#E0301E", "#A23A02",
    "#2E8540", "#2563eb", "#7c3aed", "#0891b2",
]

LAYOUT_DEFAULTS = dict(
    font=dict(
        family="Inter, -apple-system, 'Segoe UI', Roboto, sans-serif",
        size=12, color="#0f172a",
    ),
    title_font=dict(
        family="Plus Jakarta Sans, Inter, sans-serif", size=15, color="#0f172a",
    ),
    plot_bgcolor="rgba(0,0,0,0)",
    paper_bgcolor="rgba(0,0,0,0)",
    margin=dict(l=44, r=24, t=56, b=44),
    colorway=CATEGORICAL,
    hoverlabel=dict(
        bgcolor="#0f172a", font=dict(color="#ffffff", family="Inter, sans-serif", size=12),
        bordercolor="#0f172a",
    ),
    legend=dict(
        bgcolor="rgba(255,255,255,0.6)", bordercolor="#f1d9c4", borderwidth=1,
        font=dict(size=11),
    ),
    xaxis=dict(
        gridcolor="#f1d9c4", zerolinecolor="#e3bfa1", linecolor="#e3bfa1",
        tickfont=dict(size=11, color="#5b6473"),
    ),
    yaxis=dict(
        gridcolor="#f1d9c4", zerolinecolor="#e3bfa1", linecolor="#e3bfa1",
        tickfont=dict(size=11, color="#5b6473"),
    ),
)


def apply_chart_theme(fig):
    """Apply the ESG Pilot design system to any Plotly figure.

    Idempotent — call right before ``st.plotly_chart``. Safe to use on
    figures that already set their own colors; explicit traces win, the
    theme only fills in gaps (axis colors, fonts, hover label, margins).
    """
    if fig is None or not PLOTLY_AVAILABLE:
        return fig
    try:
        fig.update_layout(**LAYOUT_DEFAULTS)
    except Exception:
        pass
    return fig


def charts_available():
    """Return whether Plotly-backed charts can be rendered."""
    return PLOTLY_AVAILABLE


def chart_unavailable_message():
    """Short UI message for environments without Plotly installed."""
    return "Charts are unavailable in this local environment because `plotly` is not installed."


def emissions_donut(scope_totals):
    """Donut chart for Scope 1/2/3 breakdown."""
    if not PLOTLY_AVAILABLE:
        return None
    labels = list(scope_totals.keys())
    values = list(scope_totals.values())
    colors = [COLORS.get(l.lower().replace(" ", ""), COLORS["primary"]) for l in labels]

    fig = go.Figure(go.Pie(
        labels=labels,
        values=values,
        hole=0.55,
        marker=dict(colors=colors),
        textinfo="label+percent",
        textposition="outside",
    ))
    fig.update_layout(
        title="Emissions by Scope",
        showlegend=True,
        **LAYOUT_DEFAULTS,
    )
    total = sum(values)
    fig.add_annotation(
        text=f"<b>{total:,.0f}</b><br>tCO2e",
        x=0.5, y=0.5, showarrow=False,
        font=dict(size=16, color=COLORS["dark"]),
    )
    return fig


def emissions_trend(df):
    """Line chart for emissions trend over time."""
    if not PLOTLY_AVAILABLE:
        return None
    fig = px.line(
        df,
        x="period",
        y="emissions_tco2e",
        color="scope",
        markers=True,
        color_discrete_map={
            "Scope 1": COLORS["scope1"],
            "Scope 2": COLORS["scope2"],
            "Scope 3": COLORS["scope3"],
        },
    )
    fig.update_layout(
        title="Emissions Trend by Scope",
        xaxis_title="Quarter",
        yaxis_title="tCO2e",
        **LAYOUT_DEFAULTS,
    )
    return fig


def compliance_radar(framework_scores):
    """Radar chart for compliance across frameworks."""
    if not PLOTLY_AVAILABLE:
        return None
    categories = list(framework_scores.keys())
    values = list(framework_scores.values())
    values.append(values[0])  # close the polygon
    categories.append(categories[0])

    fig = go.Figure(go.Scatterpolar(
        r=values,
        theta=categories,
        fill="toself",
        fillcolor="rgba(30, 39, 97, 0.15)",
        line=dict(color=COLORS["primary"], width=2),
        marker=dict(size=8),
    ))
    fig.update_layout(
        title="Framework Compliance Score",
        polar=dict(
            radialaxis=dict(range=[0, 100], ticksuffix="%"),
        ),
        **LAYOUT_DEFAULTS,
    )
    return fig


def risk_gauge(score, title="Risk Score"):
    """Gauge chart for risk scores (0-100)."""
    if not PLOTLY_AVAILABLE:
        return None
    if score < 30:
        color = COLORS["success"]
    elif score < 60:
        color = COLORS["warning"]
    else:
        color = COLORS["danger"]

    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=score,
        title=dict(text=title, font=dict(size=16)),
        gauge=dict(
            axis=dict(range=[0, 100]),
            bar=dict(color=color),
            steps=[
                dict(range=[0, 30], color="#E8F5E9"),
                dict(range=[30, 60], color="#FFF3E0"),
                dict(range=[60, 100], color="#FFEBEE"),
            ],
        ),
    ))
    fig.update_layout(height=250, margin=dict(l=20, r=20, t=40, b=20))
    return fig


def quality_bar(quality_scores):
    """Horizontal bar chart for data quality scores."""
    if not PLOTLY_AVAILABLE:
        return None
    categories = list(quality_scores.keys())
    scores = list(quality_scores.values())
    colors = [
        COLORS["success"] if s >= 80
        else COLORS["warning"] if s >= 60
        else COLORS["danger"]
        for s in scores
    ]

    fig = go.Figure(go.Bar(
        x=scores,
        y=categories,
        orientation="h",
        marker=dict(color=colors),
        text=[f"{s}%" for s in scores],
        textposition="outside",
    ))
    fig.update_layout(**LAYOUT_DEFAULTS)
    fig.update_layout(
        title="Data Quality Scores",
        xaxis=dict(range=[0, 105], title="Score (%)"),
    )
    return fig


def supplier_risk_heatmap(suppliers_df):
    """Heatmap for supplier ESG risk."""
    if not PLOTLY_AVAILABLE:
        return None
    import numpy as np

    risk_map = {"Low": 1, "Medium": 2, "High": 3}
    suppliers_df = suppliers_df.copy()
    suppliers_df["risk_value"] = suppliers_df["risk_rating"].map(risk_map)

    fig = go.Figure(go.Bar(
        x=suppliers_df["supplier_name"],
        y=suppliers_df["esg_score"],
        marker=dict(
            color=suppliers_df["risk_value"],
            colorscale=[[0, COLORS["success"]], [0.5, COLORS["warning"]], [1, COLORS["danger"]]],
            cmin=1,
            cmax=3,
            showscale=True,
            colorbar=dict(
                title="Risk",
                tickvals=[1, 2, 3],
                ticktext=["Low", "Medium", "High"],
            ),
        ),
        text=suppliers_df["esg_score"],
        textposition="outside",
    ))
    fig.update_layout(**LAYOUT_DEFAULTS)
    fig.update_layout(
        title="Supplier ESG Scores & Risk Ratings",
        xaxis_title="Supplier",
        yaxis_title="ESG Score",
        xaxis=dict(tickangle=-45),
    )
    return fig


def kpi_card_data(label, value, delta=None, delta_color="normal"):
    """Return dict for Streamlit metric display."""
    return {"label": label, "value": value, "delta": delta, "delta_color": delta_color}


def action_timeline(actions_df):
    """Gantt-like chart for action items."""
    if not PLOTLY_AVAILABLE:
        return None
    colors_map = {
        "Critical": COLORS["danger"],
        "High": COLORS["warning"],
        "Medium": COLORS["info"],
        "Low": COLORS["success"],
    }

    fig = go.Figure()
    for _, row in actions_df.iterrows():
        fig.add_trace(go.Bar(
            x=[row.get("duration_weeks", 4)],
            y=[row["action"]],
            orientation="h",
            marker=dict(color=colors_map.get(row.get("priority", "Medium"), COLORS["info"])),
            name=row.get("priority", "Medium"),
            showlegend=False,
            text=f"{row.get('priority', 'Medium')} - {row.get('duration_weeks', 4)} weeks",
            textposition="inside",
        ))

    fig.update_layout(
        title="Implementation Roadmap",
        xaxis_title="Duration (Weeks)",
        barmode="stack",
        **LAYOUT_DEFAULTS,
    )
    return fig


# ─────────────────────────────────────────────────────────────────────────────
# NEW CHARTS — Presentation features not previously implemented
# ─────────────────────────────────────────────────────────────────────────────


def scope3_xray_map(supply_chain_df):
    """Geographic scatter-map showing Scope 3 supply chain hotspots worldwide."""
    if not PLOTLY_AVAILABLE:
        return None
    country_coords = {
        "China": (35.86, 104.19), "Taiwan": (23.69, 120.96), "India": (20.59, 78.96),
        "South Korea": (35.90, 127.76), "Germany": (51.16, 10.45), "Singapore": (1.35, 103.82),
        "Brazil": (-14.23, -51.92), "Japan": (36.20, 138.25), "Indonesia": (-0.78, 113.92),
        "Switzerland": (46.81, 8.22), "Bangladesh": (23.68, 90.35), "Sweden": (60.12, 18.64),
        "Chile": (-35.67, -71.54), "UAE": (23.42, 53.84), "USA": (37.09, -95.71),
        "Thailand": (15.87, 100.99),
    }

    df = supply_chain_df.copy()
    df["lat"] = df["country"].map(lambda c: country_coords.get(c, (0, 0))[0])
    df["lon"] = df["country"].map(lambda c: country_coords.get(c, (0, 0))[1])

    risk_colors = {"Low": COLORS["success"], "Medium": COLORS["warning"], "High": COLORS["danger"]}
    df["color"] = df["risk_rating"].map(risk_colors)

    fig = go.Figure()
    for risk in ["High", "Medium", "Low"]:
        rdf = df[df["risk_rating"] == risk]
        if rdf.empty:
            continue
        fig.add_trace(go.Scattergeo(
            lat=rdf["lat"], lon=rdf["lon"],
            text=rdf.apply(
                lambda r: f"<b>{r['supplier_name']}</b><br>{r['country']} — {r['sector']}<br>"
                          f"Emissions: {r['emission_contribution_tco2e']:,.0f} tCO2e<br>"
                          f"ESG Score: {r['esg_score']}/100",
                axis=1,
            ),
            marker=dict(
                size=rdf["emission_contribution_tco2e"] / 40,
                color=risk_colors[risk],
                opacity=0.75,
                line=dict(width=1, color="white"),
                sizemin=6,
            ),
            name=f"{risk} Risk",
            hoverinfo="text",
        ))

    fig.update_geos(
        showcountries=True, countrycolor="#d0d0d0",
        showcoastlines=True, coastlinecolor="#aaa",
        showland=True, landcolor="#f8f8f8",
        showocean=True, oceancolor="#eef4fb",
        projection_type="natural earth",
    )
    fig.update_layout(
        title="Scope 3 X-Ray — Global Supply Chain Emission Hotspots",
        height=500,
        margin=dict(l=0, r=0, t=50, b=0),
        font=dict(family="Calibri, sans-serif"),
    )
    return fig


def pipeline_flow_diagram():
    """Sankey diagram showing data flow between the 8 agents."""
    if not PLOTLY_AVAILABLE:
        return None
    labels = [
        "Data Collector",          # 0
        "Regulatory Tracker",      # 1
        "Carbon Accountant",       # 2
        "Risk Predictor",          # 3
        "Audit Agent",             # 4
        "Report Generator",        # 5
        "Action Agent",            # 6
        "Stakeholder Agent",       # 7
    ]
    node_colors = [
        "#2196F3", "#FF9800", "#4CAF50", "#F44336",
        "#607D8B", "#9C27B0", "#E91E63", "#00BCD4",
    ]

    # source -> target -> value (data flow weight)
    links = {
        "source": [0, 0, 0, 1, 2, 1, 2, 3, 3, 4, 5, 5, 6],
        "target": [1, 2, 3, 3, 4, 4, 5, 4, 5, 5, 6, 7, 7],
        "value":  [3, 3, 2, 2, 2, 2, 3, 2, 2, 3, 3, 2, 3],
    }

    fig = go.Figure(go.Sankey(
        node=dict(
            pad=20, thickness=25,
            label=labels,
            color=node_colors,
            line=dict(color="white", width=1),
        ),
        link=dict(
            source=links["source"],
            target=links["target"],
            value=links["value"],
            color=[f"rgba({int(c[1:3],16)},{int(c[3:5],16)},{int(c[5:7],16)},0.25)"
                   for c in [node_colors[s] for s in links["source"]]],
        ),
    ))
    fig.update_layout(
        title="Agent Pipeline — Data Flow Between 8 Agents",
        height=450,
        font=dict(family="Calibri, sans-serif", size=13),
    )
    return fig


def business_impact_gauges():
    """Four large KPI gauges matching Slide 12 — 80%, 5000+, 95%, 24/7."""
    if not PLOTLY_AVAILABLE:
        return None

    fig = make_subplots(
        rows=1, cols=4,
        specs=[[{"type": "indicator"}] * 4],
    )
    metrics = [
        ("Faster Reporting", 80, "%", "Compared to manual frameworks"),
        ("Hours Saved", 5000, "+", "Freed annually across teams"),
        ("Data Accuracy", 95, "%", "AI-driven validation"),
        ("Uptime", 99.7, "%", "Always-on monitoring"),
    ]
    colors = [COLORS["accent"], COLORS["primary"], COLORS["success"], COLORS["info"]]

    for i, (title, value, suffix, desc) in enumerate(metrics):
        fig.add_trace(go.Indicator(
            mode="number+delta",
            value=value,
            number=dict(suffix=suffix, font=dict(size=48, color=colors[i])),
            title=dict(text=f"<b>{title}</b><br><span style='font-size:11px;color:#888'>{desc}</span>", font=dict(size=14)),
        ), row=1, col=i+1)

    fig.update_layout(height=220, margin=dict(l=20, r=20, t=30, b=10))
    return fig


def before_after_comparison():
    """Before/After transformation bar comparison (Slide 13)."""
    if not PLOTLY_AVAILABLE:
        return None
    categories = ["Reporting Cycle", "Scope 3 Coverage", "Data Accuracy", "ESG Rating", "Audit Readiness"]
    before = [100, 60, 72, 65, 55]  # percentages (reporting = weeks mapped to %)
    after = [20, 90, 95, 88, 92]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=categories, x=before, orientation="h",
        name="Before (Manual)", marker_color="#bbb",
        text=[f"{v}%" for v in before], textposition="inside",
    ))
    fig.add_trace(go.Bar(
        y=categories, x=after, orientation="h",
        name="After (ESG Pilot)", marker_color=COLORS["accent"],
        text=[f"{v}%" for v in after], textposition="inside",
    ))
    fig.update_layout(**LAYOUT_DEFAULTS)
    fig.update_layout(
        title="Real-World Transformation — Before vs. After",
        xaxis_title="Score / Coverage (%)",
        barmode="group",
        height=350,
        legend=dict(orientation="h", y=1.12),
    )
    return fig


def enterprise_stack_layers():
    """Horizontal stacked bar representing the 7-layer Enterprise Stack Architecture (Slide 10)."""
    if not PLOTLY_AVAILABLE:
        return None
    layers = [
        ("Layer 7", "Command Center UI", "Streamlit + Gradio dashboards", COLORS["accent"]),
        ("Layer 6", "8 Orchestrated Agents", "Autonomous AI agents", "#E91E63"),
        ("Layer 5", "Foundational AI Models", "HuggingFace / LLM inference", "#9C27B0"),
        ("Layer 4", "Integration & Connectors", "ERP, HR, IoT, API connectors", "#2196F3"),
        ("Layer 3", "Data Lake", "Unified ESG data storage", "#00BCD4"),
        ("Layer 2", "Governance & Security", "Access control, encryption, audit logs", "#607D8B"),
        ("Layer 1", "Cloud Foundation", "Infrastructure & compute", "#455A64"),
    ]

    fig = go.Figure()
    for i, (layer_id, name, desc, color) in enumerate(layers):
        width = 100 - i * 4  # pyramid narrowing
        fig.add_trace(go.Bar(
            y=[layer_id],
            x=[width],
            orientation="h",
            marker=dict(color=color, opacity=0.85),
            text=f"<b>{name}</b> — {desc}",
            textposition="inside",
            textfont=dict(color="white", size=12),
            showlegend=False,
        ))

    fig.update_layout(**LAYOUT_DEFAULTS)
    fig.update_layout(
        title="Enterprise Stack Architecture",
        xaxis=dict(showticklabels=False, showgrid=False, zeroline=False),
        yaxis=dict(autorange="reversed"),
        height=400,
        bargap=0.15,
    )
    return fig


def connector_status_chart(statuses):
    """Horizontal bar chart showing connector sync status."""
    if not PLOTLY_AVAILABLE:
        return None
    names = [s["name"] for s in statuses.values()]
    status_map = {"synced": 100, "streaming": 100, "connected": 75, "error": 20, "disconnected": 0}
    values = [status_map.get(s["status"], 0) for s in statuses.values()]
    colors = [
        COLORS["success"] if v >= 90 else COLORS["warning"] if v >= 50 else COLORS["danger"]
        for v in values
    ]

    fig = go.Figure(go.Bar(
        y=names, x=values, orientation="h",
        marker=dict(color=colors),
        text=[s["status"].capitalize() for s in statuses.values()],
        textposition="inside",
    ))
    fig.update_layout(**LAYOUT_DEFAULTS)
    fig.update_layout(
        title="Enterprise Connector Status",
        xaxis=dict(range=[0, 110], title="Sync Health (%)"),
        height=300,
    )
    return fig


def monitoring_timeline(alerts):
    """Timeline scatter plot of monitoring alerts by severity."""
    if not PLOTLY_AVAILABLE:
        return None
    if not alerts:
        return None

    severity_y = {"critical": 3, "warning": 2, "info": 1}
    severity_colors = {"critical": COLORS["danger"], "warning": COLORS["warning"], "info": COLORS["info"]}

    fig = go.Figure()
    for sev in ["critical", "warning", "info"]:
        sev_alerts = [a for a in alerts if a["severity"] == sev]
        if not sev_alerts:
            continue
        fig.add_trace(go.Scatter(
            x=[a["timestamp"][:16] for a in sev_alerts],
            y=[severity_y[sev]] * len(sev_alerts),
            mode="markers+text",
            marker=dict(size=14, color=severity_colors[sev], symbol="circle"),
            text=[a["type"][:12] for a in sev_alerts],
            textposition="top center",
            name=sev.capitalize(),
            hovertext=[a["message"] for a in sev_alerts],
            hoverinfo="text",
        ))

    fig.update_layout(**LAYOUT_DEFAULTS)
    fig.update_layout(
        title="24/7 Monitoring — Alert Timeline",
        yaxis=dict(tickvals=[1, 2, 3], ticktext=["Info", "Warning", "Critical"], range=[0.5, 3.5]),
        xaxis_title="Timestamp",
        height=300,
    )
    return fig


def tier_comparison_chart():
    """Grouped bar chart comparing Starter / Professional / Enterprise tiers (Slide 14)."""
    if not PLOTLY_AVAILABLE:
        return None
    features = ["Agents Active", "Frameworks", "Data Sources", "Refresh Rate", "Support", "Custom Reports"]
    starter = [3, 1, 2, 10, 30, 20]
    professional = [6, 3, 4, 60, 70, 60]
    enterprise = [8, 4, 6, 100, 100, 100]

    fig = go.Figure()
    fig.add_trace(go.Bar(name="Starter", y=features, x=starter, orientation="h", marker_color="#bbb"))
    fig.add_trace(go.Bar(name="Professional", y=features, x=professional, orientation="h", marker_color=COLORS["warning"]))
    fig.add_trace(go.Bar(name="Enterprise", y=features, x=enterprise, orientation="h", marker_color=COLORS["accent"]))

    fig.update_layout(**LAYOUT_DEFAULTS)
    fig.update_layout(
        title="Tier Comparison — Feature Coverage (%)",
        barmode="group",
        xaxis_title="Capability Level",
        height=350,
        legend=dict(orientation="h", y=1.12),
    )
    return fig
