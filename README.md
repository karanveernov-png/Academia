# 🎓 Student Intelligence Portal

**Unified Streamlit dashboard** — Exam Analysis · Attendance Tracker · Fee Controller.

All data is **user-uploaded**. No hardcoded students, no demo mode.

---

## 🚀 Quick Start

```bash
pip install -r requirements.txt
streamlit run app.py
```

---

## 📂 What to Upload

| Module | File type | Minimum columns needed |
|---|---|---|
| **Exam Analysis** | CSV or Excel | Student name, subject mark columns |
| **Attendance** | CSV or Excel | Student name, present days, absent days (or attendance %) |
| **Fee Controller** | CSV or Excel | Student name, amount due, amount paid |

Upload 2+ exam files to unlock **Cross-Exam Comparison**.

---

## 🗂️ Folder Structure

```
student_portal/
├── app.py                    ← main entry point
├── requirements.txt
├── core/
│   ├── config.py             ← shared constants & page config
│   ├── styling.py            ← all CSS (one place)
│   ├── ui_components.py      ← HTML helpers, KPI cards, column mappers
│   ├── sidebar.py            ← three-upload sidebar
│   ├── data_loader.py        ← file loading + exam data pipeline
│   ├── charts.py             ← Plotly chart builders (exam)
│   ├── ai_insights.py        ← Groq AI summary generation
│   ├── ai_commands_single.py ← AI natural-language command bar
│   └── pdf_export.py         ← ReportLab PDF export
└── tabs/
    ├── exam_tab.py           ← single-exam full analysis
    ├── cross_exam_tab.py     ← multi-exam comparison
    ├── attendance_tab.py     ← attendance module (upload-driven)
    └── fee_tab.py            ← fee controller (upload-driven)
```

---

## 🤖 AI Features (optional)

Add a **Groq API key** in the sidebar to unlock:
- Natural-language command bar ("list girls above 80% in maths")
- AI-generated teacher-ready insight reports
- Free key: https://console.groq.com/keys

---

## 📄 Sample CSV Formats

**Exam CSV:**
```
Name,Roll,Class,Maths,Science,English,Hindi,Social
Aarav Sharma,S001,9-A,22,18,21,19,20
```

**Attendance CSV:**
```
Name,Student ID,Class,Present,Absent,Late,Total Days
Aarav Sharma,S001,9-A,38,4,2,44
```

**Fee CSV:**
```
Name,Student ID,Class,Term,Fee Due,Amount Paid,Balance,Status
Aarav Sharma,S001,9-A,Term 1,10200,10200,0,Paid
```
