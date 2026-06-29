"""
core.styling — unified CSS for the entire portal.
Warm orange / terracotta theme that mirrors the login page.
  Login page palette:
    Background : linear-gradient(135deg, #0b1121 40%, #c48b6d 100%)
    Accent     : #f97316  (orange-500)
    Hover      : #ea580c  (orange-600)
    Form bg    : white card
Call inject_css() once at the top of app.py.
"""
import streamlit as st

_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap');

*, *::before, *::after { box-sizing: border-box; }
html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
}

/* ── Background — matches login gradient ── */
.stApp {
    background:
        radial-gradient(ellipse at 0% 0%,   rgba(249,115,22,0.12) 0%, transparent 50%),
        radial-gradient(ellipse at 100% 100%, rgba(196,139,109,0.10) 0%, transparent 50%),
        linear-gradient(135deg, #0b1121 0%, #0f1829 40%, #1a1008 70%, #0b1121 100%);
    min-height: 100vh;
}
.main .block-container { padding: 1.8rem 2.2rem 3rem; max-width: 1500px; }

/* ── Sidebar ── */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, rgba(15,12,20,0.98) 0%, rgba(11,9,18,0.99) 100%);
    border-right: 1px solid rgba(249,115,22,0.2);
    box-shadow: 4px 0 30px rgba(0,0,0,0.4);
}
[data-testid="stSidebar"]::before {
    content: '';
    position: absolute; top: 0; left: 0; right: 0; height: 3px;
    background: linear-gradient(90deg, #f97316, #c48b6d, #fbbf24);
}
[data-testid="stSidebar"] .stMarkdown { color: #e2e8f0; }
[data-testid="stSidebar"] h3 {
    color: #fdba74 !important; font-size: 0.78rem !important;
    text-transform: uppercase; letter-spacing: 0.12em; margin-bottom: 0.5rem !important;
}

/* Sidebar logo */
.sidebar-logo { text-align:center; padding:1.4rem 0.5rem 0.8rem; }
.sidebar-logo-icon {
    font-size: 2.8rem; display:block; margin-bottom:0.3rem;
    filter: drop-shadow(0 0 16px rgba(249,115,22,0.7));
}
.sidebar-logo-title {
    font-size: 1rem; font-weight: 700;
    background: linear-gradient(135deg, #fdba74, #f97316, #fbbf24);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text;
}
.sidebar-logo-sub { font-size:0.68rem; color:#78716c; margin-top:0.2rem; letter-spacing:0.05em; }
.sidebar-badge {
    display:inline-block;
    background:linear-gradient(135deg,rgba(249,115,22,0.2),rgba(196,139,109,0.2));
    border:1px solid rgba(249,115,22,0.35); border-radius:20px;
    padding:2px 10px; font-size:0.63rem; color:#fdba74; margin-top:0.3rem;
    letter-spacing:0.06em; text-transform:uppercase;
}
.sidebar-section-label {
    font-size:0.72rem; font-weight:700; text-transform:uppercase;
    letter-spacing:0.12em; color:#f97316; margin:1.2rem 0 0.5rem;
}

/* ── Section headers ── */
.section-header {
    font-size:0.76rem; font-weight:700; text-transform:uppercase;
    letter-spacing:0.12em; color:#f97316;
    margin:1.6rem 0 0.9rem;
    display:flex; align-items:center; gap:0.5rem;
}
.section-header-count {
    background:rgba(249,115,22,0.15); border:1px solid rgba(249,115,22,0.25);
    border-radius:20px; padding:1px 8px; font-size:0.63rem; color:#fdba74;
}

/* ── KPI Cards ── */
.kpi-card {
    background:linear-gradient(145deg,rgba(249,115,22,0.1),rgba(196,139,109,0.06));
    border:1px solid rgba(249,115,22,0.22); border-radius:16px;
    padding:1.1rem 0.8rem; text-align:center; position:relative; overflow:hidden;
    transition:transform 0.2s, box-shadow 0.2s;
}
.kpi-card:hover { transform:translateY(-2px); box-shadow:0 8px 24px rgba(249,115,22,0.15); }
.kpi-card.green { background:linear-gradient(145deg,rgba(16,185,129,0.1),rgba(5,150,105,0.06)); border-color:rgba(16,185,129,0.25); }
.kpi-card.red   { background:linear-gradient(145deg,rgba(239,68,68,0.1),rgba(220,38,38,0.06));   border-color:rgba(239,68,68,0.25); }
.kpi-card.amber { background:linear-gradient(145deg,rgba(251,191,36,0.1),rgba(245,158,11,0.06));  border-color:rgba(251,191,36,0.25); }
.kpi-card.gold  { background:linear-gradient(145deg,rgba(249,115,22,0.15),rgba(234,88,12,0.08)); border-color:rgba(249,115,22,0.3); }
.kpi-card.sky   { background:linear-gradient(145deg,rgba(14,165,233,0.1),rgba(2,132,199,0.06));  border-color:rgba(14,165,233,0.25); }
.kpi-card.pink  { background:linear-gradient(145deg,rgba(196,139,109,0.15),rgba(180,115,80,0.08)); border-color:rgba(196,139,109,0.3); }
.kpi-icon  { font-size:1.6rem; display:block; margin-bottom:0.3rem; }
.kpi-value { font-size:1.55rem; font-weight:800; color:#e2e8f0; line-height:1.1;
             white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.kpi-label { font-size:0.68rem; color:#78716c; text-transform:uppercase;
             letter-spacing:0.08em; margin-top:0.25rem; }
.kpi-sub   { font-size:0.7rem; color:#f97316; margin-top:0.2rem;
             white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }

/* ── AI box ── */
.ai-box {
    background:linear-gradient(135deg,rgba(249,115,22,0.07),rgba(196,139,109,0.04));
    border:1px solid rgba(249,115,22,0.2); border-radius:14px;
    padding:1.2rem 1.4rem; font-size:0.87rem; color:#cbd5e1; line-height:1.7;
}

/* ── Command bar ── */
.cmd-bar-wrap { margin-bottom:0.5rem; }
.cmd-hint { display:flex; gap:0.4rem; flex-wrap:wrap; margin-bottom:0.4rem; }
.cmd-chip {
    background:rgba(249,115,22,0.1); border:1px solid rgba(249,115,22,0.2);
    border-radius:20px; padding:3px 10px; font-size:0.7rem; color:#fdba74; cursor:default;
}

/* ── File info bar ── */
.file-info-bar {
    background:rgba(249,115,22,0.08); border:1px solid rgba(249,115,22,0.15);
    border-radius:8px; padding:6px 12px; font-size:0.78rem; color:#fdba74;
    margin-bottom:0.8rem;
}

/* ── Hero chips ── */
.hero-chip {
    background:rgba(255,255,255,0.1); border:1px solid rgba(249,115,22,0.3);
    border-radius:20px; padding:3px 12px; font-size:0.72rem; color:rgba(255,200,150,0.9);
}

/* ── Welcome cards ── */
.welcome-card {
    background:rgba(249,115,22,0.07); border:1px solid rgba(249,115,22,0.18);
    border-radius:12px; padding:0.9rem 1rem;
}

/* ── Upload hint box ── */
.upload-hint {
    background:rgba(255,255,255,0.02); border:1px dashed rgba(249,115,22,0.2);
    border-radius:12px; padding:0.8rem 1.1rem; font-size:0.78rem; color:#78716c;
    margin-bottom:0.5rem; line-height:1.6;
}

/* ── Attendance bars ── */
.att-bar-wrap { display:flex; align-items:center; gap:8px; }
.att-bar-bg   { height:8px; border-radius:4px; background:rgba(255,255,255,0.07); flex:1; }
.att-bar-fill { height:100%; border-radius:4px; }

/* ── Badges ── */
.badge {
    display:inline-block; border-radius:6px; padding:2px 9px;
    font-size:0.7rem; font-weight:700; letter-spacing:0.02em;
}
.badge-green   { background:rgba(16,185,129,0.15); color:#6ee7b7; border:1px solid rgba(16,185,129,0.3); }
.badge-amber   { background:rgba(251,191,36,0.15);  color:#fcd34d; border:1px solid rgba(251,191,36,0.3); }
.badge-red     { background:rgba(239,68,68,0.15);   color:#fca5a5; border:1px solid rgba(239,68,68,0.3); }
.badge-blue    { background:rgba(249,115,22,0.15);  color:#fdba74; border:1px solid rgba(249,115,22,0.3); }
.badge-purple  { background:rgba(196,139,109,0.15); color:#e0b99a; border:1px solid rgba(196,139,109,0.3); }
.badge-paid    { background:rgba(16,185,129,0.15);  color:#6ee7b7; border:1px solid rgba(16,185,129,0.3); }
.badge-due     { background:rgba(251,191,36,0.15);  color:#fcd34d; border:1px solid rgba(251,191,36,0.3); }
.badge-overdue { background:rgba(239,68,68,0.15);   color:#fca5a5; border:1px solid rgba(239,68,68,0.3); }
.badge-partial { background:rgba(196,139,109,0.15); color:#e0b99a; border:1px solid rgba(196,139,109,0.3); }

/* ── Streamlit overrides ── */
.stTabs [data-baseweb="tab-list"] {
    gap:0.3rem; background:rgba(255,255,255,0.02); border-radius:12px; padding:4px;
}
.stTabs [data-baseweb="tab"] {
    border-radius:8px; padding:6px 14px; font-size:0.8rem; font-weight:500; color:#78716c;
    background:transparent; border:none;
}
.stTabs [aria-selected="true"] {
    background:rgba(249,115,22,0.18) !important; color:#fdba74 !important;
    border:1px solid rgba(249,115,22,0.3) !important;
}
div[data-testid="stMetric"] { background:transparent; }
.stButton > button {
    background: linear-gradient(135deg, #f97316, #ea580c) !important;
    color: white !important; border: none; border-radius: 10px;
    font-weight: 600; font-size: 0.82rem;
    padding: 0.45rem 1.1rem;
    box-shadow: 0 4px 6px rgba(249,115,22,0.3);
    transition: all 0.3s ease;
}
.stButton > button:hover {
    background: linear-gradient(135deg, #ea580c, #c2410c) !important;
    box-shadow: 0 6px 12px rgba(249,115,22,0.4);
    transform: translateY(-1px);
}
.stSelectbox > div > div, .stMultiSelect > div > div {
    background:rgba(255,255,255,0.04); border-color:rgba(249,115,22,0.25) !important;
    border-radius:10px; color:#e2e8f0;
}
.stTextInput > div > div > input {
    background:rgba(255,255,255,0.04); border-color:rgba(249,115,22,0.25);
    border-radius:10px; color:#e2e8f0; font-size:0.88rem;
}
.stDataFrame { border-radius:12px; overflow:hidden; }
div[data-testid="stExpander"] {
    background:rgba(255,255,255,0.02); border:1px solid rgba(249,115,22,0.12);
    border-radius:12px;
}
/* Slider accent */
[data-testid="stSlider"] > div > div > div > div {
    background: #f97316 !important;
}
/* Divider */
hr { border-color: rgba(249,115,22,0.15) !important; }
</style>
"""


def inject_css():
    st.markdown(_CSS, unsafe_allow_html=True)
