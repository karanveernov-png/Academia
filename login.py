"""
login.py — DEPRECATED ENTRY POINT
==================================
Login is now built directly into app.py (see core/auth.py).
You no longer need to run this file.

Run the portal with:
    streamlit run app.py
"""
import streamlit as st

st.set_page_config(page_title="Moved", page_icon="↪️", layout="centered")
st.title("↪️ This file has moved")
st.info(
    "Login is now built into **app.py**.\n\n"
    "Please run the portal with:\n\n"
    "```\nstreamlit run app.py\n```"
)
