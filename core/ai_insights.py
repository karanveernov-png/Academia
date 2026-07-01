"""
core.ai_insights
=================
Groq LLaMA call that turns a single exam's KPI dict into a teacher-
ready written summary. Cached for 1 hour per unique KPI payload so
the same exam/data does not re-call the API.
"""
import streamlit as st
from groq import Groq

# Same invisible-character set used for API keys — KPI values (student
# names pulled from uploaded spreadsheets) can carry these too, and they
# trigger the same "'ascii' codec can't encode character ..." crash if they
# end up inside the request.
_INVISIBLE_CHARS = (
    "\u200b\u200c\u200d\u2060\ufeff\u00a0"
    "\u202a\u202b\u202c\u202d\u202e"
)


def _clean(value):
    """Strip invisible unicode characters from any string value (leaves
    non-strings untouched)."""
    if isinstance(value, str):
        for ch in _INVISIBLE_CHARS:
            value = value.replace(ch, "")
        return value.encode("ascii", "ignore").decode("ascii")
    if isinstance(value, dict):
        return {_clean(k): _clean(v) for k, v in value.items()}
    return value


@st.cache_data(show_spinner=False, ttl=3600)
def get_xai_insights(kpis: dict, xai_key: str, exam_label: str = "Exam") -> str:
    """Call Groq LLaMA to generate teacher-friendly insights from KPIs.
    Cached for 1hr so identical KPIs (same exam, same data) don't re-call the API."""
    if not xai_key:
        return "⚠️ Enter your Groq API key in the sidebar to enable AI insights."

    exam_label = _clean(exam_label) or "Exam"
    top_name = _clean(kpis.get("top_name", "N/A"))
    bot_name = _clean(kpis.get("bot_name", "N/A"))
    grade_dist = _clean(kpis.get("grade_dist", {}))
    subject_avg = _clean(kpis.get("subject_avg", {}))

    system_prompt = (
        "You are an expert educational data analyst. You write short, precise, "
        "teacher-ready performance summaries grounded only in the numbers given. "
        "You are deliberately concise — no filler, no repetition."
    )

    prompt = f"""Analyse these student performance KPIs for '{exam_label}' and produce a SHORT report with EXACTLY these sections (keep every section brief):

**📋 Summary** (1 sentence, include 1-2 concrete numbers)
**🏆 Strength** (1 bullet, data-backed)
**⚠️ Concern** (1 bullet, the single biggest risk area with a number)
**🎯 Top Action** (1-2 numbered items, specific and teacher-ready)

KPI Data:
- Total students      : {kpis['total']}
- Average percentage  : {kpis['avg_pct']}%
- Pass rate           : {kpis['pass_rate']}%
- At-risk students    : {kpis['at_risk_n']} ({round(kpis['at_risk_n']/max(kpis['total'],1)*100,1)}% of class)
- Detained students   : {kpis.get('detained_n', 0)}
- Top scorer          : {top_name} ({kpis['top_marks']} marks)
- Lowest scorer       : {bot_name} ({kpis['bot_marks']} marks)
- Grade distribution  : {grade_dist}
- Subject averages    : {subject_avg}

Rules: be specific (use the actual numbers above), STRICT LIMIT of 110 words total, use markdown for the section headers, no preamble, no closing remarks."""

    try:
        client = Groq(api_key=xai_key)
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            max_tokens=220,
            temperature=0.4,
        )
        return response.choices[0].message.content.strip()
    except UnicodeEncodeError:
        return ("❌ Your Groq API key contains a hidden/invisible character (often picked up "
                "when copy-pasting). Please re-type or re-paste it as plain text in the sidebar "
                "and try again.")
    except Exception as e:
        return f"❌ Groq API Error: {e}"


