"""
app.py — Student Intelligence Portal  (v4.0 — Section-First Navigation)
=========================================================================
Flow:
  1. Login  →  Home Dashboard  (3 cards: Attendance · Fee · Current MST)
  2. Tap a card  →  Section page with its own sidebar + back button
     • MST        → upload MST Excel, map Name/Roll/Columns, full analysis
     • Attendance → upload Attendance sheet, view tracker
     • Fee        → upload Fee sheet, view fee controller

No file upload appears until you're inside a section.
"""
import warnings
warnings.filterwarnings("ignore")

import streamlit as st

from core.config import configure_page
from core.styling import inject_css
from core.ui_components import render_html
from core.auth import init_auth_state, is_logged_in, inject_login_css, render_login_page
from core.secrets_helper import resolve_api_key, has_default_key

# ── Auth state must exist before anything else ─────────────────────────
init_auth_state()

# ── Page config ────────────────────────────────────────────────────────
if is_logged_in():
    configure_page(layout="wide", sidebar_state="collapsed")
else:
    configure_page(page_title="Studora Login Portal", layout="centered", sidebar_state="collapsed")

# ── Gate: show login until authenticated ───────────────────────────────
if not is_logged_in():
    inject_login_css()
    render_login_page()
    st.stop()

inject_css()

# ── Extra CSS for home cards, section sidebar, back button ─────────────
st.markdown("""
<style>
/* ── Home card grid ── */
.home-header {
    padding: 2.6rem 0 0.4rem;
    text-align: left;
}
.home-header h2 {
    font-size: 2rem; font-weight: 800;
    color: #f1f5f9 !important; margin: 0 0 0.2rem;
}
.home-header p {
    color: #78716c !important; font-size: 0.88rem; margin: 0;
}

/* top-bar strip */
.topbar {
    display: flex; justify-content: space-between; align-items: center;
    padding: 0.7rem 2rem;
    background: rgba(11,17,33,0.95);
    border-bottom: 1px solid rgba(249,115,22,0.12);
    position: sticky; top: 0; z-index: 100;
}
.topbar-logo {
    font-size: 0.95rem; font-weight: 700; color: #fdba74;
    display: flex; align-items: center; gap: 0.5rem;
}
.topbar-user { font-size: 0.78rem; color: #78716c; }

/* Section sidebar */
.section-sidebar-title {
    font-size: 1rem; font-weight: 700; color: #fdba74;
    padding: 1rem 0 0.3rem; text-align: center;
}
.section-sidebar-sub {
    font-size: 0.68rem; color: #78716c; text-align: center;
    margin-bottom: 1rem; letter-spacing: 0.04em;
}

/* Back button override */
div[data-testid="stSidebar"] .back-btn > button {
    background: rgba(249,115,22,0.12) !important;
    border: 1px solid rgba(249,115,22,0.35) !important;
    color: #fdba74 !important;
    font-size: 0.8rem !important;
    margin-bottom: 0.5rem;
    box-shadow: none !important;
}
div[data-testid="stSidebar"] .back-btn > button:hover {
    background: rgba(249,115,22,0.22) !important;
    transform: none !important;
}

/* Section page header */
.section-page-header {
    display: flex; align-items: center; gap: 1rem;
    padding: 1.4rem 0 1rem;
    border-bottom: 1px solid rgba(249,115,22,0.12);
    margin-bottom: 1.4rem;
}
.section-page-header .sec-icon { font-size: 2.2rem; }
.section-page-header h1 {
    font-size: 1.6rem; font-weight: 800; color: #f1f5f9 !important; margin: 0;
}
.section-page-header p { color: #78716c !important; font-size: 0.82rem; margin: 0.2rem 0 0; }

/* Upload prompt box */
.upload-prompt {
    text-align: center; padding: 3rem 2rem;
    background: rgba(249,115,22,0.03);
    border: 1px dashed rgba(249,115,22,0.2);
    border-radius: 18px; margin-top: 1rem;
}
.upload-prompt .up-icon { font-size: 3.5rem; margin-bottom: 0.8rem; }
.upload-prompt h3 { color: #fdba74 !important; font-size: 1.1rem; margin-bottom: 0.4rem; }
.upload-prompt p { color: #78716c !important; font-size: 0.82rem; max-width: 420px; margin: 0 auto; }
</style>
""", unsafe_allow_html=True)

