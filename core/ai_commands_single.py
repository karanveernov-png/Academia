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
import difflib
import textwrap
import pandas as pd
import numpy as np
import streamlit as st
from groq import Groq

from core.data_loader import prepare_data
from core.charts import chart_grade_pie, chart_top_n_students, chart_score_distribution


def _resolve_name(candidate: str, student_names: list, cutoff: float = 0.72):
    """
    Resolve a (possibly mistyped) name against the real roster. Tries, in
    order: exact match, substring match (either direction), then a
    typo-tolerant fuzzy match that forgives a missing/extra/swapped letter
    (e.g. 'Babta' / 'Shyana' / 'Babitaa' still resolve correctly).
    Returns the matched name, or None if nothing is close enough.
    """
    if not candidate or not student_names:
        return None
    cand = candidate.strip().lower()
    if not cand:
        return None
    for n in student_names:
        if n.lower() == cand:
            return n
    for n in student_names:
        if cand in n.lower() or n.lower() in cand:
            return n
    close = difflib.get_close_matches(cand, [n.lower() for n in student_names], n=1, cutoff=cutoff)
    if close:
        lower_names = [n.lower() for n in student_names]
        return student_names[lower_names.index(close[0])]
    return None


def _suggest_names(candidate: str, student_names: list, limit: int = 15) -> list:
    """
    Return up to `limit` student names most similar to `candidate`, used to
    give a friendly "did you mean…" list when no confident match is found.
    The count is dynamic — only names that are actually somewhat close are
    included, capped at `limit`, so a wildly off typo won't dump the entire
    class roster.
    """
    if not candidate or not student_names:
        return []
    cand = candidate.strip().lower()
    scored = [(n, difflib.SequenceMatcher(None, cand, n.lower()).ratio()) for n in student_names]
    scored = [s for s in scored if s[1] >= 0.4]
    scored.sort(key=lambda x: x[1], reverse=True)
    return [n for n, _ in scored[:limit]]


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
        suggestions = _suggest_names(student_name, view_df["Student_Name"].dropna().astype(str).tolist())
        if suggestions:
            return "error", f"Couldn't find a student matching '{student_name}'. Did you mean: {', '.join(suggestions)}?"
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


def _build_rank_target_text(student_name: str, target_rank: int, view_df: pd.DataFrame,
                              mapping: dict, detain_threshold: float) -> tuple:
    """
    Build a teacher-ready answer for "what does X need to do to reach rank N"
    style questions — shows the exact marks gap to the student currently
    holding that rank, plus weak-subject tips, all via plain pandas (no API
    call). Returns (kind, payload).
    """
    if "Student_Name" not in view_df.columns:
        return "error", "No student name column found."

    total_students = len(view_df)
    if target_rank < 1 or target_rank > total_students:
        return "error", f"Rank {target_rank} doesn't exist — this exam only has {total_students} students."

    ranked = view_df.sort_values("Percentage", ascending=False).reset_index(drop=True)
    match_idx = ranked.index[ranked["Student_Name"].astype(str).str.lower() == student_name.lower()]
    if len(match_idx) == 0:
        return "error", f"Couldn't find a student matching '{student_name}'."

    row = ranked.iloc[match_idx[0]]
    current_rank = int(match_idx[0]) + 1
    name  = row.get("Student_Name", "N/A")
    total = row.get("Total_Marks", 0)
    pct   = row.get("Percentage", 0)

    if current_rank <= target_rank:
        return "text", (
            f"🎉 **{name}** is already at **Rank #{current_rank}**, which is at or ahead of the "
            f"target Rank #{target_rank}! Total Marks: **{total}** ({pct}%)."
        )

    target_row = ranked.iloc[target_rank - 1]
    target_name = target_row.get("Student_Name", "N/A")
    gap = round(float(target_row.get("Total_Marks", 0)) - float(total), 2)

    lines = [
        f"## 🎯 {name} — Path to Rank #{target_rank}",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| 🏅 Current Rank | **#{current_rank} of {total_students}** |",
        f"| 📝 Current Marks | **{total}** ({pct}%) |",
        f"| 🚀 Marks Needed | **+{gap:.1f}** to overtake **{target_name}** (currently #{target_rank}) |",
    ]

    subject_cols = [c for c in (mapping.get("marks") or []) if c in view_df.columns]
    class_avgs   = {c: round(view_df[c].mean(), 2) for c in subject_cols}
    student_marks = {c: row.get(c) for c in subject_cols if pd.notna(row.get(c))}

    weak = []
    for c in subject_cols:
        sm = student_marks.get(c)
        ca = class_avgs.get(c, 0)
        if sm is None:
            continue
        diff = round(float(sm) - ca, 2)
        if diff < 0:
            weak.append((c, float(sm), ca, diff))
    weak.sort(key=lambda x: x[3])

    if weak:
        lines += ["", "### 🎯 Focus Areas", ""]
        for i, (subj, sm, ca, diff) in enumerate(weak[:3], 1):
            tip = _subject_tip(subj)
            lines.append(
                f"{i}. **{subj}** — scored {sm:.1f} vs class avg {ca:.1f} (gap: {diff:.1f}). 💡 {tip}"
            )
    else:
        lines += ["", f"✅ Already at or above class average in every subject — focus extra "
                       f"**+{gap:.1f} marks** on the strongest subject to close the gap fastest."]

    return "text", "\n".join(lines)


