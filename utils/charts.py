"""Chart generation utilities using Plotly."""
import plotly.graph_objects as go
import plotly.express as px


COLORS = {
    "primary": "#1E2761",
    "secondary": "#CADCFC",
    "accent": "#E8453C",
    "success": "#4CAF50",
    "warning": "#FF9800",
    "danger": "#F44336",
    "info": "#2196F3",
    "dark": "#212121",
    "light": "#F5F5F5",
    "scope1": "#E8453C",
    "scope2": "#FF9800",
    "scope3": "#1E2761",
}

LAYOUT_DEFAULTS = dict(
    font=dict(family="Calibri, sans-serif"),
    plot_bgcolor="rgba(0,0,0,0)",
    paper_bgcolor="rgba(0,0,0,0)",
    margin=dict(l=40, r=40, t=50, b=40),
)


def emissions_donut(scope_totals):
    """Donut chart for Scope 1/2/3 breakdown."""
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
    fig.update_layout(
        title="Data Quality Scores",
        xaxis=dict(range=[0, 105], title="Score (%)"),
        **LAYOUT_DEFAULTS,
    )
    return fig


def supplier_risk_heatmap(suppliers_df):
    """Heatmap for supplier ESG risk."""
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
    fig.update_layout(
        title="Supplier ESG Scores & Risk Ratings",
        xaxis_title="Supplier",
        yaxis_title="ESG Score",
        xaxis=dict(tickangle=-45),
        **LAYOUT_DEFAULTS,
    )
    return fig


def kpi_card_data(label, value, delta=None, delta_color="normal"):
    """Return dict for Streamlit metric display."""
    return {"label": label, "value": value, "delta": delta, "delta_color": delta_color}


def action_timeline(actions_df):
    """Gantt-like chart for action items."""
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
