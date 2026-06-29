"""
core.cross_exam
================
All logic for the cross-exam Compare Mode:
  • build_merged_dataset()          — merge multiple exam DataFrames on name/ID
  • _cross_exam_local_shortcut()   — zero-API-call answers for common questions
  • parse_cross_exam_command_with_ai() — Groq LLM intent parser for cross-exam NL queries
  • execute_cross_exam_command()   — deterministic pandas executor for parsed commands

AI command examples that work:
  "who improved from MST1 to MST2"
  "show rank comparison"
  "top 10 leaderboard"
  "who is detained in both"
  "Ravi's progress"
  "compare Ravi and Sita"
  "most improved student"
  "who dropped the most"
  "class average each exam"
  "students above 80% in MST2"
"""
import re
import json
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st
try:
    from groq import Groq
except ImportError:
    Groq = None

from core.config import ACCENT_SEQ, CHART_BG, CHART_FONT, GRID_COLOR, TITLE_FONT


# ─────────────────────────────────────────────────────────────────────────────
# 1.  BUILD MERGED DATASET
# ─────────────────────────────────────────────────────────────────────────────

def build_merged_dataset(exam_results: dict):
    """
    Merge processed DataFrames from multiple exams on Student_Name (and
    Student_ID when available).  Returns (merged_df, exam_subjects_dict).

    exam_results format (built in app.py):
        { label: { "df": df, "mapping": mapping, "kpis": kpis,
                   "detain_threshold": float } }

    merged_df columns:  Student_Name, [Student_ID], LABEL__Percentage,
                        LABEL__Total_Marks, LABEL__Grade, LABEL__Detained,
                        LABEL__<subj>, ...
    exam_subjects_dict: { label: [subject_col, ...] }
    """
    labels = list(exam_results.keys())
    exam_subjects = {}
    per_exam = []

    for label in labels:
        info   = exam_results[label]
        df     = info["df"].copy()
        mapping = info.get("mapping", {})

        # Normalise key columns
        if "Student_Name" not in df.columns:
            continue
        df["Student_Name"] = df["Student_Name"].astype(str).str.strip().str.title()

        subjs = mapping.get("marks", [])
        exam_subjects[label] = subjs

        # Prefix every non-key column with label__
        rename = {}
        for col in df.columns:
            if col not in ("Student_Name", "Student_ID"):
                rename[col] = f"{label}__{col}"
        df = df.rename(columns=rename)
        per_exam.append(df)

    if not per_exam:
        return None, {}

    # Merge on Student_Name (outer so we see all students)
    merged = per_exam[0]
    for df_r in per_exam[1:]:
        on_cols = ["Student_Name"]
        if "Student_ID" in merged.columns and "Student_ID" in df_r.columns:
            on_cols.append("Student_ID")
        merged = pd.merge(merged, df_r, on=on_cols, how="outer")

    merged = merged.reset_index(drop=True)
    return merged, exam_subjects


# ─────────────────────────────────────────────────────────────────────────────
# 2.  LOCAL SHORTCUT — zero API calls
# ─────────────────────────────────────────────────────────────────────────────