# ── Session defaults ────────────────────────────────────────────────────
if "active_section" not in st.session_state:
    st.session_state.active_section = None   # None = home


# ══════════════════════════════════════════════════════════════════════
# HOME DASHBOARD
# ══════════════════════════════════════════════════════════════════════
def render_home():
    role = (st.session_state.get("username") or "User").title()

    # Top bar
    col_logo, col_user = st.columns([8, 2])
    with col_logo:
        st.markdown(
            '<div style="display:flex;align-items:center;gap:0.6rem;padding:0.4rem 0 1.2rem;">'
            '<span style="font-size:1.5rem;">🎓</span>'
            '<span style="font-size:1rem;font-weight:700;'
            'background:linear-gradient(135deg,#fdba74,#f97316);'
            '-webkit-background-clip:text;-webkit-text-fill-color:transparent;'
            'background-clip:text;">Student Portal</span></div>',
            unsafe_allow_html=True
        )
    with col_user:
        st.markdown(
            f'<div style="text-align:right;padding:0.4rem 0 1.2rem;">'
            f'<span style="color:#78716c;font-size:0.8rem;">{role}</span>&nbsp;&nbsp;',
            unsafe_allow_html=True
        )
        if st.button("↩ Sign out", key="home_signout"):
            from core.auth import logout
            logout()
            st.session_state.active_section = None
            st.rerun()

    # Greeting
    st.markdown(
        f'<h2 style="font-size:1.7rem;font-weight:800;color:#f1f5f9!important;margin:0.5rem 0 0.2rem;">'
        f'Good day, {role}</h2>'
        f'<p style="color:#78716c;font-size:0.88rem;margin:0 0 2rem;">Choose a section to get started</p>',
        unsafe_allow_html=True
    )

    # Cards
    c1, c2, c3, _gap = st.columns([1, 1, 1, 2])

    def card_button(col, icon, title, subtitle, key, icon_color):
        with col:
            st.markdown(f"""
            <div style="background:#fff;border-radius:14px;
                border:1px solid #e5e7eb;padding:2rem 1.5rem 1.5rem;
                text-align:center;box-shadow:0 2px 8px rgba(0,0,0,0.06);
                transition:box-shadow 0.2s;cursor:pointer;" >
                <div style="font-size:2.2rem;color:{icon_color};margin-bottom:0.6rem;">{icon}</div>
                <div style="font-weight:700;color:#111827;font-size:0.95rem;margin-bottom:0.2rem;">{title}</div>
                <div style="color:#6b7280;font-size:0.78rem;">{subtitle}</div>
            </div>
            """, unsafe_allow_html=True)
            # invisible full-width button over the card area
            if st.button(f"Open {title}", key=key, use_container_width=True,
                         help=f"Open {title}"):
                st.session_state.active_section = key
                st.rerun()

    card_button(c1, "📅", "Attendance", "Track daily presence",     "attendance", "#4ade80")
    card_button(c2, "💳", "Fee",        "Payments and dues",         "fee",        "#f97316")
    card_button(c3, "📊", "Current MST","Exam results and analysis", "mst",        "#38bdf8")


