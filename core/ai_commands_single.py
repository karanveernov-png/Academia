"""
core.ai_commands_single
========================
Natural-language command bar for a SINGLE exam: local (zero-API-call)
shortcuts for common questions (rank, profile, tips, simple charts/
filters), an AI fallback parser via Groq for anything more open-ended,
and the executor that turns a parsed command into a chart/table/text.
"""
import json
import re as _re
import textwrap
import pandas as pd
import numpy as np
import streamlit as st
from groq import Groq

from core.data_loader import prepare_data
from core.charts import chart_grade_pie, chart_top_n_students, chart_score_distribution


def _build_student_profile_text(student_name: str, view_df: pd.DataFrame,
                                  mapping: dict, detain_threshold: float,
                                  include_tips: bool = True) -> tuple:
    """
    Build a rich, teacher-ready profile for a single student using only
    pandas computations — no API call needed. Returns (kind, payload).

    Covers: rank, percentile, grade, risk, per-subject marks, detained flag,
    distance to next rank, weakest subjects, and personalised improvement tips.
    """
    if "Student_Name" not in view_df.columns:
        return "error", "No student name column found."

    match = _find_student(view_df, student_name)
    if match.empty:
        return "error", f"Couldn't find a student matching '{student_name}'."

    row = match.iloc[0]
    name   = row.get("Student_Name", "N/A")
    total  = row.get("Total_Marks", 0)
    pct    = row.get("Percentage", 0)
    grade  = row.get("Grade", "N/A")
    risk   = row.get("Risk", "N/A")
    detained = bool(row.get("Detained", False))

    # ── Rank & percentile ──────────────────────────────────────────────────
    ranked = view_df.sort_values("Percentage", ascending=False).reset_index(drop=True)
    rank_pos = int(ranked[ranked["Student_Name"] == name].index[0]) + 1 if name in ranked["Student_Name"].values else None
    total_students = len(view_df)
    percentile = round((1 - rank_pos / total_students) * 100, 1) if rank_pos else None

    # ── Distance to next rank above ────────────────────────────────────────
    next_student = None
    marks_gap = None
    if rank_pos and rank_pos > 1:
        above_row = ranked.iloc[rank_pos - 2]  # 0-indexed row above
        next_student = above_row.get("Student_Name", "N/A")
        marks_gap = round(float(above_row.get("Total_Marks", 0)) - float(total), 2)

    # ── Per-subject breakdown & weak areas ────────────────────────────────
    subject_cols = [c for c in (mapping.get("marks") or []) if c in view_df.columns]
    class_avgs   = {c: round(view_df[c].mean(), 2) for c in subject_cols}
    student_marks = {c: row.get(c) for c in subject_cols if pd.notna(row.get(c))}

    weak   = []
    strong = []
    for c in subject_cols:
        sm = student_marks.get(c)
        ca = class_avgs.get(c, 0)
        if sm is None:
            continue
        diff = round(float(sm) - ca, 2)
        if diff < 0:
            weak.append((c, float(sm), ca, diff))
        else:
            strong.append((c, float(sm), ca, diff))

    weak.sort(key=lambda x: x[3])   # biggest deficit first

    # ── Build output text ──────────────────────────────────────────────────
    detained_badge = "🚫 YES" if detained else "✅ No"
    risk_icon = {"High": "🔴", "Medium": "🟡", "Low": "🟢"}.get(risk, "⚪")

    lines = [
        f"## 👤 {name}",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| 🏅 Rank | **#{rank_pos} of {total_students}** |" if rank_pos else "| 🏅 Rank | N/A |",
        f"| 📊 Percentile | **Top {100 - percentile:.0f}%** |" if percentile is not None else "",
        f"| 📝 Total Marks | **{total}** |",
        f"| 📈 Percentage | **{pct}%** |",
        f"| 🎓 Grade | **{grade}** |",
        f"| {risk_icon} Risk Level | **{risk}** |",
        f"| 🚫 Detained | **{detained_badge}** (threshold: {detain_threshold:.0f}%) |",
    ]

    if next_student and marks_gap is not None:
        lines.append(f"| ⬆️ Next Rank | **{next_student}** — needs **+{marks_gap:.1f} marks** |")

    # Per-subject table
    if student_marks:
        lines += ["", "### 📚 Subject Breakdown", "",
                  "| Subject | Score | Class Avg | Δ |",
                  "|---------|-------|-----------|---|"]
        for c in subject_cols:
            sm = student_marks.get(c)
            if sm is None:
                continue
            ca = class_avgs.get(c, 0)
            diff = round(float(sm) - ca, 2)
            arrow = "🔺" if diff >= 0 else "🔻"
            lines.append(f"| {c} | {sm:.1f} | {ca:.1f} | {arrow} {diff:+.1f} |")

    if include_tips:
        lines += ["", "### 🎯 Personalised Improvement Tips", ""]

        if not weak:
            lines.append("✅ **Above class average in all subjects!** Keep up the consistency.")
        else:
            lines.append(f"**Priority: focus on these {len(weak)} weak area(s):**\n")
            for i, (subj, sm, ca, diff) in enumerate(weak[:3], 1):
                needed = round(ca - sm, 1)
                tip = _subject_tip(subj)
                lines.append(
                    f"{i}. **{subj}** — scored {sm:.1f} vs class avg {ca:.1f} "
                    f"(gap: {diff:.1f} marks). *Need +{needed:.1f} to reach class average.*  \n"
                    f"   💡 {tip}"
                )

        if detained:
            lines += [
                "",
                f"⚠️ **Detention Alert:** {name} is below the {detain_threshold:.0f}% threshold. "
                f"Recommend immediate intervention: extra practice sessions, personal mentoring, "
                f"and regular progress checks."
            ]

        if risk == "High":
            lines += [
                "",
                "🔴 **High-Risk Student:** Prioritise this student for teacher attention. "
                "Consider connecting with parents/guardians and creating a structured study plan."
            ]
        elif risk == "Medium":
            lines += [
                "",
                "🟡 **Medium-Risk:** Regular monitoring recommended. "
                "Ensure the student is attending support classes and reviewing past mistakes."
            ]

        if strong:
            lines += ["", f"✅ **Already strong in:** " + ", ".join(f"**{s[0]}** (+{s[3]:.1f})" for s in strong[:3])]

        if next_student and marks_gap is not None:
            lines += [
                "",
                f"🚀 **To reach Rank #{rank_pos - 1}** ({next_student}): need **+{marks_gap:.1f} marks** overall. "
                f"{'Focus on the weakest subject above — that alone may close the gap.' if weak else 'Improve consistency across all subjects.'}"
            ]

    return "text", "\n".join(l for l in lines if l is not None)


