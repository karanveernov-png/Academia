"""
core.data_loader
================
File ingestion + the core transformation pipeline that turns a raw
upload into the canonical schema (Total_Marks, Percentage, Grade, Risk,
Detained) used by every chart, AI command, and PDF export in the app.

ACCURACY UPGRADES in prepare_data():
1. "Max possible marks" per subject now comes from the user-confirmed
   `mapping["max_marks"]` dict (set in the column mapper UI) instead of
   silently assuming the highest score actually present in the data is
   the full mark. The old approach under-counts the denominator whenever
   nobody scored 100%, which inflates everyone's percentage.
2. Missing/NaN marks are now prorated out of BOTH the numerator and the
   denominator for that student, instead of being treated as a zero in
   the numerator while still counting full marks in the denominator.
   That previous mismatch silently punished students with one missing
   mark far more harshly than a genuine zero.
3. Per-subject fail/detain flags use the same confirmed full-marks figure
   instead of re-deriving it from observed data, so single-subject and
   cross-exam views can never disagree about what "33% in Maths" means.
"""
import pandas as pd
import numpy as np
import streamlit as st


@st.cache_data(show_spinner=False)
def load_file(uploaded_file):
    """Load CSV or Excel file and return a raw DataFrame."""
    name = uploaded_file.name.lower()
    if name.endswith(".csv"):
        # Try common encodings
        for enc in ["utf-8", "latin-1", "cp1252"]:
            try:
                df = pd.read_csv(uploaded_file, encoding=enc)
                uploaded_file.seek(0)
                return df, None
            except Exception:
                uploaded_file.seek(0)
        return None, "Could not decode CSV file."
    elif name.endswith((".xlsx", ".xls")):
        try:
            df = pd.read_excel(uploaded_file)
            return df, None
        except Exception as e:
            return None, str(e)
    return None, "Unsupported file type."