# ══════════════════════════════════════════════════════════════════════
# MST SECTION  — multi-file + Compare Mode
# ══════════════════════════════════════════════════════════════════════
def render_mst_section():
    with st.sidebar:
        _section_sidebar_header("📊", "Current MST", "Exam results & analysis")

        st.markdown("### 📂 Upload MST Sheets")
        render_html("""
        <div class="upload-hint">
            Upload one or more MST Excel / CSV files.<br>
            Upload <b>2+ files</b> to unlock <b>🔀 Compare Mode</b> with cross-exam AI analysis.
        </div>
        """)
        mst_files = st.file_uploader(
            "MST files", type=["csv", "xlsx", "xls"],
            accept_multiple_files=True, key="mst_file_upload",
            label_visibility="collapsed"
        )

        # Per-file delete buttons
        if "mst_excluded" not in st.session_state:
            st.session_state.mst_excluded = set()
        if mst_files:
            current_names = {f.name for f in mst_files}
            st.session_state.mst_excluded &= current_names
            active_files = [f for f in mst_files if f.name not in st.session_state.mst_excluded]
            for i, f in enumerate(active_files):
                c1, c2 = st.columns([5, 1])
                with c1:
                    st.markdown(
                        f'<div style="font-size:0.7rem;color:#10b981;padding:2px 0;'
                        f'overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">📄 {f.name}</div>',
                        unsafe_allow_html=True)
                with c2:
                    if st.button("🗑️", key=f"del_mst_{i}_{f.name}", help=f"Remove {f.name}"):
                        st.session_state.mst_excluded.add(f.name)
                        st.rerun()
        else:
            active_files = []

        st.divider()

        xai_key = ""
        top_n = 10
        show_raw = True

        if active_files:
            st.markdown("### 🔑 Groq API Key")
            _typed_key = st.text_input(
                "API Key", type="password",
                placeholder="gsk_… (optional)" if has_default_key() else "gsk_…",
                help="Free at console.groq.com/keys — unlocks AI insights & compare AI command bar. "
                     "Leave blank to use this app's shared key, if one is configured.",
                label_visibility="collapsed", key="mst_xai_key"
            )
            xai_key = resolve_api_key(_typed_key)
            if _typed_key:
                st.markdown('<div style="font-size:0.7rem;color:#10b981;">✓ Using your own key</div>',
                            unsafe_allow_html=True)
            elif xai_key:
                st.markdown('<div style="font-size:0.7rem;color:#10b981;">✓ Using app\'s shared key</div>',
                            unsafe_allow_html=True)
            else:
                st.markdown('<div style="font-size:0.7rem;color:#78716c;">Enter key for AI features</div>',
                            unsafe_allow_html=True)
            st.divider()
            st.markdown("### ⚙️ Display")
            top_n    = st.slider("Top-N students in chart", 5, 30, 10, key="mst_topn")
            show_raw = st.checkbox("Show raw data tables", value=True, key="mst_showraw")
            st.divider()

        _version_footer()

    # ── Main area ──────────────────────────────────────────────────────
    _section_page_header("📊", "Current MST", "Upload MST sheets · Map columns · Compare exams · Get AI insights")

    if not active_files:
        render_html("""
        <div class="upload-prompt">
            <div class="up-icon">📊</div>
            <h3>Upload MST Excel Sheet(s)</h3>
            <p>Use the sidebar to upload one or more MST (Mid Semester Test) Excel or CSV files.
               Once uploaded, map Student Name, Roll No, and Subject columns to unlock
               full charts, AI insights, PDF export, and cross-exam Compare Mode.</p>
        </div>
        """)
        return

    # ── Load all files ────────────────────────────────────────────────
    from core.data_loader import load_file
    from tabs.exam_tab import render_exam_tab

    # Build tab list
    tab_labels = [f"📊 {f.name.rsplit('.',1)[0]}" for f in active_files]
    if len(active_files) >= 2:
        tab_labels.append("🔀 Compare Exams")

    tabs = st.tabs(tab_labels)
    exam_results = {}

    for i, (tab, upload) in enumerate(zip(tabs[:len(active_files)], active_files)):
        label = upload.name.rsplit(".", 1)[0]
        with tab:
            df_raw, err = load_file(upload)
            if err:
                st.error(f"❌ Could not load '{label}': {err}")
                continue
            if df_raw is None or df_raw.empty:
                st.warning(f"'{label}' appears empty — please re-upload.")
                continue
            st.markdown(
                f'<div class="file-info-bar">📄 <b>{label}</b> — '
                f'{len(df_raw):,} rows × {len(df_raw.columns)} columns</div>',
                unsafe_allow_html=True
            )
            result = render_exam_tab(df_raw, label, xai_key, top_n, show_raw)
            if result and result[0] is not None:
                exam_results[label] = {
                    "df": result[0], "mapping": result[2],
                    "kpis": result[1], "detain_threshold": result[3]
                }

    # ── Compare tab ───────────────────────────────────────────────────
    if len(active_files) >= 2:
        with tabs[len(active_files)]:
            if len(exam_results) >= 2:
                _render_compare_tab(exam_results, xai_key)
            else:
                st.info(
                    "⏳ Map columns for at least **2 exams** in their tabs above "
                    "to unlock Compare Mode."
                )