def _cross_exam_local_shortcut(query: str, merged: pd.DataFrame,
                                exam_subjects: dict, exam_results: dict):
    """
    Handle the most common cross-exam questions without any API call.
    Returns (kind, payload) or None to fall through to AI.
    """
    q = query.lower().strip()
    labels = list(exam_subjects.keys())
    pct_cols = [f"{l}__Percentage" for l in labels if f"{l}__Percentage" in merged.columns]

    # ── helpers ──────────────────────────────────────────────────────────
    def _pct_valid(df):
        """Drop rows where ALL pct cols are NaN."""
        return df.dropna(subset=pct_cols, how="all") if pct_cols else df

    def _add_avg_col(df):
        valid = _pct_valid(df.copy())
        valid["Avg_%"] = valid[pct_cols].mean(axis=1).round(2)
        return valid

    # ── TOPPER / top-N leaderboard ────────────────────────────────────
    top_m = re.search(r"top[\s-]*(\d+)|leaderboard|ranklist|rank list", q)
    if top_m or re.search(r"\btopper\b|\bbest student\b|\bhighest scorer\b", q):
        n = int(top_m.group(1)) if (top_m and top_m.group(1)) else 10
        df = _add_avg_col(merged)
        show = df.nlargest(n, "Avg_%")[["Student_Name"] + pct_cols + ["Avg_%"]].reset_index(drop=True)
        show.index += 1
        return "table", show

    # ── MOST IMPROVED ─────────────────────────────────────────────────
    if re.search(r"most.improved|biggest.gain|most.progress|rose.most", q):
        if len(pct_cols) < 2:
            return "text", "Need at least 2 exams to find improvements."
        df = _pct_valid(merged.copy())
        df["Improvement"] = (df[pct_cols[-1]] - df[pct_cols[0]]).round(2)
        best = df.nlargest(10, "Improvement")[["Student_Name"] + pct_cols + ["Improvement"]].reset_index(drop=True)
        best.index += 1
        return "table", best

    # ── DROPPED / DECLINED ────────────────────────────────────────────
    if re.search(r"drop|declin|fell|worst.fall|most.fall|biggest.drop", q):
        if len(pct_cols) < 2:
            return "text", "Need at least 2 exams to find drops."
        df = _pct_valid(merged.copy())
        df["Drop"] = (df[pct_cols[0]] - df[pct_cols[-1]]).round(2)
        worst = df.nlargest(10, "Drop")[["Student_Name"] + pct_cols + ["Drop"]].reset_index(drop=True)
        worst.index += 1
        return "table", worst

    # ── IMPROVED (any improvement) ────────────────────────────────────
    if re.search(r"\bimproved\b|\bwho.improved\b|\bprogress\b", q):
        if len(pct_cols) < 2:
            return "text", "Need at least 2 exams."
        df = _pct_valid(merged.copy())
        df["Δ%"] = (df[pct_cols[-1]] - df[pct_cols[0]]).round(2)
        improved = df[df["Δ%"] > 0][["Student_Name"] + pct_cols + ["Δ%"]].sort_values("Δ%", ascending=False).reset_index(drop=True)
        improved.index += 1
        return "table", improved

    # ── DETAINED IN ALL ───────────────────────────────────────────────
    if re.search(r"detained.in.both|detained.in.all|consistently.detained|always.detained", q):
        det_cols = [f"{l}__Detained" for l in labels if f"{l}__Detained" in merged.columns]
        if not det_cols:
            return "text", "No detained data found."
        df = merged[merged[det_cols].fillna(False).all(axis=1)]
        show = df[["Student_Name"] + pct_cols + det_cols].reset_index(drop=True)
        if show.empty:
            return "text", "🎉 No students are detained in ALL exams!"
        return "table", show

    # ── CLASS AVERAGE COMPARISON ──────────────────────────────────────
    if re.search(r"class.avg|average.each|avg.per.exam|overall.average", q):
        avgs = {l: round(merged[f"{l}__Percentage"].mean(), 2)
                for l in labels if f"{l}__Percentage" in merged.columns}
        fig = go.Figure(go.Bar(
            x=list(avgs.keys()), y=list(avgs.values()),
            marker_color=ACCENT_SEQ[:len(avgs)],
            text=[f"{v:.1f}%" for v in avgs.values()],
            textposition="outside"
        ))
        fig.update_layout(
            title="Class Average % — Exam Comparison",
            paper_bgcolor=CHART_BG, plot_bgcolor=CHART_BG,
            font_color=CHART_FONT, title_font_color=TITLE_FONT,
            yaxis=dict(range=[0, 110], gridcolor=GRID_COLOR),
            xaxis=dict(gridcolor=GRID_COLOR),
        )
        return "chart", fig

    # ── RANK COMPARISON CHART ─────────────────────────────────────────
    if re.search(r"rank.comparison|rank.chart|rank.graph|show.rank", q):
        if len(pct_cols) < 2:
            return "text", "Need at least 2 exams."
        df = _add_avg_col(merged).nlargest(20, "Avg_%")
        fig = go.Figure()
        colors = ACCENT_SEQ
        for i, col in enumerate(pct_cols):
            label_name = col.replace("__Percentage", "")
            fig.add_trace(go.Bar(
                name=label_name, x=df["Student_Name"], y=df[col],
                marker_color=colors[i % len(colors)]
            ))
        fig.update_layout(
            barmode="group", title="Rank Comparison — Top 20 Students",
            paper_bgcolor=CHART_BG, plot_bgcolor=CHART_BG,
            font_color=CHART_FONT, title_font_color=TITLE_FONT,
            yaxis=dict(gridcolor=GRID_COLOR), xaxis=dict(gridcolor=GRID_COLOR),
            legend=dict(bgcolor="rgba(0,0,0,0)", font_color=CHART_FONT),
        )
        return "chart", fig

    # ── PROGRESS LINE CHART (all students) ───────────────────────────
    if re.search(r"progress.chart|line.chart|trend|trajectory|show.progress", q):
        if len(pct_cols) < 2:
            return "text", "Need at least 2 exams to draw a trend."
        df = _pct_valid(merged).head(30)
        fig = go.Figure()
        x_labels = [c.replace("__Percentage", "") for c in pct_cols]
        for _, row in df.iterrows():
            ys = [row.get(c) for c in pct_cols]
            if any(pd.notna(y) for y in ys):
                fig.add_trace(go.Scatter(
                    x=x_labels, y=ys, mode="lines+markers",
                    name=str(row["Student_Name"]),
                    line=dict(width=1.5),
                    marker=dict(size=6),
                ))
        fig.update_layout(
            title="Student Progress Across Exams",
            paper_bgcolor=CHART_BG, plot_bgcolor=CHART_BG,
            font_color=CHART_FONT, title_font_color=TITLE_FONT,
            showlegend=len(df) <= 15,
            yaxis=dict(range=[0, 110], gridcolor=GRID_COLOR),
            xaxis=dict(gridcolor=GRID_COLOR),
        )
        return "chart", fig

    # ── SINGLE STUDENT PROFILE ────────────────────────────────────────
    # "Ravi's progress" / "profile of Anjali" / "how did Rahul do"
    name_m = re.search(
        r"(?:profile of|progress of|how did|how is|tips for|rank of|marks of|"
        r"score of|what did|how to improve)\s+([a-z][a-z .]{1,28})|"
        r"([a-z][a-z]{2,20})'s\s+(?:progress|rank|profile|marks|score|performance)",
        q
    )
    if name_m:
        raw_name = (name_m.group(1) or name_m.group(2) or "").strip().title()
        if raw_name:
            return _single_student_cross_profile(raw_name, merged, labels, pct_cols, exam_results)

    # ── STUDENTS ABOVE / BELOW threshold in a specific exam ──────────
    above_m = re.search(r"above\s+(\d+)\s*%?\s+in\s+(\w[\w\s]*)", q)
    below_m = re.search(r"below\s+(\d+)\s*%?\s+in\s+(\w[\w\s]*)", q)
    for m, op in [(above_m, "above"), (below_m, "below")]:
        if m:
            threshold = float(m.group(1))
            exam_hint = m.group(2).strip().title()
            # find matching exam label
            target_col = next(
                (f"{l}__Percentage" for l in labels if exam_hint.lower() in l.lower()),
                pct_cols[-1] if pct_cols else None
            )
            if target_col:
                filtered = merged[
                    merged[target_col] >= threshold if op == "above"
                    else merged[target_col] < threshold
                ][["Student_Name"] + pct_cols].dropna(subset=[target_col]).reset_index(drop=True)
                filtered.index += 1
                return "table", filtered

    return None   # fall through to AI


