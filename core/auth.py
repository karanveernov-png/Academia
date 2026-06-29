"""
core.auth — login screen, session-state auth, and logout handling.

This is the bridge between login.py (the old standalone login screen)
and app.py (the real upload-driven dashboard). It owns:
  • session_state initialization for auth
  • the login page UI (same look as the original login.py)
  • logout()

⚠️ Demo credentials only — replace with real auth (DB / hashed passwords /
   an identity provider) before putting this in front of real users.
     Student → student / 1234
     Admin   → admin   / admin123
"""
import streamlit as st


# ──────────────────────────────────────────────────────────────────────────
# Session state
# ──────────────────────────────────────────────────────────────────────────
def init_auth_state() -> None:
    """Make sure auth keys exist before anything else touches them."""
    if "logged_in" not in st.session_state:
        st.session_state["logged_in"] = False
        st.session_state["role"] = None
        st.session_state["username"] = None


def is_logged_in() -> bool:
    return bool(st.session_state.get("logged_in", False))


def logout() -> None:
    st.session_state["logged_in"] = False
    st.session_state["role"] = None
    st.session_state["username"] = None


# ──────────────────────────────────────────────────────────────────────────
# Login page styling (lifted from the original login.py)
# ──────────────────────────────────────────────────────────────────────────
def inject_login_css() -> None:
    st.markdown("""
    <style>
    [data-testid="stHeader"] { background-color: transparent !important; }
    .block-container { padding-top: 2rem !important; }

    .stApp {
        background: linear-gradient(135deg, #0b1121 40%, #c48b6d 100%);
        background-attachment: fixed;
    }

    h1, h2, h3, p, span, div { color: #ffffff !important; }

    [data-testid="stForm"] {
        background-color: #ffffff;
        border-radius: 15px;
        padding: 35px 30px;
        border: none;
        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5);
    }

    [data-testid="stForm"] h1,
    [data-testid="stForm"] h2,
    [data-testid="stForm"] h3,
    [data-testid="stForm"] p,
    [data-testid="stForm"] span,
    [data-testid="stForm"] label,
    [data-testid="stForm"] div { color: #374151 !important; }

    .stTextInput input {
        border-radius: 6px;
        border: 1px solid #d1d5db;
        padding: 10px;
        background-color: #f9fafb;
        color: #111827 !important;
    }

    .stButton>button {
        width: 100%;
        background-color: #f97316 !important;
        color: white !important;
        border: none;
        border-radius: 6px;
        padding: 10px;
        font-weight: bold;
        box-shadow: 0 4px 6px rgba(249, 115, 22, 0.3);
        transition: all 0.3s ease;
    }
    .stButton>button:hover {
        background-color: #ea580c !important;
        box-shadow: 0 6px 12px rgba(249, 115, 22, 0.4);
        transform: translateY(-2px);
    }

    .stTabs [data-baseweb="tab-list"] {
        background-color: transparent;
        justify-content: center;
        gap: 20px;
    }
    .stTabs [data-baseweb="tab"] {
        color: #e5e7eb;
        background-color: rgba(255, 255, 255, 0.1);
        border-radius: 8px 8px 0 0;
    }
    .stTabs [aria-selected="true"] {
        color: #f97316 !important;
        border-bottom: 3px solid #f97316 !important;
        background-color: rgba(255, 255, 255, 0.2);
    }
    </style>
    """, unsafe_allow_html=True)


# ──────────────────────────────────────────────────────────────────────────
# Login page UI
# ──────────────────────────────────────────────────────────────────────────
def render_login_page() -> None:
    st.title("🎓 Portal Login")

    with st.container():
        st.markdown("### Welcome Back! Please select your role.")

        student_tab, admin_tab = st.tabs(["🧑‍🎓 Student Login", "👨‍💻 Admin Login"])

        # ── Student login ───────────────────────────────────────────────
        with student_tab:
            with st.form("student_form"):
                st.write("Sign in to your student account")
                s_username = st.text_input("Student ID", placeholder="Enter your student ID")
                s_password = st.text_input("Password", type="password", placeholder="Enter your password")
                s_submit = st.form_submit_button("Student Login")

                if s_submit:
                    if s_username == "student" and s_password == "1234":
                        st.session_state["logged_in"] = True
                        st.session_state["role"] = "student"
                        st.session_state["username"] = s_username
                        st.rerun()
                    else:
                        st.error("Incorrect Student ID or Password.")

        # ── Admin login ──────────────────────────────────────────────────
        with admin_tab:
            with st.form("admin_form"):
                st.write("Sign in to the administrative portal")
                a_username = st.text_input("Admin Username", placeholder="Enter admin username")
                a_password = st.text_input("Password", type="password", placeholder="Enter admin password")
                a_submit = st.form_submit_button("Admin Login")

                if a_submit:
                    if a_username == "admin" and a_password == "admin123":
                        st.session_state["logged_in"] = True
                        st.session_state["role"] = "admin"
                        st.session_state["username"] = a_username
                        st.rerun()
                    else:
                        st.error("Incorrect Admin credentials.")