def _render_compare_tab(exam_results: dict, xai_key: str):
    """Full Compare Mode — KPIs, charts, and a powerful AI command bar."""
    from core.cross_exam import (
        build_merged_dataset, _cross_exam_local_shortcut,
        parse_cross_exam_command_with_ai, execute_cross_exam_command,
    )
    from core.ui_components import kpi_card, render_html

    labels = list(exam_results.keys())

    st.markdown(
        '<div class="section-header">🔀 Cross-Exam Compare Mode</div>',
        unsafe_allow_html=True
    )
    st.caption(f"Comparing: **{' · '.join(labels)}** — students matched by Name / Roll No across exams.")

    merged, exam_subjects = build_merged_dataset(exam_results)
    if merged is None or merged.empty:
        st.warning("Couldn't match students across exams — make sure Student Name/ID columns are mapped in each tab.")
        return

    pct_cols = [f"{l}__Percentage" for l in labels if f"{l}__Percentage" in merged.columns]
    det_cols = [f"{l}__Detained"   for l in labels if f"{l}__Detained"   in merged.columns]

    # ── KPI row ───────────────────────────────────────────────────────
    both_detained = (
        merged[merged[det_cols].fillna(False).all(axis=1)]
        if det_cols else merged.iloc[0:0]
    )
    improved_count = 0
    if len(pct_cols) >= 2:
        improved_count = int(
            ((merged[pct_cols[-1]] - merged[pct_cols[0]]) > 0).sum()
        )
    most_improved_val = 0.0
    if len(pct_cols) >= 2:
        most_improved_val = float((merged[pct_cols[-1]] - merged[pct_cols[0]]).max())

    k1, k2, k3, k4 = st.columns(4)
    k1.markdown(kpi_card("👥", len(merged), "Students Matched", variant="sky"), unsafe_allow_html=True)
    k2.markdown(kpi_card("🚫", len(both_detained), "Detained in ALL Exams", variant="red"), unsafe_allow_html=True)
    k3.markdown(kpi_card("📈", improved_count, "Students Improved", variant="green"), unsafe_allow_html=True)
    k4.markdown(kpi_card("🚀", f"{most_improved_val:+.1f}%", "Biggest Improvement", variant="gold"), unsafe_allow_html=True)

    # ── Quick charts ──────────────────────────────────────────────────
    import plotly.graph_objects as go
    from core.config import ACCENT_SEQ, CHART_BG, CHART_FONT, GRID_COLOR, TITLE_FONT

    if pct_cols:
        # Avg per exam bar
        avgs = {l: round(merged[f"{l}__Percentage"].mean(), 2)
                for l in labels if f"{l}__Percentage" in merged.columns}
        fig_avg = go.Figure(go.Bar(
            x=list(avgs.keys()), y=list(avgs.values()),
            marker_color=ACCENT_SEQ[:len(avgs)],
            text=[f"{v:.1f}%" for v in avgs.values()], textposition="outside"
        ))
        fig_avg.update_layout(
            title="📊 Class Average % — Per Exam",
            paper_bgcolor=CHART_BG, plot_bgcolor=CHART_BG,
            font_color=CHART_FONT, title_font_color=TITLE_FONT,
            yaxis=dict(range=[0, 110], gridcolor=GRID_COLOR),
            xaxis=dict(gridcolor=GRID_COLOR), height=320,
        )

        # Rank comparison grouped bar (top 15)
        df_top = merged.copy()
        df_top["Avg_%"] = df_top[pct_cols].mean(axis=1)
        df_top = df_top.nlargest(15, "Avg_%")
        fig_rank = go.Figure()
        for i, col in enumerate(pct_cols):
            lbl = col.replace("__Percentage", "")
            fig_rank.add_trace(go.Bar(
                name=lbl, x=df_top["Student_Name"], y=df_top[col],
                marker_color=ACCENT_SEQ[i % len(ACCENT_SEQ)]
            ))
        fig_rank.update_layout(
            barmode="group", title="🏅 Rank Comparison — Top 15",
            paper_bgcolor=CHART_BG, plot_bgcolor=CHART_BG,
            font_color=CHART_FONT, title_font_color=TITLE_FONT,
            yaxis=dict(gridcolor=GRID_COLOR), xaxis=dict(gridcolor=GRID_COLOR),
            legend=dict(bgcolor="rgba(0,0,0,0)", font_color=CHART_FONT), height=320,
        )

        ch1, ch2 = st.columns(2)
        with ch1:
            st.plotly_chart(fig_avg,  use_container_width=True, key="cmp_avg_bar")
        with ch2:
            st.plotly_chart(fig_rank, use_container_width=True, key="cmp_rank_bar")

    # Detained in all exams callout
    if not both_detained.empty:
        with st.expander(f"🚫 {len(both_detained)} student(s) detained in ALL exams", expanded=False):
            show_cols = ["Student_Name"] + pct_cols
            st.dataframe(both_detained[show_cols], use_container_width=True)

    # ── 💬 POWERFUL AI COMMAND BAR ────────────────────────────────────
    st.markdown('<div class="section-header">💬 Cross-Exam AI Command Bar</div>', unsafe_allow_html=True)

    render_html("""
    <div class="cmd-bar-wrap">
      <div class="cmd-hint">
        <span class="cmd-chip">🏆 top 10 leaderboard</span>
        <span class="cmd-chip">📈 who improved</span>
        <span class="cmd-chip">📉 who dropped the most</span>
        <span class="cmd-chip">🚫 detained in all exams</span>
        <span class="cmd-chip">📊 class average each exam</span>
        <span class="cmd-chip">🔀 rank comparison chart</span>
        <span class="cmd-chip">📉 progress trend chart</span>
        <span class="cmd-chip">👤 Ravi's progress</span>
        <span class="cmd-chip">🆚 compare Ravi and Sita</span>
        <span class="cmd-chip">🎯 students above 80% in MST2</span>
        <span class="cmd-chip">🔴 who is at risk in both exams</span>
        <span class="cmd-chip">🏅 rank of Anjali</span>
      </div>
    </div>
    """)

    cmd_c1, cmd_c2 = st.columns([6, 1])
    with cmd_c1:
        nl_query = st.text_input(
            "Cross-exam command",
            key="cross_nlcmd",
            label_visibility="collapsed",
            placeholder="🔍  Ask anything across multiple exams — top 10, who improved, Ravi's profile, compare Ravi and Sita…"
        )
    with cmd_c2:
        run_cmd = st.button("▶ Run", key="cross_runcmd", use_container_width=True)

    if run_cmd and nl_query.strip():
        # 1️⃣ Try zero-API local shortcuts first
        local_result = _cross_exam_local_shortcut(nl_query, merged, exam_subjects, exam_results)
        if local_result:
            kind, payload = local_result
        elif not xai_key:
            st.warning("⚠️ Enter your Groq API key in the sidebar to use AI-powered commands.")
            kind, payload = None, None
        else:
            # 2️⃣ Full AI parse + execute
            with st.spinner("🤖 Interpreting your command…"):
                parsed = parse_cross_exam_command_with_ai(nl_query, exam_subjects, xai_key)
                kind, payload = execute_cross_exam_command(parsed, merged, exam_subjects)

        if kind == "chart":
            st.plotly_chart(payload, use_container_width=True, key="cross_cmd_chart")
        elif kind == "table":
            st.dataframe(payload, use_container_width=True, height=360)
        elif kind == "text":
            st.markdown(f'<div class="ai-box">{payload}</div>', unsafe_allow_html=True)
        elif kind == "error":
            st.error(payload)

    # ── Full merged table download ─────────────────────────────────────
    with st.expander("🗃️ Full merged comparison table", expanded=False):
        st.dataframe(merged, use_container_width=True)
        st.download_button(
            "⬇️ Download merged CSV",
            merged.to_csv(index=False).encode(),
            file_name="cross_exam_comparison.csv",
            mime="text/csv"
        )


