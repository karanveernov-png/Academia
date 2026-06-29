"""
tabs.cross_exam_tab
====================
Renders the "Compare Exams" tab: builds the merged multi-exam table,
shows headline comparison KPIs, the AI command bar for cross-exam
questions (rank-gap, most-improved, student lookup), and the full
merged table with a CSV download.
"""
import streamlit as st

from core.ui_components import render_html, kpi_card
from core.cross_exam import (
    build_merged_dataset, parse_cross_exam_command_with_ai, execute_cross_exam_command,
    _cross_exam_local_shortcut,
)


def render_cross_exam_tab(exam_results: dict, xai_key: str):
    st.markdown(
        f'<div class="section-header">🔀 Cross-Exam Comparison</div>',
        unsafe_allow_html=True
    )
    labels = list(exam_results.keys())
    st.caption(f"Comparing: **{' vs '.join(labels)}** — matched by Student ID / Name across exams.")

    merged, exam_subjects = build_merged_dataset(exam_results)
    if merged is None or merged.empty:
        st.warning("Couldn't match students across these exams — check that Student Name/ID columns are mapped consistently.")
        return

    # Quick at-a-glance: students detained in EVERY exam
    detain_cols = [f"{l}__Detained" for l in labels if f"{l}__Detained" in merged.columns]
    both_detained = merged[merged[detain_cols].fillna(False).all(axis=1)] if detain_cols else merged.iloc[0:0]

    k1, k2, k3 = st.columns(3)
    k1.markdown(kpi_card("👥", len(merged),         "Students Matched",          variant="sky"),   unsafe_allow_html=True)
    k2.markdown(kpi_card("🚫", len(both_detained),  f"Detained in All {len(labels)} Exams", variant="red"),   unsafe_allow_html=True)
    pct_cols = [f"{l}__Percentage" for l in labels if f"{l}__Percentage" in merged.columns]
    if pct_cols:
        most_improved_val = (merged[pct_cols[-1]] - merged[pct_cols[0]]).max()
        k3.markdown(kpi_card("📈", f"{most_improved_val:+.1f}%", "Biggest Improvement", variant="green"), unsafe_allow_html=True)

    if not both_detained.empty:
        with st.expander(f"🚫 {len(both_detained)} student(s) detained in ALL exams", expanded=False):
            show_cols = ["Student_Name"] + [c for c in merged.columns if c.endswith("__Percentage")]
            st.dataframe(both_detained[show_cols], use_container_width=True)

    # ── AI Command Bar — now spans multiple exams ──────────────────────────
    st.markdown('<div class="section-header">💬 Ask Across Exams — AI Command Bar</div>', unsafe_allow_html=True)
    render_html("""
    <div class="cmd-bar-wrap">
        <div class="cmd-hint">
            <span class="cmd-chip">🏅 Simran's rank</span>
            <span class="cmd-chip">🎯 tips for Ravi</span>
            <span class="cmd-chip">📋 profile of Anjali</span>
            <span class="cmd-chip">🏆 topper</span>
            <span class="cmd-chip">📊 top 10 leaderboard</span>
            <span class="cmd-chip">🚫 who is detained in both MST-1 and MST-2</span>
            <span class="cmd-chip">📈 how many improved from MST-1 to MST-2</span>
            <span class="cmd-chip">🚀 what should rank 10 do to reach rank 2</span>
            <span class="cmd-chip">🔍 how to improve Rahul</span>
            <span class="cmd-chip">👑 who is rank 3</span>
        </div>
    </div>
    """)
    c1, c2 = st.columns([5, 1])
    with c1:
        nl_query = st.text_input(
            "Cross-exam command",
            key="cross_nlcmd",
            label_visibility="collapsed",
            placeholder="🔍  Ask a question spanning multiple exams…"
        )
    with c2:
        run_cmd = st.button("▶ Run", key="cross_runcmd", use_container_width=True)

    if run_cmd and nl_query.strip():
        # ── Try local shortcut FIRST (zero API calls) ─────────────────────
        local_result = _cross_exam_local_shortcut(nl_query, merged, exam_subjects, exam_results)
        if local_result:
            kind, payload = local_result
            if kind == "chart":
                st.plotly_chart(payload, use_container_width=True)
            elif kind == "table":
                st.dataframe(payload, use_container_width=True, height=320)
            elif kind == "text":
                st.markdown(payload, unsafe_allow_html=False)
            else:
                st.error(payload)
        elif not xai_key:
            st.warning("⚠️ Enter your Groq API key in the sidebar to use the AI command bar.")
        else:
            with st.spinner("Interpreting cross-exam command…"):
                parsed = parse_cross_exam_command_with_ai(nl_query, exam_subjects, xai_key)
                kind, payload = execute_cross_exam_command(parsed, merged, exam_subjects)
            if kind == "chart":
                st.plotly_chart(payload, use_container_width=True)
            elif kind == "table":
                st.dataframe(payload, use_container_width=True, height=320)
            elif kind == "text":
                st.markdown(f'<div class="ai-box">{payload}</div>', unsafe_allow_html=True)
            else:
                st.error(payload)

    with st.expander("🗃️ Full merged comparison table", expanded=False):
        st.dataframe(merged, use_container_width=True)
        st.download_button("⬇️ Download merged CSV", merged.to_csv(index=False).encode(),
                           file_name="cross_exam_comparison.csv", mime="text/csv")