def _single_student_cross_profile(name: str, merged: pd.DataFrame,
                                   labels: list, pct_cols: list,
                                   exam_results: dict):
    """Generate a rich multi-exam profile for one student."""
    mask = merged["Student_Name"].astype(str).str.lower().str.contains(name.lower(), na=False)
    rows = merged[mask]
    if rows.empty:
        return "text", f"Couldn't find a student matching '{name}'. Try checking the spelling."
    row = rows.iloc[0]
    actual_name = row["Student_Name"]

    lines = [f"## 👤 {actual_name} — Cross-Exam Profile", ""]
    lines += ["| Exam | Percentage | Grade | Detained |",
              "|------|-----------|-------|---------|"]

    prev_pct = None
    for label in labels:
        pct_col  = f"{label}__Percentage"
        grd_col  = f"{label}__Grade"
        det_col  = f"{label}__Detained"
        pct  = row.get(pct_col)
        grd  = row.get(grd_col, "—")
        det  = "🚫 Yes" if row.get(det_col) else "✅ No"
        arrow = ""
        if prev_pct is not None and pd.notna(pct):
            diff = float(pct) - float(prev_pct)
            arrow = f" (🔺+{diff:.1f})" if diff > 0 else f" (🔻{diff:.1f})"
        pct_str = f"{pct:.1f}%{arrow}" if pd.notna(pct) else "—"
        lines.append(f"| {label} | **{pct_str}** | {grd} | {det} |")
        if pd.notna(pct):
            prev_pct = float(pct)

    # Per-exam rank
    lines += ["", "### 🏅 Rank per Exam", ""]
    for label in labels:
        pct_col = f"{label}__Percentage"
        if pct_col not in merged.columns:
            continue
        sub = merged[[pct_col]].dropna()
        my_pct = row.get(pct_col)
        if pd.notna(my_pct):
            rank = int((sub[pct_col] > float(my_pct)).sum()) + 1
            total = len(sub)
            lines.append(f"- **{label}**: Rank #{rank} of {total}")

    # Trend summary
    valid_pcts = [float(row[c]) for c in pct_cols if pd.notna(row.get(c))]
    if len(valid_pcts) >= 2:
        delta = valid_pcts[-1] - valid_pcts[0]
        trend = "📈 improving" if delta > 1 else ("📉 declining" if delta < -1 else "➡️ stable")
        lines += ["", f"### 📊 Trend: {trend}",
                  f"Overall change from first to last exam: **{delta:+.1f}%**"]

        # Personalised advice
        lines += ["", "### 🎯 Advice"]
        if delta > 5:
            lines.append("Great upward trend! Consistency is key — keep up the study rhythm.")
        elif delta < -5:
            lines.append("Performance is declining. Recommend reviewing weak subjects and increasing practice frequency.")
        else:
            lines.append("Performance is stable. To move to the next grade, focus on the subject with the largest gap to class average.")

    return "text", "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# 3.  AI PARSER