# ══════════════════════════════════════════════════════════════════════
# ATTENDANCE SECTION
# ══════════════════════════════════════════════════════════════════════
def render_attendance_section():
    with st.sidebar:
        _section_sidebar_header("📅", "Attendance", "Track daily presence")

        st.markdown("### 📂 Upload Attendance Sheet")
        render_html("""
        <div class="upload-hint">
            Upload your attendance Excel / CSV with student names and present/absent counts.
        </div>
        """)
        att_file = st.file_uploader(
            "Attendance file", type=["csv", "xlsx", "xls"],
            accept_multiple_files=False, key="att_file_upload",
            label_visibility="collapsed"
        )
        if att_file:
            st.markdown(f'<div style="font-size:0.7rem;color:#10b981;">📄 {att_file.name}</div>',
                        unsafe_allow_html=True)
        st.divider()
        _version_footer()

    _section_page_header("📅", "Attendance", "Upload your attendance sheet to track daily presence")

    if not att_file:
        render_html("""
        <div class="upload-prompt">
            <div class="up-icon">📅</div>
            <h3>Upload Attendance Sheet</h3>
            <p>Use the sidebar to upload your Attendance Excel or CSV file.
               The file should contain student names and present / absent / late counts.</p>
        </div>
        """)
        return

    from tabs.attendance_tab import render_attendance_tab
    render_attendance_tab(att_file)