def _subject_tip(subject_name: str) -> str:
    """Return a generic but contextual study tip based on the subject name."""
    s = subject_name.lower()
    if any(x in s for x in ["math", "maths", "algebra", "calculus", "arithmetic"]):
        return "Practice 10 problems daily. Focus on formula memorisation and step-by-step working."
    if any(x in s for x in ["english", "grammar", "language", "literature"]):
        return "Read one passage per day, practice writing answers in full sentences, and revise vocabulary."
    if any(x in s for x in ["science", "physics", "chemistry", "biology", "bio"]):
        return "Diagram key concepts, revise definitions, and solve past paper MCQs."
    if any(x in s for x in ["history", "social", "geo", "geography", "civics", "sst"]):
        return "Create timeline/mind-maps for events. Revise dates and key terms regularly."
    if any(x in s for x in ["computer", "cs", "coding", "it", "informatics"]):
        return "Practice writing programs by hand, revise theory definitions, and do past paper questions."
    if any(x in s for x in ["hindi", "urdu", "punjabi", "marathi", "telugu", "tamil", "bengali"]):
        return "Practice grammar rules, learn new words daily, and read comprehension passages."
    return "Review class notes, solve practice questions, and ask teachers to clarify doubts on weak topics."


def _single_exam_local_shortcut(query: str, df_raw: pd.DataFrame,
                                  mapping: dict, detain_threshold: float):
    """
    Try to answer common high-value queries LOCALLY (zero API calls).
    Returns (kind, payload) if handled, or None to let the AI take over.

    Handles:
    - "rank of <student>" / "<student>'s rank"
    - "tips for <student>" / "how to improve <student>"
    - "profile of <student>" / "show <student>"
    - "rank students" / "leaderboard" (already handled by local parser but
      added here too for speed — bypasses the Groq round-trip)
    - "topper" / "who topped"
    - "lowest scorer" / "who failed"
    """
    q = query.lower().strip()
    view_df = prepare_data(df_raw, mapping, detain_threshold=detain_threshold)

    # ── "rank students" / "leaderboard" / "top 10 list" ──
    if _re.search(r"\b(leaderboard|rank\s+all|rank\s+students|full\s+rank|all\s+students\s+rank)\b", q):
        cols = [c for c in ["Student_Name", "Student_ID", "Total_Marks", "Percentage", "Grade", "Detained"] if c in view_df.columns]
        return "table", view_df[cols].sort_values("Percentage", ascending=False).reset_index(drop=True)

    # ── "topper" / "who topped" ──
    if _re.search(r"\b(topper|who\s+topped|highest\s+scorer|best\s+student)\b", q):
        top_row = view_df.loc[view_df["Percentage"].idxmax()]
        name = top_row.get("Student_Name", "N/A")
        return _build_student_profile_text(name, view_df, mapping, detain_threshold, include_tips=False)

    # ── "lowest scorer" / "who failed most" ──
    if _re.search(r"\b(lowest\s+scorer|worst\s+student|bottom\s+student|who\s+failed|least\s+marks)\b", q):
        bot_row = view_df.loc[view_df["Percentage"].idxmin()]
        name = bot_row.get("Student_Name", "N/A")
        return _build_student_profile_text(name, view_df, mapping, detain_threshold, include_tips=True)

    # ── Student-specific queries: rank / tips / profile / improvement ──
    patterns = [
        r"(?:rank\s+of|rank\s+for)\s+([a-z][a-z\s.]{1,30})",
        r"([a-z][a-z\s.]{1,30})[''`]?s\s+rank",
        r"(?:tips\s+for|improve|improvement\s+for|how\s+(?:can|should|to\s+help)\s+)([a-z][a-z\s.]{1,30})",
        r"(?:profile\s+of|show\s+me|tell\s+me\s+about|details\s+of|info(?:rmation)?\s+(?:on|about)\s+)([a-z][a-z\s.]{1,30})",
        r"(?:what\s+(?:is|are|should|can)\s+)([a-z][a-z\s.]{1,30})\s+(?:do|doing|score|rank|marks|percentage|grade)",
        r"([a-z][a-z\s.]{1,30})\s+(?:rank|score|percentage|marks|grade|tips|improvement)",
    ]
    include_tips = bool(_re.search(r"\b(tip|tips|improve|improvement|help|advice|suggest|plan|weak|weak areas?)\b", q))

    for pat in patterns:
        m = _re.search(pat, q)
        if m:
            candidate = m.group(1).strip().title()
            # Make sure it's not a keyword
            if candidate.lower() in ("the", "a", "an", "all", "me", "my", "students", "student"):
                continue
            student_names = view_df["Student_Name"].dropna().tolist() if "Student_Name" in view_df.columns else []
            resolved = next((n for n in student_names if n.lower() == candidate.lower()), None)
            if not resolved:
                resolved = next((n for n in student_names if candidate.lower() in n.lower() or n.lower() in candidate.lower()), None)
            if resolved:
                return _build_student_profile_text(resolved, view_df, mapping, detain_threshold,
                                                   include_tips=include_tips)

    return None  # hand off to AI


