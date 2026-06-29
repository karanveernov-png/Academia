"""
tabs.exam_tab
=============
Renders the full single-exam analysis: column mapping, KPIs, AI
command bar, charts, AI insights, at-risk/detained tables, raw data,
and PDF export. Used once per uploaded file (each gets its own tab).
"""
import streamlit as st
import pandas as pd

from core.ui_components import render_html, kpi_card, column_mapper_ui
from core.data_loader import prepare_data, compute_kpis
from core.charts import (
    chart_grade_pie, chart_top_n_students, chart_scatter_percentile,
    chart_class_box, chart_gender_avg, chart_pass_fail_funnel,
)
from core.ai_insights import get_xai_insights
from core.ai_commands_single import (
    _single_exam_local_shortcut, parse_command_with_ai, execute_command,
)
from core.pdf_export import generate_pdf


def render_exam_tab(df_raw: pd.DataFrame, label: str, xai_key: str, top_n: int, show_raw: bool):
    """Render full analysis for one exam dataset."""

    # ── Column Mapping ───────────────────────────────────────────────────
    mapping = column_mapper_ui(df_raw, key_prefix=label.replace(" ","_"))

    if not mapping["marks"]:
        st.warning("⚠️ Please select at least one **Marks / Score column** in the sidebar to proceed.")
        st.dataframe(df_raw.head(10), use_container_width=True)
        return None, None, None, None

    # ── Analysis Scope: whole-subjects (combined) vs a single subject ─────
    scope_col1, scope_col2 = st.columns([2, 1])
    with scope_col1:
        scope_choice = st.selectbox(
            "📊 Analyze",
            ["All Subjects (Combined)"] + mapping["marks"],
            key=f"scope_{label}",
            help="Switch between the combined total/percentage across every subject, or drill into one subject at a time."
        )
    with scope_col2:
        detain_threshold = st.slider(
            "🚫 Detain threshold (%)", 0, 60, 33, key=f"detain_{label}",
            help="Students scoring below this percentage in the selected scope are flagged as Detained."
        )
    active_marks = None if scope_choice == "All Subjects (Combined)" else [scope_choice]
    subject_label = "All Subjects (Combined)" if active_marks is None else scope_choice

    # ── Prepare ──────────────────────────────────────────────────────────
    df = prepare_data(df_raw, mapping, active_marks=active_marks, detain_threshold=detain_threshold)
    kpis = compute_kpis(df, mapping["marks"])

    # ══════════ KPI CARDS ══════════
    st.markdown(
        f'<div class="section-header">📊 Key Performance Indicators'
        f'<span class="section-header-count">{subject_label}</span></div>',
        unsafe_allow_html=True
    )
    c1,c2,c3,c4,c5,c6,c7 = st.columns(7)
    c1.markdown(kpi_card("👥", kpis["total"],           "Total Students",  variant="sky"),   unsafe_allow_html=True)
    c2.markdown(kpi_card("📈", f"{kpis['avg_pct']}%",   "Avg Score",       variant=""),      unsafe_allow_html=True)
    c3.markdown(kpi_card("✅", f"{kpis['pass_rate']}%", "Pass Rate",       variant="green"), unsafe_allow_html=True)
    c4.markdown(kpi_card("🏆", kpis["top_name"],        "Top Scorer",
                          str(kpis["top_marks"])+" marks",                  variant="gold"),  unsafe_allow_html=True)
    c5.markdown(kpi_card("⚠️", kpis["at_risk_n"],       "At‑Risk",          variant="amber"), unsafe_allow_html=True)
    c6.markdown(kpi_card("🚫", kpis["detained_n"],      "Detained",        variant="red"),   unsafe_allow_html=True)
    c7.markdown(kpi_card("📉", kpis["bot_name"],        "Lowest Scorer",
                          str(kpis["bot_marks"])+" marks",                  variant="pink"),  unsafe_allow_html=True)

    # ══════════ AI COMMAND BAR ══════════
    st.markdown('<div class="section-header">💬 AI Command Bar</div>', unsafe_allow_html=True)
    render_html("""
    <div class="cmd-bar-wrap">
        <div class="cmd-hint">
            <span class="cmd-chip">🏅 Ravi's rank</span>
            <span class="cmd-chip">🎯 tips for Sita</span>
            <span class="cmd-chip">📋 profile of Anjali</span>
            <span class="cmd-chip">🏆 topper</span>
            <span class="cmd-chip">📊 make english graph of first 40 students</span>
            <span class="cmd-chip">🚫 how many detentions in maths</span>
            <span class="cmd-chip">👧 list girls above 80% in maths</span>
            <span class="cmd-chip">🔍 what did Ravi score</span>
        </div>
    </div>
    """)
    cmd_col1, cmd_col2 = st.columns([5, 1])
    with cmd_col1:
        nl_query = st.text_input(
            "Command",
            key=f"nlcmd_{label}",
            label_visibility="collapsed",
            placeholder="🔍  Type a natural-language command…"
        )
    with cmd_col2:
        run_cmd = st.button("▶ Run", key=f"runcmd_{label}", use_container_width=True)

    if run_cmd and nl_query.strip():
        # ── Try local shortcut FIRST (zero API calls) ─────────────────────
        local_result = _single_exam_local_shortcut(nl_query, df_raw, mapping, detain_threshold)
        if local_result:
            kind, payload = local_result
            if kind == "chart":
                st.plotly_chart(payload, use_container_width=True, key=f"cmd_local_chart_{label}")
            elif kind == "table":
                st.dataframe(payload, use_container_width=True, height=320)
            elif kind == "text":
                st.markdown(payload, unsafe_allow_html=False)
            else:
                st.error(payload)
        elif not xai_key:
            st.warning("⚠️ Enter your Groq API key in the sidebar to use the AI command bar.")
        else:
            with st.spinner("Interpreting command…"):
                parsed = parse_command_with_ai(nl_query, mapping["marks"], xai_key)
                kind, payload = execute_command(parsed, df_raw, mapping, detain_threshold)
            if kind == "chart":
                st.plotly_chart(payload, use_container_width=True, key=f"cmd_ai_chart_{label}")
            elif kind == "table":
                st.dataframe(payload, use_container_width=True, height=320)
            elif kind == "text":
                st.markdown(f'<div class="ai-box">{payload}</div>', unsafe_allow_html=True)
            else:
                st.error(payload)

    # ══════════ CHARTS ══════════
    st.markdown('<div class="section-header">📉 Interactive Charts</div>', unsafe_allow_html=True)


    st.plotly_chart(chart_grade_pie(df), use_container_width=True, key=f"grade_pie_{label}")

    col_e, col_f = st.columns(2)
    with col_e:
        st.plotly_chart(chart_top_n_students(df, top_n), use_container_width=True, key=f"top_n_{label}")
    with col_f:
        st.plotly_chart(chart_scatter_percentile(df), use_container_width=True, key=f"scatter_{label}")

    # Optional charts
    cls_chart = chart_class_box(df)
    gen_chart = chart_gender_avg(df)
    if cls_chart or gen_chart:
        col_g, col_h = st.columns(2)
        if cls_chart:
            col_g.plotly_chart(cls_chart, use_container_width=True, key=f"cls_box_{label}")
        if gen_chart:
            col_h.plotly_chart(gen_chart, use_container_width=True, key=f"gender_avg_{label}")

    funnel_chart = chart_pass_fail_funnel(df, detain_threshold)
    if funnel_chart:
        st.plotly_chart(funnel_chart, use_container_width=True, key=f"funnel_{label}")

    # ══════════ AI INSIGHTS ══════════
    st.markdown('<div class="section-header">🤖 AI‑Powered Insights</div>', unsafe_allow_html=True)
    insight_key = f"ai_insights_{label}"
    ins_col1, ins_col2 = st.columns([3, 1])
    with ins_col1:
        st.caption("Generates a teacher-friendly AI summary of this exam's performance. Click to call the AI (only counts as 1 API call, and is cached until you regenerate it).")
    with ins_col2:
        gen_insight_btn = st.button("✨ Generate AI Insight", key=f"gen_insight_{label}", use_container_width=True)

    if gen_insight_btn:
        if not xai_key:
            st.warning("⚠️ Enter your Groq API key in the sidebar to enable AI insights.")
        else:
            with st.spinner("✨ Generating AI insights…"):
                st.session_state[insight_key] = get_xai_insights(kpis, xai_key, label)

    insights = st.session_state.get(insight_key, "")
    if insights:
        st.markdown(f'<div class="ai-box">{insights}</div>', unsafe_allow_html=True)
    else:
        st.info("Click **✨ Generate AI Insight** above to get an AI-powered summary — the API is only called when you ask for it.")

    # ══════════ AT-RISK & DETAINED TABLES ══════════
    risk_tab_col, detain_tab_col = st.columns(2)

    with risk_tab_col:
        st.markdown('<div class="section-header">🚨 At‑Risk Students</div>', unsafe_allow_html=True)
        risk_df = df[df["Risk"] != "Low"][["Student_Name","Student_ID","Total_Marks","Percentage","Grade","Risk"]].sort_values("Percentage")

        if risk_df.empty:
            st.success("🎉 No at-risk students! All students are passing.")
        else:
            # Colour-code Risk column
            def colour_risk(val):
                c = {"High":"#ff6b6b33","Medium":"#ffb34733","Low":"#52e56b33"}.get(val,"")
                return f"background-color:{c}"
            st.dataframe(
                risk_df.style.map(colour_risk, subset=["Risk"]),
                use_container_width=True, height=300
            )

    with detain_tab_col:
        st.markdown(f'<div class="section-header">🚫 Detained — {subject_label}</div>', unsafe_allow_html=True)
        detain_df = df[df["Detained"]][["Student_Name","Student_ID","Total_Marks","Percentage","Grade"]].sort_values("Percentage")
        if detain_df.empty:
            st.success(f"🎉 No detained students in {subject_label} (threshold: {detain_threshold:.0f}%).")
        else:
            st.dataframe(detain_df, use_container_width=True, height=300)
            st.caption(f"**{len(detain_df)}** student(s) below {detain_threshold:.0f}% in {subject_label}.")

    # ══════════ RAW DATA ══════════
    if show_raw:
        with st.expander("🗃️ Full Dataset", expanded=False):
            st.dataframe(df, use_container_width=True)
            csv_bytes = df.to_csv(index=False).encode()
            st.download_button("⬇️ Download as CSV", csv_bytes,
                               file_name=f"{label}_processed.csv", mime="text/csv")

    # ══════════ PDF DOWNLOAD ══════════
    st.markdown('<div class="section-header">📄 Export Report</div>', unsafe_allow_html=True)
    pdf_col1, pdf_col2 = st.columns([1, 3])
    with pdf_col1:
        generate_pdf_btn = st.button(f"📥 Generate PDF — {label}", key=f"pdf_{label}", use_container_width=True)
    if generate_pdf_btn:
        with st.spinner("🔄 Building PDF report…"):
            pdf_bytes = generate_pdf(df, kpis, insights, label, mapping)
        with pdf_col2:
            st.download_button(
                label="⬇️  Download PDF Report",
                data=pdf_bytes,
                file_name=f"{label.replace(' ','_')}_Report.pdf",
                mime="application/pdf",
                key=f"dl_pdf_{label}",
                use_container_width=True
            )
        st.success("✅ PDF is ready — click the Download button above!")

    return df, kpis, mapping, detain_threshold