def prepare_data(df: pd.DataFrame, mapping: dict, active_marks: list = None,
                  detain_threshold: float = 33.0) -> pd.DataFrame:
    """
    Standardise the raw DataFrame to a canonical schema using the mapping.
    Adds 'Total_Marks', 'Percentage', 'Grade', 'Risk' and 'Detained' columns.

    active_marks: which of the mapped marks columns should actually count
        towards Total_Marks / Percentage for THIS view. Defaults to all
        mapped marks columns (the "combined / whole subjects" view). Pass a
        single-element list to get a per-subject view instead.
    detain_threshold: percentage below which a student is considered
        "Detained" (held back) — separate from the overall pass-rate KPI so
        a student can be flagged even if their combined percentage is fine
        but they failed the subject(s) currently in view.
    """
    out = df.copy()
    max_marks_map = mapping.get("max_marks") or {}

    # ── Rename mapped columns to standard names ──────────────────────────
    rename = {}
    if mapping["name"]  and mapping["name"]  in out.columns: rename[mapping["name"]]   = "Student_Name"
    if mapping["id"]    and mapping["id"]    in out.columns: rename[mapping["id"]]     = "Student_ID"
    if mapping["class"] and mapping["class"] in out.columns: rename[mapping["class"]]  = "Class"
    if mapping["gender"]and mapping["gender"]in out.columns: rename[mapping["gender"]] = "Gender"
    out.rename(columns=rename, inplace=True)

    # ── Compute total marks from selected score columns ───────────────────
    all_mapped = [c for c in mapping["marks"] if c in out.columns]
    missing = [c for c in mapping["marks"] if c not in out.columns]
    if missing:
        st.warning(f"⚠️ Skipping column(s) not found in data after mapping: {', '.join(missing)}")

    # Make sure every mapped marks column is numeric, regardless of which
    # subset is "active" for this particular view — this is needed so
    # per-subject views and the AI command bar can both reach any subject.
    for col in all_mapped:
        out[col] = pd.to_numeric(out[col], errors="coerce")

    mark_cols = [c for c in (active_marks if active_marks else all_mapped) if c in out.columns]

    def _full_marks(col):
        """User-confirmed full marks for a subject, falling back to the
        observed max in the data if the mapper didn't supply one
        (e.g. mapping built programmatically rather than via the UI)."""
        val = max_marks_map.get(col)
        if val and val > 0:
            return float(val)
        observed = pd.to_numeric(out[col], errors="coerce").max()
        return float(observed) if pd.notna(observed) and observed > 0 else np.nan

    if mark_cols:
        full_marks = {c: _full_marks(c) for c in mark_cols}
        marks_matrix = out[mark_cols]

        # Numerator: sum of marks actually present (NaN excluded automatically)
        out["Total_Marks"] = marks_matrix.sum(axis=1, skipna=True)

        # Denominator: prorate full marks per student — only count a
        # subject's full marks if that student actually has a score for
        # it, so a missing mark doesn't get treated as a free zero while
        # still being charged full marks in the denominator.
        present_mask = marks_matrix.notna()
        full_marks_row = pd.Series(0.0, index=out.index)
        for col in mark_cols:
            fm = full_marks[col]
            if pd.notna(fm):
                full_marks_row = full_marks_row + present_mask[col].astype(float) * fm

        with np.errstate(divide="ignore", invalid="ignore"):
            pct = np.where(full_marks_row > 0, out["Total_Marks"] / full_marks_row * 100, 0.0)
        out["Percentage"] = pd.Series(pct, index=out.index).round(2)
        out["__Full_Marks_Available"] = full_marks_row
    else:
        # If no marks selected, look for any numeric columns
        num_cols = out.select_dtypes(include=[np.number]).columns.tolist()
        if num_cols:
            out["Total_Marks"] = out[num_cols[0]]
            out["Percentage"]  = 0.0
        else:
            out["Total_Marks"] = 0.0
            out["Percentage"]  = 0.0

    # ── Fallback placeholders ─────────────────────────────────────────────
    if "Student_Name" not in out.columns:
        out["Student_Name"] = [f"Student {i+1}" for i in range(len(out))]
    if "Student_ID"   not in out.columns:
        out["Student_ID"]   = range(1, len(out)+1)
    if "Class"        not in out.columns:
        out["Class"]        = "N/A"
    if "Gender"       not in out.columns:
        out["Gender"]       = "N/A"

    # ── Grade assignment ──────────────────────────────────────────────────
    def grade(pct):
        if   pct >= 90: return "A+"
        elif pct >= 80: return "A"
        elif pct >= 70: return "B+"
        elif pct >= 60: return "B"
        elif pct >= 50: return "C"
        elif pct >= 40: return "D"
        else:           return "F"

    out["Grade"] = out["Percentage"].apply(grade)

    # ── Risk flag ─────────────────────────────────────────────────────────
    def risk(pct):
        if pct < 40:  return "High"
        elif pct < 60: return "Medium"
        else:          return "Low"

    out["Risk"] = out["Percentage"].apply(risk)

    # ── Detained flag (separate from overall pass-rate / risk) ────────────
    # A student is "Detained" if their percentage in the CURRENT view
    # (combined or single-subject) falls below the detain threshold. This
    # is what lets "how many D / detained in English" be answered correctly
    # even when a student's overall combined percentage looks fine.
    out["Detained"] = out["Percentage"] < detain_threshold

    # Per-subject fail flags (used by the AI command bar for questions like
    # "how many detentions in the whole class / across all subjects").
    # Uses the same confirmed full-marks figure as the main calculation
    # above, so single-subject and "all subjects" views never disagree.
    for col in all_mapped:
        fm = _full_marks(col)
        if pd.notna(fm) and fm > 0:
            out[f"__fail__{col}"] = out[col] < (fm * (detain_threshold / 100.0))
        else:
            out[f"__fail__{col}"] = False

    return out


def compute_kpis(df: pd.DataFrame, mark_cols: list) -> dict:
    kpis = {}
    kpis["total"]    = len(df)
    kpis["avg_pct"]  = round(df["Percentage"].mean(), 2) if "Percentage" in df else 0
    kpis["avg_total"]= round(df["Total_Marks"].mean(), 2)
    kpis["median_pct"] = round(df["Percentage"].median(), 2) if "Percentage" in df else 0
    kpis["std_pct"]    = round(df["Percentage"].std(), 2) if "Percentage" in df and len(df) > 1 else 0

    top_row = df.loc[df["Total_Marks"].idxmax()]
    bot_row = df.loc[df["Total_Marks"].idxmin()]
    kpis["top_name"]  = top_row.get("Student_Name", "N/A")
    kpis["top_marks"] = top_row["Total_Marks"]
    kpis["bot_name"]  = bot_row.get("Student_Name", "N/A")
    kpis["bot_marks"] = bot_row["Total_Marks"]

    kpis["pass_rate"]  = round((df["Percentage"] >= 40).mean()*100, 1)
    kpis["at_risk_n"]  = int((df["Risk"] == "High").sum())
    kpis["detained_n"] = int(df["Detained"].sum()) if "Detained" in df else 0
    kpis["grade_dist"] = df["Grade"].value_counts().to_dict()

    if mark_cols:
        kpis["subject_avg"] = {c: round(df[c].mean(), 2) for c in mark_cols if c in df}
    return kpis
