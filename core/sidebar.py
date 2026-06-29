"""
core.sidebar — unified sidebar for the integrated portal.
Returns exam uploads, fee upload, attendance upload + display settings.
"""
import streamlit as st
from core.ui_components import render_html
from core.auth import logout


def sidebar():
    with st.sidebar:
        render_html("""
        <div class="sidebar-logo">
            <span class="sidebar-logo-icon">🎓</span>
            <div class="sidebar-logo-title">Student Intelligence Portal</div>
            <div class="sidebar-logo-sub">Exam · Attendance · Fee</div>
            <div><span class="sidebar-badge">⚡ Groq AI Powered</span></div>
        </div>
        """)

        # ── Account / Logout ────────────────────────────────────────────
        role = (st.session_state.get("role") or "user").title()
        st.markdown(
            f'<div style="font-size:0.75rem;color:#fdba74;text-align:center;">'
            f'👤 Logged in as <b>{role}</b></div>',
            unsafe_allow_html=True
        )
        if st.button("🚪 Logout", use_container_width=True, key="logout_btn"):
            logout()
            st.rerun()
        st.divider()

        # ── API Key ──────────────────────────────────────────────────────
        st.markdown("### 🔑 Groq API Key")
        xai_key = st.text_input(
            "API Key", type="password", placeholder="gsk_…",
            help="Free key at console.groq.com/keys — unlocks AI insights & command bar.",
            label_visibility="collapsed"
        )
        if xai_key:
            st.markdown('<div style="font-size:0.7rem;color:#10b981;">✓ AI features unlocked</div>',
                        unsafe_allow_html=True)
        else:
            st.markdown('<div style="font-size:0.7rem;color:#78716c;">Enter key to unlock AI features</div>',
                        unsafe_allow_html=True)
        st.divider()

        # ── Exam Uploads ─────────────────────────────────────────────────
        st.markdown("### 📊 Exam Data")
        render_html("""
        <div class="upload-hint">
            Upload CSV/Excel with student names, IDs, and subject marks.
            Upload 2+ files to enable cross-exam comparison.
        </div>
        """)
        exam_uploads = st.file_uploader(
            "Exam files", type=["csv","xlsx","xls"],
            accept_multiple_files=True, key="exam_uploads",
            label_visibility="collapsed"
        )

        if "excluded_exams" not in st.session_state:
            st.session_state.excluded_exams = set()

        if exam_uploads:
            current = {u.name for u in exam_uploads}
            st.session_state.excluded_exams &= current
            exam_uploads = [u for u in exam_uploads
                            if u.name not in st.session_state.excluded_exams]
            for i, u in enumerate(exam_uploads):
                c1, c2 = st.columns([5, 1])
                with c1:
                    st.markdown(
                        f'<div style="font-size:0.7rem;color:#10b981;padding:4px 0;'
                        f'overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">📄 {u.name}</div>',
                        unsafe_allow_html=True)
                with c2:
                    if st.button("🗑️", key=f"del_exam_{i}_{u.name}", help=f"Remove {u.name}"):
                        st.session_state.excluded_exams.add(u.name)
                        st.rerun()
        st.divider()

        # ── Attendance Upload ─────────────────────────────────────────────
        st.markdown("### ✅ Attendance Data")
        render_html("""
        <div class="upload-hint">
            Upload CSV/Excel with student names, present/absent/late counts.
        </div>
        """)
        att_upload = st.file_uploader(
            "Attendance file", type=["csv","xlsx","xls"],
            accept_multiple_files=False, key="att_upload",
            label_visibility="collapsed"
        )
        if att_upload:
            st.markdown(f'<div style="font-size:0.7rem;color:#10b981;">📄 {att_upload.name}</div>',
                        unsafe_allow_html=True)
        st.divider()

        # ── Fee Upload ────────────────────────────────────────────────────
        st.markdown("### 💰 Fee Data")
        render_html("""
        <div class="upload-hint">
            Upload CSV/Excel with fee amounts, payment status, balances.
        </div>
        """)
        fee_upload = st.file_uploader(
            "Fee file", type=["csv","xlsx","xls"],
            accept_multiple_files=False, key="fee_upload",
            label_visibility="collapsed"
        )
        if fee_upload:
            st.markdown(f'<div style="font-size:0.7rem;color:#10b981;">📄 {fee_upload.name}</div>',
                        unsafe_allow_html=True)
        st.divider()

        # ── Display Settings ──────────────────────────────────────────────
        st.markdown("### ⚙️ Display Settings")
        top_n    = st.slider("Top-N students in chart", 5, 30, 10)
        show_raw = st.checkbox("Show raw data tables", value=True)

        st.divider()
        st.markdown(
            '<div style="font-size:0.65rem;color:#44403c;text-align:center;">'
            'Student Intelligence Portal v3.0<br>'
            '<span style="color:#292524;">Streamlit · Groq · Plotly</span></div>',
            unsafe_allow_html=True
        )

        return xai_key, exam_uploads or [], fee_upload, att_upload, top_n, show_raw
