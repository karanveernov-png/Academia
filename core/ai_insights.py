"""
core.ai_insights
=================
Groq LLaMA call that turns a single exam's KPI dict into a teacher-
ready written summary. Cached for 1 hour per unique KPI payload so
the same exam/data does not re-call the API.
"""
import streamlit as st
from groq import Groq


@st.cache_data(show_spinner=False, ttl=3600)
def get_xai_insights(kpis: dict, xai_key: str, exam_label: str = "Exam") -> str:
    """Call Groq LLaMA to generate teacher-friendly insights from KPIs.
    Cached for 1hr so identical KPIs (same exam, same data) don't re-call the API."""
    if not xai_key:
        return "⚠️ Enter your Groq API key in the sidebar to enable AI insights."

    system_prompt = (
        "You are an expert educational data analyst and academic performance coach with 15+ years of "
        "experience advising teachers and school administrators. Your analyses are precise, data-driven, "
        "empathetic to student needs, and immediately actionable. Always ground recommendations in the "
        "specific numbers provided — never give vague advice. Prioritise students at risk of failure."
    )

    prompt = f"""Analyse the following student performance KPIs for the exam '{exam_label}' and produce a structured report with EXACTLY these sections:

**📋 Executive Summary** (2–3 sentences — include concrete numbers)
**🏆 Key Strengths** (2 bullet points — data-backed positives)
**⚠️ Critical Concerns** (2 bullet points — immediate risk areas with numbers)
**🎯 Actionable Recommendations** (3 numbered items — specific, practical, teacher-ready)
**📌 Priority Focus** (1 sentence — the single most important action right now)

KPI Data:
- Total students      : {kpis['total']}
- Average percentage  : {kpis['avg_pct']}%
- Average total marks : {kpis['avg_total']}
- Pass rate           : {kpis['pass_rate']}%
- At-risk students    : {kpis['at_risk_n']} ({round(kpis['at_risk_n']/max(kpis['total'],1)*100,1)}% of class)
- Detained students   : {kpis.get('detained_n', 0)}
- Top scorer          : {kpis['top_name']} ({kpis['top_marks']} marks)
- Lowest scorer       : {kpis['bot_name']} ({kpis['bot_marks']} marks)
- Grade distribution  : {kpis['grade_dist']}
- Subject averages    : {kpis.get('subject_avg', {})}

Rules: be specific (use the actual numbers above), be concise (≤350 words total), use markdown formatting for the section headers."""

    try:
        client = Groq(api_key=xai_key)
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            max_tokens=600,
            temperature=0.4,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"❌ Groq API Error: {e}"


