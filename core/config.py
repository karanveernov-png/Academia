"""
core.config — shared constants and page configuration.
Warm orange / terracotta theme — matches the login page.
"""
try:
    from reportlab.lib import colors as rl_colors
    GRADE_COLORS = {
        "A+": rl_colors.HexColor("#15803d"), "A":  rl_colors.HexColor("#16a34a"),
        "B+": rl_colors.HexColor("#c2410c"), "B":  rl_colors.HexColor("#ea580c"),
        "C":  rl_colors.HexColor("#d97706"), "D":  rl_colors.HexColor("#b45309"),
        "F":  rl_colors.HexColor("#dc2626"),
    }
except ImportError:
    GRADE_COLORS = {}

APP_TITLE = "Student Intelligence Portal"
APP_ICON  = "🎓"

# Chart palette — warm orange / amber / terracotta theme
CHART_BG   = "rgba(0,0,0,0)"
CHART_FONT = "#94a3b8"
GRID_COLOR = "rgba(255,255,255,0.05)"
TITLE_FONT = "#fdba74"          # warm peach / orange-200
ACCENT_SEQ = ["#f97316","#fb923c","#fdba74","#c2410c","#ea580c","#fbbf24","#f59e0b"]
RISK_COLORS= {"High":"#f87171","Medium":"#fbbf24","Low":"#34d399"}
GRADE_ORDER= ["A+","A","B+","B","C","D","F"]


def configure_page(page_title=None, page_icon=None, layout="wide", sidebar_state="expanded"):
    import streamlit as st
    st.set_page_config(
        page_title=page_title or APP_TITLE,
        page_icon=page_icon or APP_ICON,
        layout=layout,
        initial_sidebar_state=sidebar_state,
    )