# ══════════════════════════════════════════════════════════════════════
# FEE SECTION
# ══════════════════════════════════════════════════════════════════════
def render_fee_section():
    with st.sidebar:
        _section_sidebar_header("💳", "Fee Controller", "Payments and dues")

        st.markdown("### 📂 Upload Fee Sheet")
        render_html("""
        <div class="upload-hint">
            Upload your fee Excel / CSV with fee amounts, payment status and balances.
        </div>
        """)
        fee_file = st.file_uploader(
            "Fee file", type=["csv", "xlsx", "xls"],
            accept_multiple_files=False, key="fee_file_upload",
            label_visibility="collapsed"
        )
        if fee_file:
            st.markdown(f'<div style="font-size:0.7rem;color:#10b981;">📄 {fee_file.name}</div>',
                        unsafe_allow_html=True)
        st.divider()
        _version_footer()

    _section_page_header("💳", "Fee Controller", "Upload your fee sheet to manage payments and dues")

    if not fee_file:
        render_html("""
        <div class="upload-prompt">
            <div class="up-icon">💳</div>
            <h3>Upload Fee Sheet</h3>
            <p>Use the sidebar to upload your Fee Excel or CSV file.
               The file should contain fee amounts, payment status, and outstanding balances.</p>
        </div>
        """)
        return

    from tabs.fee_tab import render_fee_tab
    render_fee_tab(fee_file)


# ══════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════
def _section_sidebar_header(icon, title, sub):
    """Renders logo + back button at the top of every section sidebar."""
    render_html(f"""
    <div class="sidebar-logo">
        <span class="sidebar-logo-icon">{icon}</span>
        <div class="sidebar-logo-title">{title}</div>
        <div class="sidebar-logo-sub">{sub}</div>
    </div>
    """)
    st.markdown('<div class="back-btn">', unsafe_allow_html=True)
    if st.button("← Back to Home", key="back_home_btn", use_container_width=True):
        st.session_state.active_section = None
        # Clear uploaded files and exclude sets for this section
        for k in ["mst_file_upload", "att_file_upload", "fee_file_upload",
                  "mst_excluded"]:
            if k in st.session_state:
                del st.session_state[k]
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)
    st.divider()


def _section_page_header(icon, title, subtitle):
    st.markdown(f"""
    <div class="section-page-header">
        <span class="sec-icon">{icon}</span>
        <div>
            <h1>{title}</h1>
            <p>{subtitle}</p>
        </div>
    </div>
    """, unsafe_allow_html=True)


def _version_footer():
    st.markdown(
        '<div style="font-size:0.65rem;color:#44403c;text-align:center;">'
        'Studora Dashboard v4.0<br>'
        '<span style="color:#292524;">Streamlit · Groq · Plotly</span></div>',
        unsafe_allow_html=True
    )


# ══════════════════════════════════════════════════════════════════════
# ROUTER
# ══════════════════════════════════════════════════════════════════════
section = st.session_state.active_section

if section is None:
    # Collapse sidebar on home
    st.markdown("""
    <style>
    [data-testid="stSidebar"] { display: none !important; }
    [data-testid="collapsedControl"] { display: none !important; }
    </style>
    """, unsafe_allow_html=True)
    render_home()

elif section == "mst":
    configure_page(layout="wide", sidebar_state="expanded")
    render_mst_section()

elif section == "attendance":
    configure_page(layout="wide", sidebar_state="expanded")
    render_attendance_section()

elif section == "fee":
    configure_page(layout="wide", sidebar_state="expanded")
    render_fee_section()