def _local_fallback_parser(query: str, subjects: list) -> dict:
    """
    Lightweight, dependency-free intent guesser used in two situations:
      1. As an instant pre-pass so obviously-simple commands don't even need
         an API round trip.
      2. As a safety net if the AI call fails or returns malformed JSON, so
         the command bar still does *something* sensible instead of just
         erroring out.
    Never guesses at numbers — only at intent/scope/filters; pandas still
    does all the actual counting.
    """
    q = query.lower().strip()
    cmd = {
        "intent": "chart", "chart_type": "histogram", "subject": "ALL",
        "metric": None, "scope": "all", "n": None, "sort_order": "desc",
        "filters": {"class": None, "gender": None, "min_pct": None, "max_pct": None,
                    "student_name": None, "compare_names": None},
    }

    # subject detection
    for s in subjects:
        if s.lower() in q:
            cmd["subject"] = s
            break

    # numeric scope: "first N", "top N"
    m = _re.search(r"first\s+(\d+)", q)
    if m:
        cmd["scope"], cmd["n"] = "first_n", int(m.group(1))
    m = _re.search(r"top\s+(\d+)", q)
    if m:
        cmd["scope"], cmd["n"] = "top_n", int(m.group(1))

    # percentage thresholds: "above 80", "below 40", "between 40 and 60"
    m = _re.search(r"between\s+(\d+(?:\.\d+)?)\s*(?:and|-|to)\s*(\d+(?:\.\d+)?)", q)
    if m:
        cmd["filters"]["min_pct"], cmd["filters"]["max_pct"] = float(m.group(1)), float(m.group(2))
    else:
        m = _re.search(r"(?:above|over|more than|greater than)\s+(\d+(?:\.\d+)?)", q)
        if m:
            cmd["filters"]["min_pct"] = float(m.group(1))
        m = _re.search(r"(?:below|under|less than)\s+(\d+(?:\.\d+)?)", q)
        if m:
            cmd["filters"]["max_pct"] = float(m.group(1))

    # gender filter
    if _re.search(r" (girls?|female) ", q):
        cmd["filters"]["gender"] = "Female"
    elif _re.search(r" (boys?|male) ", q):
        cmd["filters"]["gender"] = "Male"

    # class filter, e.g. "class 10a", "section b"
    m = _re.search(r" (?:class|section)\s+([a-z0-9]+)", q)
    if m:
        cmd["filters"]["class"] = m.group(1).upper()

    # compare X and Y
    m = _re.search(r" compare\s+([a-z0-9][a-z0-9 .]{1,25})\s+(?:and|vs\.?|with)\s+([a-z0-9][a-z0-9 .]{1,25})", q)
    if m:
        cmd["intent"] = "compare"
        cmd["filters"]["compare_names"] = [m.group(1).strip().title(), m.group(2).strip().title()]

    # intent detection (skip if already set to compare above)
    if cmd["intent"] != "compare":
        if _re.search(r" how many | count | no\.? of | number of ", q):
            cmd["intent"] = "count"
            if _re.search(r"detain|detention|fail", q):
                cmd["metric"] = "detained"
            elif "pass" in q:
                cmd["metric"] = "pass"
        elif _re.search(r" average | avg | mean ", q):
            cmd["intent"] = "average"
        elif _re.search(r" rank | sort | order by ", q):
            cmd["intent"] = "rank"
            cmd["sort_order"] = "asc" if "ascend" in q or "lowest first" in q else "desc"
        elif _re.search(r" who | which student", q) or cmd["filters"]["min_pct"] or cmd["filters"]["max_pct"]                 or cmd["filters"]["gender"] or cmd["filters"]["class"]:
            cmd["intent"] = "table"
        elif _re.search(r" graph | chart | plot | visuali[sz]e | histogram | pie ", q):
            cmd["intent"] = "chart"
            if "pie" in q:
                cmd["chart_type"] = "pie_grade"
            elif "top" in q or "bar" in q:
                cmd["chart_type"] = "bar_top_n"

        # single-student lookup, e.g. "what did Ravi score" / "Ravi's percentage"
        m = _re.search(r"(?:what did|how did)\s+([a-z0-9][a-z0-9 .]{1,30}?)\s+(?:score|do|perform) ", q)
        if not m:
            m = _re.search(r"(?:score of|marks of|percentage of)\s+([a-z0-9][a-z0-9 .]{1,30})", q)
        if m:
            cmd["intent"] = "lookup"
            cmd["filters"]["student_name"] = m.group(1).strip().title()
        m = _re.search(r"^([a-z0-9][a-z0-9]{1,20})'s ", q)
        if m:
            cmd["intent"] = "lookup"
            cmd["filters"]["student_name"] = m.group(1).strip().title()

    return cmd