# ─────────────────────────────────────────────────────────────────────────────

_CROSS_SCHEMA = """\
Return ONLY raw JSON (no markdown, no preamble) matching this schema:
{
  "intent": "leaderboard" | "improved" | "dropped" | "detained_all" | "avg_comparison"
            | "rank_comparison" | "progress_chart" | "student_profile" | "filter_table"
            | "compare_two" | "count",
  "n": <integer or null>,
  "student_name": "<name or null>",
  "compare_names": ["<name1>", "<name2>"] | null,
  "exam_label": "<which exam label the user mentioned, or null>",
  "threshold": <number or null>,
  "direction": "above" | "below" | null,
  "metric": "percentage" | "detained" | "improved" | null
}
Rules:
- "top 10 leaderboard" → intent leaderboard, n 10
- "who improved" → intent improved
- "who dropped" → intent dropped
- "detained in both/all" → intent detained_all
- "class average" / "avg comparison" → intent avg_comparison
- "rank comparison" / "rank chart" → intent rank_comparison
- "progress chart" / "trend" → intent progress_chart
- "Ravi's progress" / "profile of Anjali" → intent student_profile, student_name
- "compare Ravi and Sita" → intent compare_two, compare_names
- "students above 80% in MST2" → intent filter_table, threshold 80, direction above, exam_label MST2
- Always include all keys even if null."""


@st.cache_data(show_spinner=False, ttl=3600)
def parse_cross_exam_command_with_ai(query: str, exam_subjects: dict, xai_key: str) -> dict:
    """Parse a cross-exam NL command with the Groq LLM, falling back gracefully."""
    labels = list(exam_subjects.keys())
    subject_info = {lbl: exam_subjects[lbl] for lbl in labels}

    prompt = (
        f"Exams available: {labels}\n"
        f"Subjects per exam: {subject_info}\n"
        f"User command: \"{query}\"\n\n"
        f"{_CROSS_SCHEMA}"
    )

    defaults = {
        "intent": "leaderboard", "n": None, "student_name": None,
        "compare_names": None, "exam_label": None,
        "threshold": None, "direction": None, "metric": None,
    }

    if not xai_key or Groq is None:
        return defaults

    try:
        client = Groq(api_key=xai_key)
        resp = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a JSON intent parser for a multi-exam educational analytics tool. "
                        "Output ONLY a single valid JSON object — no markdown, no explanation."
                    )
                },
                {"role": "user", "content": prompt},
            ],
            max_tokens=300,
            temperature=0,
        )
        raw = resp.choices[0].message.content.strip()
        raw = raw.replace("```json", "").replace("```", "").strip()
        s, e = raw.find("{"), raw.rfind("}")
        if s != -1 and e != -1:
            raw = raw[s:e+1]
        cmd = json.loads(raw)
        for k, v in defaults.items():
            cmd.setdefault(k, v)
        return cmd
    except Exception:
        return defaults


