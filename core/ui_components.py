"""
core.ui_components — shared HTML helpers, KPI card builder, column mapper.
"""
import streamlit as st
import pandas as pd


def render_html(html: str) -> None:
    cleaned = "\n".join(line.strip() for line in html.strip().splitlines())
    st.markdown(cleaned, unsafe_allow_html=True)


def kpi_card(icon, value, label, sub="", variant=""):
    sub_html = f'<div class="kpi-sub" title="{sub}">{sub}</div>' if sub else ""
    cls = f"kpi-card {variant}".strip()
    return f"""
<div class="{cls}">
<span class="kpi-icon">{icon}</span>
<div class="kpi-value">{value}</div>
<div class="kpi-label">{label}</div>
{sub_html}
</div>"""


def column_mapper_ui(df: pd.DataFrame, key_prefix: str) -> dict:
    """
    Sidebar widget that maps user's column names → standard roles.
    Returns: { name, id, marks, class, gender, max_marks }
    """
    st.sidebar.divider()
    st.sidebar.markdown("### 🗂️ Column Mapping")
    st.sidebar.caption("Select which columns are Name, Roll No, and Marks.")

    def pick(label, hints, multi=False, exclude=None):
        exclude = set(exclude or [])
        available = [c for c in df.columns if c not in exclude]
        local_cols = ["(none)"] + available
        lower_map = {c.lower(): c for c in available}

        guessed = None
        for hint in hints:
            hl = hint.lower()
            if hl in lower_map:
                guessed = lower_map[hl]; break
            for lc, rc in lower_map.items():
                if hl in lc:
                    guessed = rc; break
            if guessed:
                break

        if multi:
            default = [guessed] if guessed else []
            return st.sidebar.multiselect(label, available, default=default,
                                          key=f"{key_prefix}_{label}")
        else:
            idx = local_cols.index(guessed) if guessed and guessed in local_cols else 0
            return st.sidebar.selectbox(label, local_cols, index=idx,
                                        key=f"{key_prefix}_{label}")

    name_col   = pick("👤 Student Name",   ["name","student name","sname","full name"])
    id_col     = pick("🆔 Student ID / Roll",["id","roll","roll no","enrollment","student id","regno"],
                       exclude=[name_col] if name_col != "(none)" else [])
    used = [c for c in [name_col, id_col] if c and c != "(none)"]
    marks_cols = pick("📊 Marks / Score columns",
                      ["marks","score","total","obtained"], multi=True, exclude=used)
    used = used + marks_cols
    class_col  = pick("🏫 Class / Section", ["class","section","batch","group","div"], exclude=used)
    used = used + ([class_col] if class_col and class_col != "(none)" else [])
    gender_col = pick("⚧ Gender", ["gender","sex"], exclude=used)

    max_marks = {}
    if marks_cols:
        with st.sidebar.expander("🎯 Max marks per subject", expanded=False):
            st.caption("Defaults to observed max. Override for accuracy.")
            for col in marks_cols:
                obs = pd.to_numeric(df[col], errors="coerce").max()
                default_val = float(obs) if pd.notna(obs) and obs > 0 else 100.0
                max_marks[col] = st.number_input(
                    f"{col}", min_value=1.0, value=default_val, step=1.0,
                    key=f"{key_prefix}_maxmarks_{col}"
                )

    def clean(v):
        return v if v != "(none)" else None

    return {
        "name":      clean(name_col),
        "id":        clean(id_col),
        "marks":     marks_cols,
        "class":     clean(class_col),
        "gender":    clean(gender_col),
        "max_marks": max_marks,
    }


def att_column_mapper_ui(df: pd.DataFrame, key_prefix: str) -> dict:
    """Column mapper specifically for attendance data."""
    st.sidebar.markdown("### 🗂️ Attendance Columns")
    st.sidebar.caption("Map your attendance CSV columns.")
    cols = list(df.columns)
    none_cols = ["(none)"] + cols
    lower = {c.lower(): c for c in cols}

    def guess(hints):
        for h in hints:
            if h.lower() in lower: return lower[h.lower()]
            for lc, rc in lower.items():
                if h.lower() in lc: return rc
        return None

    def pick(label, hints, key):
        g = guess(hints)
        idx = none_cols.index(g) if g and g in none_cols else 0
        return st.sidebar.selectbox(label, none_cols, index=idx, key=key)

    name_col    = pick("👤 Student Name",   ["name","student","sname"],   f"{key_prefix}_att_name")
    id_col      = pick("🆔 Student ID",     ["id","roll","sid"],          f"{key_prefix}_att_id")
    class_col   = pick("🏫 Class/Section",  ["class","section","batch"],  f"{key_prefix}_att_class")
    present_col = pick("✅ Present Days",   ["present","present days"],   f"{key_prefix}_att_present")
    absent_col  = pick("❌ Absent Days",    ["absent","absence"],         f"{key_prefix}_att_absent")
    late_col    = pick("⏰ Late Days",      ["late","tardy"],             f"{key_prefix}_att_late")
    total_col   = pick("📅 Total Days",     ["total","total days","days"],f"{key_prefix}_att_total")
    pct_col     = pick("% Attendance",     ["attendance %","att%","pct","percentage"],f"{key_prefix}_att_pct")

    def clean(v): return v if v != "(none)" else None
    return {
        "name": clean(name_col), "id": clean(id_col), "class": clean(class_col),
        "present": clean(present_col), "absent": clean(absent_col),
        "late": clean(late_col), "total": clean(total_col), "pct": clean(pct_col),
    }


def fee_column_mapper_ui(df: pd.DataFrame, key_prefix: str) -> dict:
    """Column mapper specifically for fee data."""
    st.sidebar.markdown("### 🗂️ Fee Columns")
    st.sidebar.caption("Map your fee CSV columns.")
    cols = list(df.columns)
    none_cols = ["(none)"] + cols
    lower = {c.lower(): c for c in cols}

    def guess(hints):
        for h in hints:
            if h.lower() in lower: return lower[h.lower()]
            for lc, rc in lower.items():
                if h.lower() in lc: return rc
        return None

    def pick(label, hints, key):
        g = guess(hints)
        idx = none_cols.index(g) if g and g in none_cols else 0
        return st.sidebar.selectbox(label, none_cols, index=idx, key=key)

    name_col   = pick("👤 Student Name",  ["name","student"],           f"{key_prefix}_fee_name")
    id_col     = pick("🆔 Student ID",    ["id","roll","sid"],          f"{key_prefix}_fee_id")
    class_col  = pick("🏫 Class",         ["class","section"],          f"{key_prefix}_fee_class")
    term_col   = pick("📅 Term / Month",  ["term","month","quarter"],   f"{key_prefix}_fee_term")
    due_col    = pick("💳 Amount Due",    ["due","total fee","amount","fee"],f"{key_prefix}_fee_due")
    paid_col   = pick("✅ Amount Paid",   ["paid","amount paid"],        f"{key_prefix}_fee_paid")
    bal_col    = pick("📉 Balance",       ["balance","bal","outstanding"],f"{key_prefix}_fee_bal")
    status_col = pick("🏷️ Status",        ["status","payment status"],   f"{key_prefix}_fee_status")

    def clean(v): return v if v != "(none)" else None
    return {
        "name": clean(name_col), "id": clean(id_col), "class": clean(class_col),
        "term": clean(term_col), "due": clean(due_col), "paid": clean(paid_col),
        "balance": clean(bal_col), "status": clean(status_col),
    }