@st.cache_data(show_spinner=False, ttl=3600)
def parse_command_with_ai(query: str, subjects: list, xai_key: str) -> dict:
    """
    Ask the LLM to turn a free-text command into a small structured JSON
    object. We never let the LLM touch the actual numbers — it only
    classifies *intent*; all counting/filtering/charting below is done by
    plain pandas so the numbers are always exactly right. A regex-based
    local parser backs this up if the API call fails, so the command bar
    degrades gracefully instead of going silent.
    """
    schema_hint = """Return ONLY raw JSON (no markdown fences, no preamble) matching this schema:
{
  "intent": "chart" | "count" | "average" | "table" | "rank" | "compare" | "lookup",
  "chart_type": "histogram" | "bar_top_n" | "pie_grade" | "line" | null,
  "subject": "<one of the subject names, or 'ALL'>",
  "metric": "detained" | "pass" | "fail" | "score" | "highest" | "lowest" | null,
  "scope": "all" | "first_n" | "top_n",
  "n": <integer or null>,
  "sort_order": "asc" | "desc" | null,
  "filters": {
    "class": "<class/section name or null>",
    "gender": "Male" | "Female" | null,
    "min_pct": <number or null>,
    "max_pct": <number or null>,
    "student_name": "<a student's name mentioned by the user, or null>",
    "compare_names": ["<name1>", "<name2>"] | null
  }
}
Rules:
- "subject" must be exactly one of the given subject names, or "ALL" if the user means the whole class / all subjects combined.
- "first 40 students" / "first forty" -> scope "first_n", n 40.
- "top 10" -> scope "top_n", n 10.
- "how many detentions" / "how many failed" / "how many D" -> intent "count", metric "detained".
- "above 80%" -> filters.min_pct 80. "below 40" -> filters.max_pct 40. "between 40 and 60" -> both.
- "girls"/"female" -> filters.gender "Female"; "boys"/"male" -> filters.gender "Male".
- "class 10A" / "section B" -> filters.class.
- A specific student's name (e.g. "what did Ravi score", "Ravi's marks") -> intent "lookup", filters.student_name.
- "compare X and Y" -> intent "compare", filters.compare_names [X, Y].
- "rank"/"sort"/"order by" -> intent "rank", sort_order "asc" or "desc" (default "desc").
- if no chart/count/filter language is clearly present, default intent to "chart" with chart_type "histogram".
- Always include every key in the schema even if its value is null."""

    prompt = f"""Subjects available in this dataset: {subjects}

User command: "{query}"

{schema_hint}"""

    cmd = None
    try:
        client = Groq(api_key=xai_key)
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a precise JSON intent-parsing engine for an educational analytics dashboard. "
                        "Your ONLY job is to convert a natural-language command about student data into a single "
                        "valid JSON object. You NEVER add commentary, markdown fences, or explanation — output "
                        "raw JSON only. You are extremely accurate at detecting subject names, numeric thresholds, "
                        "gender filters, class filters, student names, and intents. When in doubt about a field, "
                        "use null. Never hallucinate subject names — only use names from the provided list."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            max_tokens=400,
            temperature=0,
        )
        raw = response.choices[0].message.content.strip()
        raw = raw.replace("```json", "").replace("```", "").strip()
        # Be tolerant of any stray preamble text before/after the JSON object.
        start, end = raw.find("{"), raw.rfind("}")
        if start != -1 and end != -1:
            raw = raw[start:end + 1]
        cmd = json.loads(raw)
    except Exception:
        # Fall back to the local regex parser rather than surfacing an error —
        # this keeps the command bar usable even without a working API key.
        cmd = _local_fallback_parser(query, subjects)

    return _validate_and_resolve_command(cmd, subjects)