def _build_compare_text(name1: str, name2: str, view_df: pd.DataFrame, mapping: dict) -> tuple:
    """
    Build a rich, teacher-ready head-to-head comparison between two students.
    Covers: rank, percentile, marks, grade, risk, detained, subject breakdown,
    a subject-level performance gap bar, and a clear overall verdict.
    Returns (kind, payload).
    """
    if "Student_Name" not in view_df.columns:
        return "error", "No student name column found."

    row1_df = view_df[view_df["Student_Name"] == name1]
    row2_df = view_df[view_df["Student_Name"] == name2]
    if row1_df.empty or row2_df.empty:
        missing = name1 if row1_df.empty else name2
        return "error", f"Couldn't find a student matching '{missing}'."

    row1, row2 = row1_df.iloc[0], row2_df.iloc[0]
    total_students = len(view_df)
    ranked = view_df.sort_values("Percentage", ascending=False).reset_index(drop=True)
    rank1 = int(ranked[ranked["Student_Name"] == name1].index[0]) + 1
    rank2 = int(ranked[ranked["Student_Name"] == name2].index[0]) + 1
    pct1  = round(float(row1.get("Percentage", 0)), 2)
    pct2  = round(float(row2.get("Percentage", 0)), 2)
    tot1  = float(row1.get("Total_Marks", 0))
    tot2  = float(row2.get("Total_Marks", 0))

    # Percentile = % of class scoring below this student
    pctile1 = round((total_students - rank1) / max(total_students - 1, 1) * 100, 1)
    pctile2 = round((total_students - rank2) / max(total_students - 1, 1) * 100, 1)

    def w(v1, v2, higher_is_better=True):
        try:
            f1, f2 = float(v1), float(v2)
        except (TypeError, ValueError):
            return "", ""
        if f1 == f2:
            return "🤝 ", "🤝 "
        return ("🏆 ", "") if (f1 > f2) == higher_is_better else ("", "🏆 ")

    w1r, w2r = w(rank1, rank2, higher_is_better=False)
    w1t, w2t = w(tot1, tot2)
    w1p, w2p = w(pct1, pct2)

    lines = [
        f"## ⚖️ Head-to-Head: {name1} vs {name2}",
        "",
        f"| Metric | {name1} | {name2} |",
        "|---|---|---|",
        f"| 🏅 Class Rank | {w1r}**#{rank1}** of {total_students} | {w2r}**#{rank2}** of {total_students} |",
        f"| 📈 Percentile | {w1r}**{pctile1}th** | {w2r}**{pctile2}th** |",
        f"| 📝 Total Marks | {w1t}**{tot1:.0f}** | {w2t}**{tot2:.0f}** |",
        f"| 📊 Percentage | {w1p}**{pct1}%** | {w2p}**{pct2}%** |",
        f"| 🎓 Grade | **{row1.get('Grade','N/A')}** | **{row2.get('Grade','N/A')}** |",
        f"| ⚠️ Risk | **{row1.get('Risk','N/A')}** | **{row2.get('Risk','N/A')}** |",
        f"| 🚫 Detained | {'Yes' if row1.get('Detained') else 'No'} | {'Yes' if row2.get('Detained') else 'No'} |",
    ]

    # Subject-wise breakdown with a visual ascii gap bar
    subject_cols = [c for c in (mapping.get("marks") or []) if c in view_df.columns]
    valid_subjects = [c for c in subject_cols if pd.notna(row1.get(c)) and pd.notna(row2.get(c))]
    if valid_subjects:
        lines += ["", "### 📚 Subject Breakdown", ""]
        lines.append(f"| Subject | {name1} | {name2} | Winner |")
        lines.append("|---|---|---|---|")
        s1_wins, s2_wins, ties = 0, 0, 0
        for c in valid_subjects:
            v1, v2 = float(row1.get(c, 0)), float(row2.get(c, 0))
            class_avg = round(view_df[c].mean(), 1)
            if v1 > v2:
                winner = f"🏆 {name1.split()[0]}"
                s1_wins += 1
            elif v2 > v1:
                winner = f"🏆 {name2.split()[0]}"
                s2_wins += 1
            else:
                winner = "🤝 Tie"
                ties += 1
            lines.append(f"| {c} | **{v1:.0f}** _(avg {class_avg})_ | **{v2:.0f}** _(avg {class_avg})_ | {winner} |")

        lines += [
            "",
            f"**Subject wins →** {name1.split()[0]}: {s1_wins} &nbsp;|&nbsp; "
            f"{name2.split()[0]}: {s2_wins} &nbsp;|&nbsp; Ties: {ties}",
        ]

    # Overall verdict
    gap = round(abs(tot1 - tot2), 1)
    lines.append("")
    if gap == 0:
        lines.append(f"### 🤝 Verdict: **{name1}** and **{name2}** are perfectly tied — {tot1:.0f} marks each.")
    else:
        leader = name1 if tot1 > tot2 else name2
        trailer = name2 if tot1 > tot2 else name1
        trailer_pct = pct2 if tot1 > tot2 else pct1
        trailer_rank = rank2 if tot1 > tot2 else rank1
        lines.append(
            f"### 🏆 Verdict: **{leader}** leads by **{gap} marks** overall.\n"
            f"> {trailer} needs **+{gap:.0f} marks** to catch up "
            f"(currently Rank #{trailer_rank}, {trailer_pct}%)."
        )

    return "text", "\n".join(lines)


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

    # ── Compare two students ──────────────────────────────────────────────
    # Covers: "compare X and Y", "X vs Y", "X vs. Y", "X against Y",
    # "difference between X and Y", "who is better X or Y", "X or Y who is better"
    _compare_patterns = [
        r"\bcompare\s+([a-z][a-z\s.]{1,30})\s+(?:and|vs\.?|with|against)\s+([a-z][a-z\s.]{1,30})",
        r"\bdifference\s+between\s+([a-z][a-z\s.]{1,30})\s+and\s+([a-z][a-z\s.]{1,30})",
        r"\bwho\s+is\s+better\s+([a-z][a-z\s.]{1,30})\s+or\s+([a-z][a-z\s.]{1,30})",
        r"([a-z][a-z\s.]{1,30})\s+or\s+([a-z][a-z\s.]{1,30})\s+who\s+is\s+better",
        r"([a-z][a-z\s.]{1,20})\s+vs\.?\s+([a-z][a-z\s.]{1,20})",
        r"([a-z][a-z\s.]{1,20})\s+against\s+([a-z][a-z\s.]{1,20})",
    ]
    student_names_list = view_df["Student_Name"].dropna().astype(str).tolist() if "Student_Name" in view_df.columns else []

    for _cpat in _compare_patterns:
        compare_m = _re.search(_cpat, q)
        if compare_m:
            n1_raw = compare_m.group(1).strip().title()
            n2_raw = compare_m.group(2).strip().title()
            # Verify at least one name is a real student before treating this
            # as a compare (avoids false positives like "A vs B" on other queries)
            r1 = _resolve_name(n1_raw, student_names_list)
            r2 = _resolve_name(n2_raw, student_names_list)
            if r1 or r2:  # at least one matched — treat as compare intent
                if not r1:
                    suggestions = _suggest_names(n1_raw, student_names_list, limit=15)
                    msg = f"Couldn't find **'{n1_raw}'**."
                    if suggestions:
                        msg += f"\n\nDid you mean: {', '.join(suggestions[:8])}?"
                    return "error", msg
                if not r2:
                    suggestions = _suggest_names(n2_raw, student_names_list, limit=15)
                    msg = f"Couldn't find **'{n2_raw}'**."
                    if suggestions:
                        msg += f"\n\nDid you mean: {', '.join(suggestions[:8])}?"
                    return "error", msg
                return _build_compare_text(r1, r2, view_df, mapping)
            break  # pattern matched but neither name found → fall through to AI

    # ── "lowest scorer" / "who failed most" ──
    if _re.search(r"\b(lowest\s+scorer|worst\s+student|bottom\s+student|who\s+failed|least\s+marks)\b", q):
        bot_row = view_df.loc[view_df["Percentage"].idxmin()]
        name = bot_row.get("Student_Name", "N/A")
        return _build_student_profile_text(name, view_df, mapping, detain_threshold, include_tips=True)

    # ── "what does/should <name> need to do to reach/get rank N" / "how does
    # <name> rank up to top N" / and similar "advice toward a target rank"
    # phrasings. Handled BEFORE the generic patterns below because otherwise
    # this kind of sentence gets mis-parsed as a plain "sort by rank" command
    # and dumps the full class table instead of answering the actual question.
    target_rank_m = _re.search(r"(?:rank\s*#?\s*|top\s*-?\s*)(\d+)\b", q)
    has_goal_words = bool(_re.search(
        r"\b(need|needs|do|does|should|reach|achieve|become|get|climb|improve|up|tips|advice|plan)\b", q))
    no_chart_words = not _re.search(r"\b(chart|graph|plot|visuali[sz]e|histogram|pie)\b", q)

    if target_rank_m and has_goal_words and no_chart_words:
        target_rank = int(target_rank_m.group(1))
        student_names = view_df["Student_Name"].dropna().tolist() if "Student_Name" in view_df.columns else []

        # 1) Look for any *real* student's full name mentioned anywhere in the
        #    query (longest names first, so "Anish Kumar" wins over a partial
        #    first-name-only collision).
        found_name = None
        for n in sorted(student_names, key=len, reverse=True):
            if _re.search(r"\b" + _re.escape(n.lower()) + r"\b", q):
                found_name = n
                break
        if not found_name:
            for n in student_names:
                first_tok = n.lower().split()[0]
                if len(first_tok) >= 3 and _re.search(r"\b" + _re.escape(first_tok) + r"\b", q):
                    found_name = n
                    break
        if not found_name:
            # 1b) typo-tolerant fuzzy pass over individual query words/word
            #     pairs (catches a missing/extra/swapped letter, e.g. typing
            #     "Babta" or "Shyana" instead of "Babita" / "Shayana").
            q_tokens = _re.findall(r"[a-z]+", q)
            candidate_tokens = [t for t in q_tokens if len(t) >= 3] + \
                                [f"{a} {b}" for a, b in zip(q_tokens, q_tokens[1:])]
            best, best_score = None, 0.0
            for tok in candidate_tokens:
                for n in student_names:
                    score = difflib.SequenceMatcher(None, tok, n.lower()).ratio()
                    if score > best_score:
                        best_score, best = score, n
            if best and best_score >= 0.75:
                found_name = best

        if found_name:
            return _build_rank_target_text(found_name, target_rank, view_df, mapping, detain_threshold)

        # 2) No real student matched — if the sentence clearly *names*
        #    someone (even if that person isn't an actual student in this
        #    exam), say so explicitly instead of silently falling through to
        #    a generic/irrelevant table.
        name_guess_m = _re.search(
            r"(?:what|how)\s+(?:does|do|should|can|would)?\s*([a-z]+(?:\s+[a-z]+){0,2}?)\s+"
            r"(?:needs?|do|does|get|reach|achieve|become|rank|climb|improve)\b", q
        )
        if name_guess_m:
            guess = name_guess_m.group(1).strip().title()
            if guess.lower() not in ("i", "you", "we", "they", "the", "a", "an", "my", "me", "he", "she"):
                suggestions = _suggest_names(guess, student_names)
                if suggestions:
                    return "error", (f"Couldn't find a student named '{guess}' in this exam's data. "
                                      f"Did you mean: {', '.join(suggestions)}?")
                return "error", (f"Couldn't find a student named '{guess}' in this exam's data. "
                                  f"Double-check the spelling, or try their full name as it appears in the sheet.")

    # ── Student-specific queries: rank / tips / profile / improvement ──
    patterns = [
        r"(?:rank\s+of|rank\s+for)\s+([a-z][a-z\s.]{1,30})",
        r"([a-z][a-z\s.]{1,30})[''`]?s\s+rank",
        r"(?:tips\s+for|improve(?:ment)?(?:\s+for)?|how\s+(?:can|should|to\s+help))\s+([a-z][a-z\s.]{1,30})",
        r"(?:profile\s+of|show\s+me|tell\s+me\s+about|details\s+of|info(?:rmation)?\s+(?:on|about))\s+([a-z][a-z\s.]{1,30})",
        r"(?:what\s+(?:is|are|should|can)\s+)([a-z][a-z\s.]{1,30})\s+(?:do|doing|score|rank|marks|percentage|grade)",
        r"([a-z]+(?:\s+[a-z]+){0,2})\s+(?:rank|score|percentage|marks|grade|tips|improvement)",
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
    m = _re.search(r"\bcompare\s+([a-z0-9][a-z0-9 .]{1,25})\s+(?:and|vs\.?|with)\s+([a-z0-9][a-z0-9 .]{1,25})", q)
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
    """Typo-tolerant lookup of a student by name (exact -> substring -> fuzzy)."""
    if not name or "Student_Name" not in view_df.columns:
        return view_df.iloc[0:0]
    student_names = view_df["Student_Name"].dropna().astype(str).tolist()
    resolved = _resolve_name(name, student_names)
    if resolved is None:
        return view_df.iloc[0:0]
    return view_df[view_df["Student_Name"].astype(str) == resolved]


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
        student_names = view_df["Student_Name"].dropna().astype(str).tolist() if "Student_Name" in view_df.columns else []
        resolved_names = []
        for nm in names[:2]:
            resolved = _resolve_name(nm, student_names)
            if not resolved:
                suggestions = _suggest_names(nm, student_names)
                if suggestions:
                    return "error", f"Couldn't find a student matching '{nm}'. Did you mean: {', '.join(suggestions)}?"
                return "error", f"Couldn't find a student matching '{nm}'."
            resolved_names.append(resolved)
        return _build_compare_text(resolved_names[0], resolved_names[1], view_df, mapping)

    # ── LOOKUP intent: a single named student ──────────────────────────
    if intent == "lookup":
        nm = filters.get("student_name")
        student_names = view_df["Student_Name"].dropna().astype(str).tolist() if "Student_Name" in view_df.columns else []
        resolved = _resolve_name(nm, student_names) if nm else None
        if not resolved:
            suggestions = _suggest_names(nm or "", student_names)
            if suggestions:
                return "error", f"Couldn't find a student matching '{nm or ''}'. Did you mean: {', '.join(suggestions)}?"
            return "error", f"Couldn't find a student matching '{nm or ''}'."
        match = view_df[view_df["Student_Name"] == resolved]
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


