"""
core.charts
===========
All Plotly figure builders. Warm orange / terracotta theme matching the login page.
"""
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go

from core.config import CHART_BG, CHART_FONT, GRID_COLOR, TITLE_FONT, ACCENT_SEQ, RISK_COLORS


def chart_defaults(fig, height=320):
    fig.update_layout(
        paper_bgcolor=CHART_BG,
        plot_bgcolor=CHART_BG,
        font=dict(color=CHART_FONT, family="Inter, sans-serif", size=12),
        title=dict(font=dict(color=TITLE_FONT, size=14, family="Inter, sans-serif"),
                   x=0.01, xanchor="left"),
        margin=dict(l=10, r=10, t=48, b=10),
        height=height,
        legend=dict(
            bgcolor="rgba(255,255,255,0.04)",
            bordercolor="rgba(255,255,255,0.08)",
            borderwidth=1,
            font=dict(size=11),
        ),
        hoverlabel=dict(
            bgcolor="rgba(30,15,5,0.95)",
            bordercolor="rgba(249,115,22,0.5)",
            font_color="#e2e8f0",
            font_size=12,
        ),
    )
    fig.update_xaxes(
        gridcolor=GRID_COLOR, zeroline=False,
        tickfont=dict(size=11), showline=False,
    )
    fig.update_yaxes(
        gridcolor=GRID_COLOR, zeroline=False,
        tickfont=dict(size=11), showline=False,
    )
    return fig


def chart_score_distribution(df):
    fig = px.histogram(
        df, x="Total_Marks", nbins=20,
        title="📊 Score Distribution",
        color_discrete_sequence=["#f97316"],
    )
    fig.update_traces(
        opacity=0.85,
        marker_line_color="rgba(249,115,22,0.3)",
        marker_line_width=1,
    )
    return chart_defaults(fig)


def chart_grade_pie(df):
    grade_order = ["A+", "A", "B+", "B", "C", "D", "F"]
    grade_colors = {
        "A+": "#10b981", "A": "#34d399",
        "B+": "#f97316", "B": "#fb923c",
        "C":  "#fbbf24", "D": "#f59e0b",
        "F":  "#ef4444",
    }
    vc = df["Grade"].value_counts().reindex(grade_order).dropna().reset_index()
    vc.columns = ["Grade", "Count"]
    fig = px.pie(
        vc, names="Grade", values="Count",
        title="🎓 Grade Distribution",
        color="Grade",
        color_discrete_map=grade_colors,
        hole=0.52,
    )
    fig.update_traces(
        textfont_color="#ffffff",
        textfont_size=12,
        pull=[0.03] * len(vc),
    )
    fig.update_layout(
        legend=dict(orientation="v", yanchor="middle", y=0.5, xanchor="left", x=1.01),
    )
    return chart_defaults(fig)


def chart_subject_bar(df, mark_cols):
    if not mark_cols:
        return None
    avgs = {c: round(df[c].mean(), 1) for c in mark_cols if c in df.columns}
    fig = px.bar(
        x=list(avgs.keys()), y=list(avgs.values()),
        title="📚 Average Score per Subject",
        labels={"x": "Subject", "y": "Average Marks"},
        color=list(avgs.values()),
        color_continuous_scale=[[0, "#7c2d12"], [0.5, "#ea580c"], [1, "#fdba74"]],
        text_auto=".1f",
    )
    fig.update_traces(
        textfont_color="#ffffff",
        textfont_size=12,
        marker_line_color="rgba(255,255,255,0.1)",
        marker_line_width=1,
    )
    fig.update_coloraxes(showscale=False)
    return chart_defaults(fig)


def chart_risk_bar(df):
    rc = df["Risk"].value_counts().reset_index()
    rc.columns = ["Risk", "Count"]
    fig = px.bar(
        rc, x="Risk", y="Count",
        title="⚠️ Risk Level Distribution",
        color="Risk",
        color_discrete_map=RISK_COLORS,
        text_auto=True,
    )
    fig.update_traces(
        textfont_color="#fff",
        textfont_size=13,
        textfont_weight="bold",
        marker_line_color="rgba(255,255,255,0.1)",
        marker_line_width=1,
    )
    return chart_defaults(fig)


def chart_top_n_students(df, n=10):
    n = min(n, len(df))
    top = df.nlargest(n, "Total_Marks")[["Student_Name", "Total_Marks", "Percentage", "Grade"]]
    fig = px.bar(
        top, x="Total_Marks", y="Student_Name",
        orientation="h",
        title=f"🏆 Top {n} Students",
        color="Total_Marks",
        color_continuous_scale=[[0, "#7c2d12"], [0.5, "#f97316"], [1, "#fdba74"]],
        text="Total_Marks",
        hover_data=["Percentage", "Grade"],
    )
    fig.update_yaxes(categoryorder="total ascending")
    fig.update_coloraxes(showscale=False)
    fig.update_traces(
        textfont_color="#fff",
        textfont_size=11,
        marker_line_color="rgba(255,255,255,0.1)",
        marker_line_width=1,
    )
    return chart_defaults(fig, height=max(280, n * 30))