def _validate_and_resolve_command(cmd: dict, subjects: list) -> dict:
    """Sanitise whatever the AI (or fallback parser) produced: fill in any
    missing keys with safe defaults and resolve fuzzy names against the
    real column names, so execute_command() never KeyErrors on a partial
    or slightly-off response."""
    if not isinstance(cmd, dict):
        return {"error": "Couldn't understand that command."}

    defaults = {
        "intent": "chart", "chart_type": "histogram", "subject": "ALL",
        "metric": None, "scope": "all", "n": None, "sort_order": "desc",
        "filters": {},
    }
    for k, v in defaults.items():
        cmd.setdefault(k, v)
    filt_defaults = {"class": None, "gender": None, "min_pct": None, "max_pct": None,
                      "student_name": None, "compare_names": None}
    if not isinstance(cmd.get("filters"), dict):
        cmd["filters"] = {}
    for k, v in filt_defaults.items():
        cmd["filters"].setdefault(k, v)

    # ── Resolve subject against the real column names (case-insensitive) ──
    subj = cmd.get("subject", "ALL") or "ALL"
    if subj != "ALL":
        match = next((s for s in subjects if s.lower() == str(subj).lower()), None)
        if not match:
            match = next((s for s in subjects if str(subj).lower() in s.lower() or s.lower() in str(subj).lower()), None)
        cmd["subject"] = match if match else "ALL"

    # clamp n to something sane so a misfired "top 99999" can't blow up a chart
    if cmd.get("n") is not None:
        try:
            cmd["n"] = max(1, min(int(cmd["n"]), 500))
        except (TypeError, ValueError):
            cmd["n"] = None

    return cmd


