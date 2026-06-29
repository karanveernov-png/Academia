"""
tabs.attendance_tab
====================
Renders the Attendance module.
ALL data comes from the user-uploaded file — no hardcoded students.
Supports any CSV/Excel column layout via the sidebar column mapper.
"""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go

from core.ui_components import render_html, kpi_card, att_column_mapper_ui
from core.data_loader import load_file
from core.config import CHART_BG, CHART_FONT, GRID_COLOR, TITLE_FONT, ACCENT_SEQ


# ── Chart helpers ────────────────────────────────────────────────────────────

def _chart_defaults(fig, height=320):
    fig.update_layout(
        paper_bgcolor=CHART_BG, plot_bgcolor=CHART_BG,
        font=dict(color=CHART_FONT, family="Inter, sans-serif", size=12),
        title=dict(font=dict(color=TITLE_FONT, size=14), x=0.01, xanchor="left"),
        margin=dict(l=10, r=10, t=48, b=10), height=height,
        legend=dict(bgcolor="rgba(255,255,255,0.04)", bordercolor="rgba(255,255,255,0.08)",
                    borderwidth=1, font=dict(size=11)),
        hoverlabel=dict(bgcolor="rgba(15,12,41,0.95)", bordercolor="rgba(99,102,241,0.5)",
                        font_color="#e2e8f0", font_size=12),
    )
    fig.update_xaxes(gridcolor=GRID_COLOR, zeroline=False, tickfont=dict(size=11), showline=False)
    fig.update_yaxes(gridcolor=GRID_COLOR, zeroline=False, tickfont=dict(size=11), showline=False)
    return fig


def _chart_att_distribution(df, pct_col):
    fig = px.histogram(df, x=pct_col, nbins=20, title="📊 Attendance % Distribution",
                       color_discrete_sequence=["#f97316"])
    fig.update_traces(opacity=0.85, marker_line_color="rgba(56,189,248,0.3)", marker_line_width=1)
    return _chart_defaults(fig)


def _chart_class_avg(df, class_col, pct_col):
    avg = df.groupby(class_col)[pct_col].mean().reset_index()
    avg.columns = ["Class", "Avg Attendance %"]
    avg = avg.sort_values("Avg Attendance %", ascending=True)
    fig = px.bar(avg, x="Avg Attendance %", y="Class", orientation="h",
                 title="🏫 Average Attendance by Class",
                 color="Avg Attendance %",
                 color_continuous_scale=["#f87171","#fbbf24","#34d399"])
    fig.update_coloraxes(showscale=False)
    return _chart_defaults(fig)


def _chart_present_absent_pie(df, present_col, absent_col, late_col=None):
    totals = {}
    if present_col: totals["Present"] = df[present_col].sum()
    if absent_col:  totals["Absent"]  = df[absent_col].sum()
    if late_col and late_col in df.columns:
        totals["Late"] = df[late_col].sum()
    labels = list(totals.keys())
    values = list(totals.values())
    colors = ["#34d399","#f87171","#fbbf24"][:len(labels)]
    fig = go.Figure(go.Pie(
        labels=labels, values=values, hole=0.5,
        marker=dict(colors=colors, line=dict(color="rgba(0,0,0,0)", width=2)),
        textfont=dict(size=12), hovertemplate="%{label}: %{value:,} days<extra></extra>"
    ))
    fig.update_layout(title="🔵 Overall Attendance Breakdown", showlegend=True)
    return _chart_defaults(fig, height=300)


def _chart_top_absentees(df, name_col, absent_col, top_n=10):
    tmp = df[[name_col, absent_col]].copy()
    tmp.columns = ["Student", "Absent Days"]
    tmp = tmp.sort_values("Absent Days", ascending=False).head(top_n)
    fig = px.bar(tmp, x="Absent Days", y="Student", orientation="h",
                 title=f"🚨 Top {top_n} Most Absent Students",
                 color="Absent Days", color_continuous_scale=["#fbbf24","#f87171"])
    fig.update_coloraxes(showscale=False)
    return _chart_defaults(fig)


# ── Main render ──────────────────────────────────────────────────────────────

