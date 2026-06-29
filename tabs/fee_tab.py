"""
tabs.fee_tab
=============
Renders the Fee Controller module.
ALL data comes from the user-uploaded file — no hardcoded records.
Supports any CSV/Excel column layout via sidebar column mapper.
"""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go

from core.ui_components import render_html, kpi_card, fee_column_mapper_ui
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


def _chart_status_pie(df, status_col):
    counts = df[status_col].value_counts().reset_index()
    counts.columns = ["Status", "Count"]
    color_map = {"Paid":"#10b981","Overdue":"#ef4444","Partial":"#c2410c",
                 "Pending":"#f59e0b","Upcoming":"#f97316","Due":"#f59e0b"}
    fig = go.Figure(go.Pie(
        labels=counts["Status"], values=counts["Count"], hole=0.5,
        marker=dict(colors=[color_map.get(s,"#f97316") for s in counts["Status"]],
                    line=dict(color="rgba(0,0,0,0)", width=2)),
        textfont=dict(size=12),
        hovertemplate="%{label}: %{value} records<extra></extra>"
    ))
    fig.update_layout(title="💳 Payment Status Breakdown", showlegend=True)
    return _chart_defaults(fig, height=300)


def _chart_collection_by_class(df, class_col, paid_col):
    grp = df.groupby(class_col)[paid_col].sum().reset_index()
    grp.columns = ["Class", "Total Collected"]
    grp = grp.sort_values("Total Collected", ascending=True)
    fig = px.bar(grp, x="Total Collected", y="Class", orientation="h",
                 title="🏫 Fee Collection by Class",
                 color="Total Collected",
                 color_continuous_scale=["#c2410c","#f97316","#f97316"])
    fig.update_coloraxes(showscale=False)
    return _chart_defaults(fig)


def _chart_due_vs_paid(df, due_col, paid_col):
    total_due  = df[due_col].sum()
    total_paid = df[paid_col].sum()
    balance    = total_due - total_paid
    fig = go.Figure(go.Bar(
        x=["Total Due","Total Collected","Outstanding Balance"],
        y=[total_due, total_paid, max(balance, 0)],
        marker_color=["#f97316","#10b981","#ef4444"],
        text=[f"₹{total_due:,.0f}", f"₹{total_paid:,.0f}", f"₹{max(balance,0):,.0f}"],
        textposition="outside", textfont=dict(color="#e2e8f0", size=11),
    ))
    fig.update_layout(title="💰 Due vs Collected vs Outstanding")
    return _chart_defaults(fig)


# ── Badge HTML ───────────────────────────────────────────────────────────────

def _status_badge(status):
    status = str(status).strip()
    cls = {
        "Paid": "badge-paid", "Overdue": "badge-overdue",
        "Partial": "badge-partial", "Pending": "badge-due",
        "Upcoming": "badge-blue", "Due": "badge-due",
    }.get(status, "badge-purple")
    return f'<span class="badge {cls}">{status}</span>'


# ── Main render ──────────────────────────────────────────────────────────────