def _apply_filters(view_df: pd.DataFrame, filters: dict) -> pd.DataFrame:
    """Apply class/gender/percentage-range filters. All real pandas filtering —
    the AI only ever decides *which* filters apply, never the resulting count."""
    if not filters:
        return view_df
    out = view_df
    if filters.get("class") and "Class" in out.columns:
        out = out[out["Class"].astype(str).str.upper() == str(filters["class"]).upper()]
    if filters.get("gender") and "Gender" in out.columns:
        out = out[out["Gender"].astype(str).str.lower() == str(filters["gender"]).lower()]
    if filters.get("min_pct") is not None:
        out = out[out["Percentage"] >= float(filters["min_pct"])]
    if filters.get("max_pct") is not None:
        out = out[out["Percentage"] <= float(filters["max_pct"])]
    return out


def _find_student(view_df: pd.DataFrame, name: str):
    """Fuzzy (case-insensitive, partial) lookup of a student by name."""
    if not name or "Student_Name" not in view_df.columns:
        return view_df.iloc[0:0]
    exact = view_df[view_df["Student_Name"].astype(str).str.lower() == name.lower()]
    if not exact.empty:
        return exact
    return view_df[view_df["Student_Name"].astype(str).str.lower().str.contains(name.lower(), na=False)]


