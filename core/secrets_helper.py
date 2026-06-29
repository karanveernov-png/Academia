"""
core.secrets_helper
====================
Central place that decides which Groq API key to actually use, so no
key ever has to be hardcoded/pasted directly inside app.py / sidebar.py.

Priority order (first one found wins):
  1. A key the person typed into the on-screen "API Key" box —
     this lets any visitor bring their own key without touching any files.
  2. A default key the *owner* of this app configured privately in
     `.streamlit/secrets.toml` (kept out of git — see
     `.streamlit/secrets.toml.example` for the format).
  3. A default key set via the GROQ_API_KEY environment variable
     (handy for Docker / server deployments).
  4. "" — no key available anywhere; AI features stay locked until
     someone provides one.

On Streamlit Community Cloud, step 2 is normally configured through
"App settings → Secrets" in the dashboard instead of a real file —
either way it ends up readable through `st.secrets`, and never sits in
the source code.
"""
import os
import streamlit as st


def resolve_api_key(user_input: str = "") -> str:
    """Return the Groq API key to use for this request.

    `user_input` is whatever the person typed into the text box (or ""
    if they left it blank). A non-empty user_input always wins.
    """
    if user_input and user_input.strip():
        return user_input.strip()

    try:
        secret_key = st.secrets.get("GROQ_API_KEY", "")
        if secret_key:
            return str(secret_key).strip()
    except Exception:
        pass

    env_key = os.environ.get("GROQ_API_KEY", "")
    if env_key:
        return env_key.strip()

    return ""


def has_default_key() -> bool:
    """True if the app owner has configured a shared/default key
    (via secrets.toml or env var), regardless of what the user typed."""
    try:
        if st.secrets.get("GROQ_API_KEY", ""):
            return True
    except Exception:
        pass
    return bool(os.environ.get("GROQ_API_KEY", ""))