def render_fee_tab(fee_file):
    """Render the full fee controller module from uploaded file."""

    # ── Hero banner ──────────────────────────────────────────────────────
    render_html("""
    <div style='position:relative;background:linear-gradient(135deg,#1a0a00 0%,#2d1600 40%,#1a0e00 100%);
        padding:1.6rem 2rem;border-radius:18px;margin-bottom:1.4rem;overflow:hidden;
        box-shadow:0 16px 48px rgba(0,0,0,0.45),inset 0 1px 0 rgba(255,255,255,0.07);'>
        <div style="position:absolute;top:-30px;right:-20px;width:160px;height:160px;
            background:radial-gradient(circle,rgba(251,191,36,0.2),transparent 70%);border-radius:50%;"></div>
        <div style='position:relative;z-index:1;'>
            <div style='display:flex;align-items:center;gap:0.8rem;margin-bottom:0.3rem;'>
                <span style='font-size:2rem;filter:drop-shadow(0 0 12px rgba(251,191,36,0.5));'>💰</span>
                <h2 style='color:white!important;margin:0;font-size:1.55rem;font-weight:800;'>
                    Fee Controller
                </h2>
            </div>
            <p style='color:rgba(255,255,255,0.6);margin:0;font-size:0.83rem;'>
                Payment tracking · Outstanding dues · Collection analysis · Export
            </p>
        </div>
    </div>
    """)

    # ── Load data ─────────────────────────────────────────────────────────
    df_raw, err = load_file(fee_file)
    if err:
        st.error(f"❌ Could not load file: {err}")
        return
    if df_raw is None or df_raw.empty:
        st.warning("The uploaded file appears to be empty.")
        return

    st.markdown(
        f'<div class="file-info-bar">📄 <b>{fee_file.name}</b> — '
        f'{len(df_raw):,} rows × {len(df_raw.columns)} columns</div>',
        unsafe_allow_html=True
    )

    # ── Column mapping ────────────────────────────────────────────────────
    m = fee_column_mapper_ui(df_raw, key_prefix="fee")

    df = df_raw.copy()

    # Numeric coerce for money columns
    for col in [m["due"], m["paid"], m["balance"]]:
        if col and col in df.columns:
            # Strip currency symbols
            df[col] = df[col].astype(str).str.replace(r"[₹$,]", "", regex=True)
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    # Auto-compute balance if not provided
    if (not m["balance"] or m["balance"] not in df.columns) and m["due"] and m["paid"]:
        df["__balance__"] = df[m["due"]] - df[m["paid"]]
        m["balance"] = "__balance__"

    # ── Check minimum mapping ─────────────────────────────────────────────
    if not m["due"] or m["due"] not in df.columns:
        st.warning("⚠️ Please map the **Amount Due** column in the sidebar to proceed.")
        st.dataframe(df_raw.head(10), use_container_width=True)
        return

    # ── KPIs ──────────────────────────────────────────────────────────────
    total_due    = df[m["due"]].sum()   if m["due"]    else 0
    total_paid   = df[m["paid"]].sum()  if m["paid"] and m["paid"] in df.columns else 0
    total_bal    = df[m["balance"]].sum() if m["balance"] and m["balance"] in df.columns else total_due - total_paid
    collect_rate = round(total_paid / total_due * 100, 1) if total_due > 0 else 0

    overdue_n = 0
    if m["status"] and m["status"] in df.columns:
        overdue_n = int(df[m["status"]].astype(str).str.strip().isin(["Overdue","Due"]).sum())

    st.markdown('<div class="section-header">📊 Financial Summary</div>', unsafe_allow_html=True)
    c1,c2,c3,c4,c5 = st.columns(5)
    c1.markdown(kpi_card("📋", len(df), "Total Records", variant="sky"),             unsafe_allow_html=True)
    c2.markdown(kpi_card("💳", f"₹{total_due/1e5:.1f}L", "Total Due", variant=""),  unsafe_allow_html=True)
    c3.markdown(kpi_card("✅", f"₹{total_paid/1e5:.1f}L", "Collected", variant="green"), unsafe_allow_html=True)
    c4.markdown(kpi_card("📉", f"₹{total_bal/1e5:.1f}L", "Outstanding", variant="red"),  unsafe_allow_html=True)
    c5.markdown(kpi_card("📈", f"{collect_rate}%", "Collection Rate", variant="gold"),    unsafe_allow_html=True)

    if overdue_n > 0:
        render_html(f"""
        <div style='background:rgba(239,68,68,0.08);border:1px solid rgba(239,68,68,0.25);
            border-radius:10px;padding:10px 14px;font-size:0.82rem;color:#fca5a5;margin:0.8rem 0;'>
            ❌ <b>{overdue_n} overdue record{'s' if overdue_n!=1 else ''}</b> need immediate attention.
        </div>
        """)

    # ── Tabs ──────────────────────────────────────────────────────────────
    tabs = st.tabs(["💳 All Payments", "⚠️ Outstanding Dues", "📊 Analytics", "🗃️ Raw Data"])

    # ── All Payments tab ──────────────────────────────────────────────────
    with tabs[0]:
        st.markdown('<div class="section-header">💳 Payment Records</div>', unsafe_allow_html=True)

        # Filters
        filter_cols = st.columns(3)
        with filter_cols[0]:
            if m["status"] and m["status"] in df.columns:
                statuses = ["All"] + sorted(df[m["status"]].astype(str).unique().tolist())
                status_filter = st.selectbox("Status", statuses, key="fee_status_f")
            else:
                status_filter = "All"
        with filter_cols[1]:
            if m["class"] and m["class"] in df.columns:
                classes = ["All"] + sorted(df[m["class"]].dropna().unique().tolist())
                cls_filter = st.selectbox("Class", classes, key="fee_class_f")
            else:
                cls_filter = "All"
        with filter_cols[2]:
            if m["term"] and m["term"] in df.columns:
                terms = ["All"] + sorted(df[m["term"]].dropna().unique().tolist())
                term_filter = st.selectbox("Term", terms, key="fee_term_f")
            else:
                term_filter = "All"

        disp = df.copy()
        if status_filter != "All" and m["status"] and m["status"] in df.columns:
            disp = disp[disp[m["status"]].astype(str).str.strip() == status_filter]
        if cls_filter != "All" and m["class"] and m["class"] in df.columns:
            disp = disp[disp[m["class"]] == cls_filter]
        if term_filter != "All" and m["term"] and m["term"] in df.columns:
            disp = disp[disp[m["term"]].astype(str) == term_filter]

        # Build display columns
        show_cols = {}
        for role, label in [("name","Student"), ("id","ID"), ("class","Class"),
                             ("term","Term"), ("due","Due (₹)"), ("paid","Paid (₹)"),
                             ("balance","Balance (₹)"), ("status","Status")]:
            if m[role] and m[role] in df.columns:
                show_cols[m[role]] = label

        disp_view = disp[list(show_cols.keys())].rename(columns=show_cols)

        def bal_color(val):
            try:
                return "color:#f87171" if float(val) > 0 else "color:#34d399"
            except: return ""

        styled = disp_view.style
        if "Balance (₹)" in disp_view.columns:
            styled = styled.map(bal_color, subset=["Balance (₹)"])

        st.dataframe(styled, use_container_width=True, height=400)
        st.caption(f"Showing {len(disp_view):,} records")
        st.download_button("⬇️ Download filtered CSV",
                           disp_view.to_csv(index=False).encode(),
                           "fee_payments.csv", "text/csv")

    # ── Outstanding Dues tab ──────────────────────────────────────────────
    with tabs[1]:
        st.markdown('<div class="section-header">⚠️ Outstanding Dues</div>', unsafe_allow_html=True)

        if m["balance"] and m["balance"] in df.columns:
            dues = df[df[m["balance"]] > 0].copy().sort_values(m["balance"], ascending=False)
            show_cols3 = {}
            for role, label in [("name","Student"), ("id","ID"), ("class","Class"),
                                 ("term","Term"), ("due","Due (₹)"), ("paid","Paid (₹)"),
                                 ("balance","Balance (₹)"), ("status","Status")]:
                if m[role] and m[role] in df.columns:
                    show_cols3[m[role]] = label
            dues_view = dues[list(show_cols3.keys())].rename(columns=show_cols3)

            if dues_view.empty:
                st.success("🎉 No outstanding dues — all records are fully paid!")
            else:
                st.markdown(
                    f'<div style="color:#fca5a5;font-size:0.82rem;margin-bottom:0.6rem;">'
                    f'📉 Total outstanding: <b>₹{dues[m["balance"]].sum():,.0f}</b> across '
                    f'<b>{len(dues_view)}</b> records</div>',
                    unsafe_allow_html=True
                )
                st.dataframe(dues_view, use_container_width=True, height=400)
                st.download_button("⬇️ Download Dues List",
                                   dues_view.to_csv(index=False).encode(),
                                   "outstanding_dues.csv", "text/csv")
        elif m["status"] and m["status"] in df.columns:
            dues = df[df[m["status"]].astype(str).str.strip().isin(["Overdue","Due","Partial"])].copy()
            show_cols3 = {v: k for k, v in {m["name"]:"Student",m["id"]:"ID"}.items() if v != "None"}
            if not dues.empty:
                st.dataframe(dues, use_container_width=True, height=400)
            else:
                st.success("🎉 No overdue or partial records found!")
        else:
            st.info("Map the **Balance** or **Status** column to see outstanding dues.")

    # ── Analytics tab ─────────────────────────────────────────────────────
    with tabs[2]:
        st.markdown('<div class="section-header">📊 Fee Analytics</div>', unsafe_allow_html=True)

        col_a, col_b = st.columns(2)
        with col_a:
            if m["status"] and m["status"] in df.columns:
                fig_status = _chart_status_pie(df, m["status"])
                st.plotly_chart(fig_status, use_container_width=True, key="fee_status_pie")
            elif m["due"] and m["paid"] and m["paid"] in df.columns:
                fig_dv = _chart_due_vs_paid(df, m["due"], m["paid"])
                st.plotly_chart(fig_dv, use_container_width=True, key="fee_dv")

        with col_b:
            if m["class"] and m["class"] in df.columns and m["paid"] and m["paid"] in df.columns:
                fig_cls = _chart_collection_by_class(df, m["class"], m["paid"])
                st.plotly_chart(fig_cls, use_container_width=True, key="fee_cls_chart")

        if m["due"] and m["paid"] and m["paid"] in df.columns:
            if not (m["status"] and m["status"] in df.columns and m["class"] and m["class"] in df.columns):
                fig_dv2 = _chart_due_vs_paid(df, m["due"], m["paid"])
                st.plotly_chart(fig_dv2, use_container_width=True, key="fee_dv2")

        # Term-wise breakdown
        if m["term"] and m["term"] in df.columns and m["paid"] and m["paid"] in df.columns:
            st.markdown('<div class="section-header">📅 Term-wise Collection</div>',
                        unsafe_allow_html=True)
            term_grp = df.groupby(m["term"]).agg(
                Total_Due=(m["due"], "sum") if m["due"] else (m["paid"], "sum"),
                Total_Paid=(m["paid"], "sum"),
            ).reset_index()
            term_grp.columns = ["Term","Total Due","Total Paid"]
            fig_term = px.bar(term_grp, x="Term", y=["Total Due","Total Paid"],
                              barmode="group", title="📅 Due vs Paid by Term",
                              color_discrete_sequence=["#f97316","#10b981"])
            _chart_defaults(fig_term)
            st.plotly_chart(fig_term, use_container_width=True, key="fee_term_chart")

    # ── Raw Data tab ──────────────────────────────────────────────────────
    with tabs[3]:
        st.markdown('<div class="section-header">🗃️ Raw Data</div>', unsafe_allow_html=True)
        st.dataframe(df_raw, use_container_width=True)
        st.download_button("⬇️ Download Raw CSV",
                           df_raw.to_csv(index=False).encode(),
                           "fee_raw.csv", "text/csv")