def execute_command(cmd: dict, df_raw: pd.DataFrame, mapping: dict, detain_threshold: float):
    """
    Deterministically execute a parsed command against the data.
    Returns (kind, payload) where kind is 'chart', 'text', 'table', or 'error'.
    """
    if "error" in cmd:
        return "error", cmd["error"]

    subject = cmd.get("subject", "ALL")
    scope   = cmd.get("scope", "all")
    n       = cmd.get("n")
    metric  = cmd.get("metric")
    intent  = cmd.get("intent", "chart")
    filters = cmd.get("filters", {}) or {}
    sort_order = cmd.get("sort_order", "desc")

    active_marks = [subject] if subject != "ALL" else mapping["marks"]
    view_df = prepare_data(df_raw, mapping, active_marks=active_marks, detain_threshold=detain_threshold)
    subject_label = subject if subject != "ALL" else "All Subjects (Combined)"

    # ── COMPARE intent: two named students, side by side ─────────────────
    if intent == "compare":
        names = filters.get("compare_names") or []
        if len(names) < 2:
            return "error", "Tell me two student names to compare, e.g. \"compare Ravi and Sita\"."
        rows = []
        for nm in names:
            match = _find_student(view_df, nm)
            if match.empty:
                return "error", f"Couldn't find a student matching '{nm}'."
            rows.append(match.iloc[0])
        cols = [c for c in ["Student_Name", "Student_ID", "Class", "Total_Marks", "Percentage", "Grade", "Detained"] if c in view_df.columns]
        cmp_df = pd.DataFrame([r[cols] for r in rows])
        return "table", cmp_df.reset_index(drop=True)

    # ── LOOKUP intent: a single named student ──────────────────────────
    if intent == "lookup":
        nm = filters.get("student_name")
        match = _find_student(view_df, nm)
        if match.empty:
            return "error", f"Couldn't find a student matching '{nm or ''}'."
        row = match.iloc[0]
        detained_txt = "Yes 🚫" if row.get("Detained") else "No ✅"
        return "text", (
            f"👤 **{row.get('Student_Name','N/A')}** — **{subject_label}**<br>"
            f"Total Marks: **{row.get('Total_Marks','N/A')}** &nbsp;|&nbsp; "
            f"Percentage: **{row.get('Percentage','N/A')}%** &nbsp;|&nbsp; "
            f"Grade: **{row.get('Grade','N/A')}** &nbsp;|&nbsp; Detained: **{detained_txt}**"
        )

    # ── Apply scope (which rows of students to look at) ───────────────────
    if scope == "first_n" and n:
        view_df = view_df.head(int(n))
        scope_label = f"first {n} students"
    elif scope == "top_n" and n:
        view_df = view_df.nlargest(int(n), "Total_Marks")
        scope_label = f"top {n} students"
    else:
        scope_label = "all students"

    # ── Apply class/gender/percentage filters ─────────────────────────────
    pre_filter_count = len(view_df)
    view_df = _apply_filters(view_df, filters)
    filt_bits = []
    if filters.get("class"):
        filt_bits.append(f"class {filters['class']}")
    if filters.get("gender"):
        filt_bits.append(filters["gender"].lower())
    if filters.get("min_pct") is not None:
        filt_bits.append(f"≥{filters['min_pct']}%")
    if filters.get("max_pct") is not None:
        filt_bits.append(f"≤{filters['max_pct']}%")
    if filt_bits:
        scope_label += " (" + ", ".join(filt_bits) + ")"

    if view_df.empty:
        return "error", f"No students match that scope/filter combination (started from {pre_filter_count} students)."

    # ── COUNT intents (e.g. "how many detentions in English") ─────────────
    if intent == "count":
        if metric == "detained" or metric == "fail":
            cnt = int(view_df["Detained"].sum())
            return "text", f"🚫 **{cnt}** student(s) are Detained in **{subject_label}** ({scope_label}, below {detain_threshold:.0f}%)."
        elif metric == "pass":
            cnt = int((~view_df["Detained"]).sum())
            return "text", f"✅ **{cnt}** student(s) passed **{subject_label}** ({scope_label})."
        else:
            return "text", f"There are **{len(view_df)}** student(s) in {scope_label} for **{subject_label}**."

    # ── AVERAGE intent ──────────────────────────────────────────────────
    if intent == "average":
        avg = round(view_df["Percentage"].mean(), 2)
        return "text", f"📈 Average percentage in **{subject_label}** ({scope_label}): **{avg}%**"

    # ── RANK intent: full sorted table ────────────────────────────────
    if intent == "rank":
        cols = [c for c in ["Student_Name", "Student_ID", "Total_Marks", "Percentage", "Grade", "Detained"] if c in view_df.columns]
        ascending = (sort_order == "asc")
        return "table", view_df[cols].sort_values("Percentage", ascending=ascending).reset_index(drop=True)

    # ── TABLE intent ──────────────────────────────────────────────────
    if intent == "table":
        cols = [c for c in ["Student_Name", "Student_ID", "Class", "Gender", "Total_Marks", "Percentage", "Grade", "Detained"] if c in view_df.columns]
        return "table", view_df[cols].sort_values("Percentage", ascending=False).reset_index(drop=True)

    # ── CHART intent ──────────────────────────────────────────────────
    chart_type = cmd.get("chart_type") or "histogram"
    title_suffix = f" — {subject_label} ({scope_label})"
    if chart_type == "pie_grade":
        fig = chart_grade_pie(view_df)
    elif chart_type == "bar_top_n":
        fig = chart_top_n_students(view_df, n or 10)
    else:
        fig = chart_score_distribution(view_df)
    fig.update_layout(title=fig.layout.title.text + title_suffix if fig.layout.title.text else title_suffix)
    return "chart", fig