# ─────────────────────────────────────────────────────────────────────────────
# 4.  EXECUTOR
# ─────────────────────────────────────────────────────────────────────────────

def execute_cross_exam_command(cmd: dict, merged: pd.DataFrame, exam_subjects: dict):
    """
    Turn a parsed command into (kind, payload).
    kind ∈ {'chart', 'table', 'text', 'error'}
    """
    labels    = list(exam_subjects.keys())
    pct_cols  = [f"{l}__Percentage" for l in labels if f"{l}__Percentage" in merged.columns]
    det_cols  = [f"{l}__Detained"   for l in labels if f"{l}__Detained"   in merged.columns]

    intent = cmd.get("intent", "leaderboard")
    n      = cmd.get("n") or 10

    def _valid(df):
        return df.dropna(subset=pct_cols, how="all") if pct_cols else df

    def _avg_col(df):
        df = _valid(df.copy())
        df["Avg_%"] = df[pct_cols].mean(axis=1).round(2)
        return df

    # ── Leaderboard ───────────────────────────────────────────────────
    if intent == "leaderboard":
        df = _avg_col(merged).nlargest(n, "Avg_%")[["Student_Name"] + pct_cols + ["Avg_%"]].reset_index(drop=True)
        df.index += 1
        return "table", df

    # ── Improved ──────────────────────────────────────────────────────
    if intent == "improved":
        if len(pct_cols) < 2:
            return "text", "Need at least 2 exams."
        df = _valid(merged.copy())
        df["Δ%"] = (df[pct_cols[-1]] - df[pct_cols[0]]).round(2)
        out = df[df["Δ%"] > 0][["Student_Name"] + pct_cols + ["Δ%"]].sort_values("Δ%", ascending=False).reset_index(drop=True)
        out.index += 1
        return "table", out

    # ── Dropped ───────────────────────────────────────────────────────
    if intent == "dropped":
        if len(pct_cols) < 2:
            return "text", "Need at least 2 exams."
        df = _valid(merged.copy())
        df["Drop"] = (df[pct_cols[0]] - df[pct_cols[-1]]).round(2)
        out = df[df["Drop"] > 0][["Student_Name"] + pct_cols + ["Drop"]].sort_values("Drop", ascending=False).reset_index(drop=True)
        out.index += 1
        return "table", out

    # ── Detained in all ───────────────────────────────────────────────
    if intent == "detained_all":
        if not det_cols:
            return "text", "No detention data found."
        df = merged[merged[det_cols].fillna(False).all(axis=1)][["Student_Name"] + pct_cols].reset_index(drop=True)
        if df.empty:
            return "text", "🎉 No students are detained in ALL exams!"
        return "table", df

    # ── Average comparison chart ───────────────────────────────────────
    if intent == "avg_comparison":
        avgs = {l: round(merged[f"{l}__Percentage"].mean(), 2)
                for l in labels if f"{l}__Percentage" in merged.columns}
        fig = go.Figure(go.Bar(
            x=list(avgs.keys()), y=list(avgs.values()),
            marker_color=ACCENT_SEQ[:len(avgs)],
            text=[f"{v:.1f}%" for v in avgs.values()], textposition="outside"
        ))
        fig.update_layout(
            title="Class Average % — Per Exam",
            paper_bgcolor=CHART_BG, plot_bgcolor=CHART_BG,
            font_color=CHART_FONT, title_font_color=TITLE_FONT,
            yaxis=dict(range=[0, 110], gridcolor=GRID_COLOR),
            xaxis=dict(gridcolor=GRID_COLOR),
        )
        return "chart", fig

    # ── Rank comparison chart ─────────────────────────────────────────
    if intent == "rank_comparison":
        df = _avg_col(merged).nlargest(n, "Avg_%")
        fig = go.Figure()
        for i, col in enumerate(pct_cols):
            lbl = col.replace("__Percentage", "")
            fig.add_trace(go.Bar(name=lbl, x=df["Student_Name"], y=df[col],
                                  marker_color=ACCENT_SEQ[i % len(ACCENT_SEQ)]))
        fig.update_layout(
            barmode="group", title=f"Rank Comparison — Top {n} Students",
            paper_bgcolor=CHART_BG, plot_bgcolor=CHART_BG,
            font_color=CHART_FONT, title_font_color=TITLE_FONT,
            yaxis=dict(gridcolor=GRID_COLOR), xaxis=dict(gridcolor=GRID_COLOR),
            legend=dict(bgcolor="rgba(0,0,0,0)", font_color=CHART_FONT),
        )
        return "chart", fig

    # ── Progress / trend line chart ────────────────────────────────────
    if intent == "progress_chart":
        df = _valid(merged).head(30)
        x_labels = [c.replace("__Percentage", "") for c in pct_cols]
        fig = go.Figure()
        for _, row in df.iterrows():
            ys = [row.get(c) for c in pct_cols]
            if any(pd.notna(y) for y in ys):
                fig.add_trace(go.Scatter(
                    x=x_labels, y=ys, mode="lines+markers",
                    name=str(row["Student_Name"]),
                    line=dict(width=1.5), marker=dict(size=5),
                ))
        fig.update_layout(
            title="Student Progress Trend Across Exams",
            paper_bgcolor=CHART_BG, plot_bgcolor=CHART_BG,
            font_color=CHART_FONT, title_font_color=TITLE_FONT,
            yaxis=dict(range=[0, 110], gridcolor=GRID_COLOR),
            xaxis=dict(gridcolor=GRID_COLOR),
            showlegend=len(df) <= 15,
        )
        return "chart", fig

    # ── Student profile ───────────────────────────────────────────────
    if intent == "student_profile":
        name = cmd.get("student_name") or ""
        return _single_student_cross_profile(name, merged, labels, pct_cols, {})

    # ── Compare two students ──────────────────────────────────────────
    if intent == "compare_two":
        names = cmd.get("compare_names") or []
        if len(names) < 2:
            return "error", "Please name two students to compare, e.g. 'compare Ravi and Sita'."
        rows = []
        for nm in names:
            mask = merged["Student_Name"].astype(str).str.lower().str.contains(nm.lower(), na=False)
            match = merged[mask]
            if match.empty:
                return "error", f"Couldn't find '{nm}'."
            rows.append(match.iloc[0])
        show_cols = ["Student_Name"] + pct_cols
        cmp_df = pd.DataFrame([r[show_cols] for r in rows]).reset_index(drop=True)
        return "table", cmp_df

    # ── Filter table ──────────────────────────────────────────────────
    if intent == "filter_table":
        threshold = cmd.get("threshold")
        direction = cmd.get("direction", "above")
        exam_label = cmd.get("exam_label")
        target_col = next(
            (f"{l}__Percentage" for l in labels if exam_label and exam_label.lower() in l.lower()),
            pct_cols[-1] if pct_cols else None
        )
        if target_col is None:
            return "error", "Couldn't identify which exam to filter on."
        if threshold is None:
            threshold = 50
        mask = merged[target_col] >= threshold if direction != "below" else merged[target_col] < threshold
        out = merged[mask][["Student_Name"] + pct_cols].dropna(subset=[target_col]).reset_index(drop=True)
        out.index += 1
        return "table", out

    # ── Count ─────────────────────────────────────────────────────────
    if intent == "count":
        metric = cmd.get("metric")
        if metric == "detained" and det_cols:
            cnt = int(merged[det_cols].fillna(False).any(axis=1).sum())
            return "text", f"🚫 **{cnt}** student(s) are detained in at least one exam."
        return "text", f"👥 Total students across all exams: **{len(merged)}**"

    # Fallback — leaderboard
    df = _avg_col(merged).nlargest(10, "Avg_%")[["Student_Name"] + pct_cols + ["Avg_%"]].reset_index(drop=True)
    df.index += 1
    return "table", df