def render_attendance_tab(att_file):
    """Render the full attendance module from uploaded file."""

    # ── Hero banner ──────────────────────────────────────────────────────
    render_html("""
    <div style='position:relative;background:linear-gradient(135deg,#0f3460 0%,#16213e 50%,#0d1b2a 100%);
        padding:1.6rem 2rem;border-radius:18px;margin-bottom:1.4rem;overflow:hidden;
        box-shadow:0 16px 48px rgba(0,0,0,0.45),inset 0 1px 0 rgba(255,255,255,0.07);'>
        <div style="position:absolute;top:-30px;right:-20px;width:160px;height:160px;
            background:radial-gradient(circle,rgba(56,189,248,0.2),transparent 70%);border-radius:50%;"></div>
        <div style='position:relative;z-index:1;'>
            <div style='display:flex;align-items:center;gap:0.8rem;margin-bottom:0.3rem;'>
                <span style='font-size:2rem;filter:drop-shadow(0 0 12px rgba(56,189,248,0.5));'>✅</span>
                <h2 style='color:white!important;margin:0;font-size:1.55rem;font-weight:800;'>
                    Attendance Tracker
                </h2>
            </div>
            <p style='color:rgba(255,255,255,0.6);margin:0;font-size:0.83rem;'>
                Overview · By class · At-risk students · Absence analysis
            </p>
        </div>
    </div>
    """)

    # ── Load data ─────────────────────────────────────────────────────────
    df_raw, err = load_file(att_file)
    if err:
        st.error(f"❌ Could not load file: {err}")
        return
    if df_raw is None or df_raw.empty:
        st.warning("The uploaded file appears to be empty.")
        return

    st.markdown(
        f'<div class="file-info-bar">📄 <b>{att_file.name}</b> — '
        f'{len(df_raw):,} rows × {len(df_raw.columns)} columns</div>',
        unsafe_allow_html=True
    )

    # ── Column mapping ────────────────────────────────────────────────────
    m = att_column_mapper_ui(df_raw, key_prefix="att")

    # ── Prepare working dataframe ─────────────────────────────────────────
    df = df_raw.copy()

    # Numeric coerce
    for col in [m["present"], m["absent"], m["late"], m["total"], m["pct"]]:
        if col and col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Compute attendance % if not provided but present+absent available
    if not m["pct"] or m["pct"] not in df.columns:
        if m["present"] and m["absent"]:
            late_vals = df[m["late"]] if m["late"] and m["late"] in df.columns else 0
            total = df[m["present"]] + df[m["absent"]] + (late_vals if isinstance(late_vals, pd.Series) else 0)
            numer = df[m["present"]] + (late_vals * 0.5 if isinstance(late_vals, pd.Series) else 0)
            df["__att_pct__"] = (numer / total.replace(0, np.nan) * 100).round(1)
            m["pct"] = "__att_pct__"

    # ── Check we have enough to work with ────────────────────────────────
    if not m["pct"] or m["pct"] not in df.columns:
        st.warning("⚠️ Please map at least the **Present Days** and **Absent Days** columns (or an **Attendance %** column) in the sidebar.")
        st.dataframe(df_raw.head(10), use_container_width=True)
        return

    pct_col = m["pct"]
    at_risk_thresh = st.sidebar.slider("⚠️ At-risk threshold (%)", 50, 90, 75, key="att_thresh")

    # ── KPIs ──────────────────────────────────────────────────────────────
    total_students = len(df)
    avg_att  = round(df[pct_col].mean(), 1)
    above    = int((df[pct_col] >= at_risk_thresh).sum())
    atrisk   = int((df[pct_col] < at_risk_thresh).sum())
    perfect  = int((df[pct_col] >= 95).sum())

    st.markdown('<div class="section-header">📊 Key Metrics</div>', unsafe_allow_html=True)
    c1,c2,c3,c4,c5 = st.columns(5)
    c1.markdown(kpi_card("👥", total_students, "Total Students", variant="sky"),  unsafe_allow_html=True)
    c2.markdown(kpi_card("📈", f"{avg_att}%", "Avg Attendance", variant=""),      unsafe_allow_html=True)
    c3.markdown(kpi_card("✅", above, f"Above {at_risk_thresh}%", variant="green"),unsafe_allow_html=True)
    c4.markdown(kpi_card("⚠️", atrisk, "At Risk", variant="amber"),               unsafe_allow_html=True)
    c5.markdown(kpi_card("🌟", perfect, "Perfect (≥95%)", variant="gold"),         unsafe_allow_html=True)

    # ── Alert ─────────────────────────────────────────────────────────────
    if atrisk > 0:
        render_html(f"""
        <div style='background:rgba(245,158,11,0.08);border:1px solid rgba(245,158,11,0.25);
            border-radius:10px;padding:10px 14px;font-size:0.82rem;color:#fcd34d;margin:0.8rem 0;'>
            ⚠️ <b>{atrisk} student{'s' if atrisk!=1 else ''}</b> below {at_risk_thresh}% attendance — review required.
        </div>
        """)

    # ── Tabs ──────────────────────────────────────────────────────────────
    tab_labels = ["📋 Overview", "🏫 By Class", "🚨 At Risk", "📉 Charts"]
    tabs = st.tabs(tab_labels)

    # ── Overview tab ──────────────────────────────────────────────────────
    with tabs[0]:
        st.markdown('<div class="section-header">📋 All Students</div>', unsafe_allow_html=True)

        # Filter by class if available
        if m["class"] and m["class"] in df.columns:
            classes = ["All"] + sorted(df[m["class"]].dropna().unique().tolist())
            cls_filter = st.selectbox("Filter by class", classes, key="att_cls_filter")
            disp = df if cls_filter == "All" else df[df[m["class"]] == cls_filter]
        else:
            disp = df

        # Build display columns
        show_cols = {}
        for role, label in [("name","Student"), ("id","ID"), ("class","Class"),
                             ("present","Present"), ("absent","Absent"), ("late","Late"),
                             ("total","Total Days")]:
            if m[role] and m[role] in df.columns:
                show_cols[m[role]] = label
        show_cols[pct_col] = "Attendance %"

        disp_view = disp[list(show_cols.keys())].rename(columns=show_cols)

        # Status column
        def status(p):
            if p >= 85: return "Good"
            elif p >= at_risk_thresh: return "Average"
            else: return "At Risk"

        def status_color(p):
            if p >= 85: return "background-color:#10b98122"
            elif p >= at_risk_thresh: return "background-color:#f59e0b22"
            else: return "background-color:#ef444422"

        disp_view["Status"] = disp_view["Attendance %"].apply(status)
        styled = disp_view.style.map(status_color, subset=["Attendance %"])
        st.dataframe(styled, use_container_width=True, height=400)

        csv = disp_view.to_csv(index=False).encode()
        st.download_button("⬇️ Download CSV", csv, "attendance_overview.csv", "text/csv")

    # ── By Class tab ──────────────────────────────────────────────────────
    with tabs[1]:
        if not m["class"] or m["class"] not in df.columns:
            st.info("Map a **Class / Section** column to see per-class breakdown.")
        else:
            st.markdown('<div class="section-header">🏫 By Class Summary</div>', unsafe_allow_html=True)
            grp = df.groupby(m["class"])
            rows = []
            for cls, g in grp:
                r = {"Class": cls, "Students": len(g),
                     "Avg Attendance %": round(g[pct_col].mean(), 1),
                     "At Risk": int((g[pct_col] < at_risk_thresh).sum()),
                     "Above 85%": int((g[pct_col] >= 85).sum())}
                if m["absent"] and m["absent"] in df.columns:
                    r["Total Absences"] = int(g[m["absent"]].sum())
                rows.append(r)
            summary_df = pd.DataFrame(rows).sort_values("Avg Attendance %")

            def color_avg(val):
                if val >= 85: return "background-color:#10b98120"
                elif val >= at_risk_thresh: return "background-color:#f59e0b20"
                else: return "background-color:#ef444420"

            styled_sum = summary_df.style.map(color_avg, subset=["Avg Attendance %"])
            st.dataframe(styled_sum, use_container_width=True, height=350)

            # Bar chart per class
            if m["class"] in df.columns:
                fig = _chart_class_avg(df, m["class"], pct_col)
                st.plotly_chart(fig, use_container_width=True, key="att_class_chart")

    # ── At Risk tab ───────────────────────────────────────────────────────
    with tabs[2]:
        st.markdown(f'<div class="section-header">🚨 Students Below {at_risk_thresh}%</div>',
                    unsafe_allow_html=True)
        atrisk_df = df[df[pct_col] < at_risk_thresh].copy()
        atrisk_df = atrisk_df.sort_values(pct_col)

        if atrisk_df.empty:
            st.success(f"🎉 No students below {at_risk_thresh}% attendance!")
        else:
            show_cols2 = {}
            for role, label in [("name","Student"), ("id","ID"), ("class","Class"),
                                 ("absent","Absent Days"), ("late","Late Days")]:
                if m[role] and m[role] in df.columns:
                    show_cols2[m[role]] = label
            show_cols2[pct_col] = "Attendance %"
            atrisk_view = atrisk_df[list(show_cols2.keys())].rename(columns=show_cols2)
            st.dataframe(atrisk_view, use_container_width=True, height=400)

            csv2 = atrisk_view.to_csv(index=False).encode()
            st.download_button("⬇️ Download At-Risk List", csv2,
                               f"at_risk_below_{at_risk_thresh}pct.csv", "text/csv")

    # ── Charts tab ────────────────────────────────────────────────────────
    with tabs[3]:
        st.markdown('<div class="section-header">📉 Visualisations</div>', unsafe_allow_html=True)

        col_a, col_b = st.columns(2)
        with col_a:
            fig_dist = _chart_att_distribution(df, pct_col)
            st.plotly_chart(fig_dist, use_container_width=True, key="att_dist")

        with col_b:
            if m["present"] and m["absent"]:
                fig_pie = _chart_present_absent_pie(df, m["present"], m["absent"], m["late"])
                st.plotly_chart(fig_pie, use_container_width=True, key="att_pie")
            else:
                st.info("Map Present/Absent columns for breakdown pie chart.")

        if m["name"] and m["absent"] and m["absent"] in df.columns:
            top_n = st.slider("Top N absentees", 5, 20, 10, key="att_topn")
            fig_abs = _chart_top_absentees(df, m["name"], m["absent"], top_n)
            st.plotly_chart(fig_abs, use_container_width=True, key="att_absentees")

    # ── Raw data ──────────────────────────────────────────────────────────
    with st.expander("🗃️ Raw Data", expanded=False):
        st.dataframe(df_raw, use_container_width=True)
        st.download_button("⬇️ Download Raw CSV", df_raw.to_csv(index=False).encode(),
                           "attendance_raw.csv", "text/csv")