def chart_scatter_percentile(df):
    df2 = df.copy()
    df2["Rank"] = df2["Total_Marks"].rank(ascending=False, method="min").astype(int)
    fig = px.scatter(
        df2, x="Rank", y="Total_Marks",
        color="Risk",
        title="🎯 Marks vs Class Rank",
        color_discrete_map=RISK_COLORS,
        hover_data=["Student_Name", "Percentage", "Grade"],
        size_max=10,
    )
    fig.update_traces(marker=dict(size=8, opacity=0.85, line=dict(width=1, color="rgba(255,255,255,0.2)")))
    return chart_defaults(fig)


def chart_class_box(df):
    if df["Class"].nunique() <= 1 or df["Class"].iloc[0] == "N/A":
        return None
    fig = px.box(
        df, x="Class", y="Total_Marks",
        title="🏫 Score Spread by Class / Section",
        color="Class",
        color_discrete_sequence=ACCENT_SEQ,
    )
    return chart_defaults(fig)


def chart_gender_avg(df):
    if df["Gender"].nunique() <= 1 or df["Gender"].iloc[0] == "N/A":
        return None
    ga = df.groupby("Gender")["Total_Marks"].mean().reset_index()
    fig = px.bar(
        ga, x="Gender", y="Total_Marks",
        title="⚧ Average Marks by Gender",
        color="Gender",
        color_discrete_sequence=["#f97316", "#fbbf24"],
        text_auto=".1f",
    )
    fig.update_traces(
        textfont_color="#fff",
        textfont_size=13,
        marker_line_color="rgba(255,255,255,0.1)",
        marker_line_width=1,
    )
    return chart_defaults(fig)


# ════════════════════════════════════════════════════════════════════════════
#  NEW DIAGRAMS
# ════════════════════════════════════════════════════════════════════════════
def chart_subject_correlation(df, mark_cols):
    """Heatmap of correlation between subjects — which subjects move together."""
    cols = [c for c in mark_cols if c in df.columns]
    if len(cols) < 2:
        return None
    corr = df[cols].corr().round(2)
    fig = go.Figure(
        data=go.Heatmap(
            z=corr.values, x=corr.columns, y=corr.columns,
            colorscale=[[0, "#7c2d12"], [0.5, "#f97316"], [1, "#fbbf24"]],
            zmin=-1, zmax=1,
            text=corr.values, texttemplate="%{text}",
            textfont=dict(color="#fff", size=11),
            hovertemplate="%{x} vs %{y}: %{z}<extra></extra>",
            colorbar=dict(thickness=14, outlinewidth=0),
        )
    )
    fig.update_layout(title="🧩 Subject Correlation")
    return chart_defaults(fig, height=max(320, len(cols) * 45))


def chart_subject_radar(df, mark_cols):
    """Class average vs. top scorer, per subject, on one radar chart."""
    cols = [c for c in mark_cols if c in df.columns]
    if len(cols) < 3:
        return None
    avg_vals = [round(df[c].mean(), 1) for c in cols]
    max_vals = [round(df[c].max(), 1) for c in cols]
    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(
        r=max_vals + max_vals[:1], theta=cols + cols[:1],
        name="Top Scorer", fill="toself",
        line_color="#fbbf24", fillcolor="rgba(251,191,36,0.15)",
    ))
    fig.add_trace(go.Scatterpolar(
        r=avg_vals + avg_vals[:1], theta=cols + cols[:1],
        name="Class Average", fill="toself",
        line_color="#f97316", fillcolor="rgba(249,115,22,0.25)",
    ))
    fig.update_layout(
        title="🕸️ Subject Strengths — Average vs Top Scorer",
        polar=dict(
            bgcolor="rgba(0,0,0,0)",
            radialaxis=dict(gridcolor=GRID_COLOR, color=CHART_FONT),
            angularaxis=dict(gridcolor=GRID_COLOR, color=CHART_FONT),
        ),
        showlegend=True,
    )
    return chart_defaults(fig, height=380)


def chart_pass_fail_funnel(df, detain_threshold=33.0):
    """Funnel showing class narrowing: Total → Passing → Above Average → Top Decile."""
    total = len(df)
    if total == 0:
        return None
    passing = int((df["Percentage"] >= detain_threshold).sum())
    above_avg = int((df["Percentage"] >= df["Percentage"].mean()).sum())
    top_decile_cutoff = df["Percentage"].quantile(0.9)
    top_decile = int((df["Percentage"] >= top_decile_cutoff).sum())

    fig = go.Figure(go.Funnel(
        y=["Total Students", "Passing", "Above Class Average", "Top 10%"],
        x=[total, passing, above_avg, top_decile],
        textinfo="value+percent initial",
        marker=dict(color=["#fb923c", "#f97316", "#ea580c", "#fbbf24"]),
        connector=dict(line=dict(color=GRID_COLOR, width=1)),
    ))
    fig.update_layout(title="🔻 Class Performance Funnel")
    return chart_defaults(fig)
