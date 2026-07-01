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

# Invisible / zero-width characters that sometimes ride along when an API
# key is copy-pasted (from a browser, PDF, Notion, WhatsApp, etc.). They're
# invisible on screen but break HTTP header encoding, causing errors like
# "'ascii' codec can't encode character '\u200b' ... ordinal not in range(128)".
_INVISIBLE_CHARS = (
    "\u200b"  # zero-width space
    "\u200c"  # zero-width non-joiner
    "\u200d"  # zero-width joiner
    "\u2060"  # word joiner
    "\ufeff"  # byte-order mark
    "\u00a0"  # non-breaking space
    "\u202a\u202b\u202c\u202d\u202e"  # bidi control chars
)


def _sanitize_key(raw: str) -> str:
    """Strip whitespace and any invisible/non-ASCII characters from an API
    key. A real Groq key is always plain printable ASCII, so anything
    outside that range is junk that snuck in during copy-paste and would
    otherwise crash the HTTP client when it tries to send it as a header."""
    if not raw:
        return ""
    cleaned = str(raw).strip()
    for ch in _INVISIBLE_CHARS:
        cleaned = cleaned.replace(ch, "")
    # Keep only printable ASCII (32-126) — drop anything else silently.
    cleaned = "".join(c for c in cleaned if 32 < ord(c) < 127)
    return cleaned.strip()


def resolve_api_key(user_input: str = "") -> str:
    """Return the Groq API key to use for this request.

    `user_input` is whatever the person typed into the text box (or ""
    if they left it blank). A non-empty user_input always wins.
    """
    if user_input and user_input.strip():
        return _sanitize_key(user_input)

    try:
        secret_key = st.secrets.get("GROQ_API_KEY", "")
        if secret_key:
            return _sanitize_key(secret_key)
    except Exception:
        pass

    env_key = os.environ.get("GROQ_API_KEY", "")
    if env_key:
        return _sanitize_key(env_key)

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
