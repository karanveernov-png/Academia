"""
core.pdf_export
================
Builds a polished, multi-page PDF report (cover, KPIs, embedded
Plotly charts, at-risk/detained tables, AI insights) via ReportLab.

CLARITY FIX: the dashboard's charts use a dark-UI theme (light gray /
light purple text on a transparent background) — perfect on the web page,
but nearly invisible once dropped onto a white PDF page. _pdf_theme()
re-colors a *copy* of each figure (opaque white background, dark slate
text, darker gridlines) purely for the PDF, without touching how charts
look on the live dashboard.

ACCURACY/CLARITY FIX: chart images used to be rendered as a fixed
900×420px PNG and then stretched into PDF boxes with a different aspect
ratio (e.g. 3.1in × 2.4in ≈ 1.29:1 vs. the rendered 900×420 ≈ 2.14:1).
That mismatch squished pie charts into ovals and distorted bar charts.
_fig_to_pdf_image() now renders each chart at the SAME aspect ratio as
the box it will be placed in, at a high pixel density (≈300 DPI
equivalent) so charts are sharp even when printed.
"""
import io
import copy
import pandas as pd
from datetime import datetime
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table,
    TableStyle, PageBreak, HRFlowable, Image, KeepTogether
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.pdfgen import canvas as _canvas

from core.config import GRADE_COLORS
from core.charts import chart_grade_pie, chart_score_distribution, chart_subject_bar, chart_top_n_students


class _FooterCanvas(_canvas.Canvas):
    """Adds a consistent footer (page number + report title) to every page."""
    def __init__(self, *args, report_title="", **kwargs):
        super().__init__(*args, **kwargs)
        self._report_title = report_title
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total_pages = len(self._saved_page_states)
        for i, state in enumerate(self._saved_page_states, start=1):
            self.__dict__.update(state)
            self._draw_footer(i, total_pages)
            super().showPage()
        super().save()

    def _draw_footer(self, page_num, total_pages):
        self.saveState()
        self.setStrokeColor(colors.HexColor("#e2e8f0"))
        self.line(0.7*inch, 0.45*inch, A4[0]-0.7*inch, 0.45*inch)
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#94a3b8"))
        self.drawString(0.7*inch, 0.3*inch, self._report_title)
        self.drawRightString(A4[0]-0.7*inch, 0.3*inch, f"Page {page_num} of {total_pages}")
        self.restoreState()


def _pdf_theme(fig, show_title=True, margin=None):
    """Return a re-themed COPY of a dashboard figure, suitable for a white
    printed page. Leaves the original figure (and the live dashboard)
    completely untouched."""
    if fig is None:
        return None
    fig = copy.deepcopy(fig)

    # Strip the leading emoji from the chart title — the PDF is rendered
    # with Helvetica, which has no emoji glyphs, so they'd otherwise show
    # up as an empty "tofu" box right before the title text.
    title_text = fig.layout.title.text if fig.layout.title else None
    if title_text:
        stripped = title_text.lstrip("🎓📊📚⚠️🏆🎯🏫⚧🧩🕸️🔻 ").strip()
        title_text = stripped or title_text
    if not show_title:
        # Several charts already sit under a Paragraph heading in the PDF
        # ("Average Score per Subject", "Top Performers"...). Repeating the
        # exact same title inside the chart image is redundant and eats
        # into the vertical space available for the chart itself.
        title_text = None

    margin = margin or dict(l=90, r=30, t=68 if show_title else 24, b=70)

    fig.update_layout(
        paper_bgcolor="#ffffff",
        plot_bgcolor="#ffffff",
        font=dict(color="#1e293b", family="Helvetica, Arial, sans-serif", size=13),
        title=dict(text=title_text, font=dict(color="#4338ca", size=16, family="Helvetica, Arial, sans-serif"),
                   x=0.02, xanchor="left"),
        legend=dict(
            bgcolor="rgba(255,255,255,0)",
            bordercolor="#e2e8f0",
            borderwidth=1,
            font=dict(color="#1e293b", size=12),
        ),
        margin=margin,
    )
    fig.update_xaxes(gridcolor="#e2e8f0", zeroline=False, linecolor="#cbd5e1",
                      tickfont=dict(color="#78716c", size=12), title_font=dict(color="#78716c"))
    fig.update_yaxes(gridcolor="#e2e8f0", zeroline=False, linecolor="#cbd5e1",
                      tickfont=dict(color="#78716c", size=12), title_font=dict(color="#78716c"))
    return fig


def _fig_to_pdf_image(fig, width=6.4*inch, height=3.0*inch, scale=3, show_title=True, margin=None):
    """Render a Plotly figure to a reportlab Image flowable via kaleido.

    Renders at the SAME aspect ratio as the target (width, height) box, at
    a "natural" pixel size (96px per inch — matching the size text/lines
    were designed at) and then uses kaleido's `scale` multiplier to
    supersample for a crisp, print-quality result. Setting a much larger
    width/height directly (without scale) keeps font sizes the same
    absolute pixel count while the canvas grows, making text shrink
    relative to the image — that was the original bug. Returns None
    (silently) if kaleido isn't installed, so the PDF still builds fine —
    just without that particular chart.

    margin: override the default (bar-chart-friendly) margins — pass a
    smaller dict for pie/donut charts, which have no y-axis and would
    otherwise get squeezed/cut off by the wide left margin bar charts need.
    """
    if fig is None:
        return None
    try:
        themed = _pdf_theme(fig, show_title=show_title, margin=margin)
        base_dpi = 96
        px_width = max(1, int(round((width / inch) * base_dpi)))
        px_height = max(1, int(round((height / inch) * base_dpi)))
        png_bytes = themed.to_image(format="png", width=px_width, height=px_height, scale=scale)
        return Image(io.BytesIO(png_bytes), width=width, height=height)
    except Exception:
        return None


def generate_pdf(df: pd.DataFrame, kpis: dict, insights: str, exam_label: str, mapping: dict = None) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                            rightMargin=0.7*inch, leftMargin=0.7*inch,
                            topMargin=0.8*inch, bottomMargin=0.7*inch)
    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle("CustomTitle", parent=styles["Title"],
                                  fontSize=24, textColor=colors.HexColor("#f97316"),
                                  spaceAfter=6, alignment=TA_CENTER)
    subtitle_style = ParagraphStyle("Subtitle", parent=styles["Heading2"],
                                     fontSize=14, textColor=colors.HexColor("#78716c"),
                                     alignment=TA_CENTER, spaceAfter=4)
    meta_style = ParagraphStyle("Meta", parent=styles["Normal"],
                                 fontSize=9, textColor=colors.HexColor("#94a3b8"),
                                 alignment=TA_CENTER)
    h1 = ParagraphStyle("H1", parent=styles["Heading1"],
                         fontSize=14, textColor=colors.HexColor("#4f46e5"),
                         spaceAfter=4)
    body = ParagraphStyle("Body", parent=styles["Normal"],
                          fontSize=10, leading=15, textColor=colors.HexColor("#1e293b"))
    small = ParagraphStyle("Small", parent=body, fontSize=8)
    grade_cell = ParagraphStyle("GradeCell", parent=small, alignment=TA_CENTER, fontName="Helvetica-Bold")

    story = []

    # ── Cover / Title block ──
    story.append(Spacer(1, 18))
    story.append(Paragraph("🎓 Studora Dashboard", title_style))
    story.append(Paragraph(f"Performance Report — {exam_label}", subtitle_style))
    story.append(Paragraph(f"Generated on {datetime.now().strftime('%d %B %Y, %I:%M %p')}", meta_style))
    story.append(Spacer(1, 10))
    story.append(HRFlowable(width="100%", color=colors.HexColor("#f97316"), thickness=1.5))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        f"This report covers <b>{kpis['total']}</b> student(s), with an average score of "
        f"<b>{kpis['avg_pct']}%</b> and a pass rate of <b>{kpis['pass_rate']}%</b>.", body))
    story.append(Spacer(1, 16))

    # ── KPI Table ──
    story.append(Paragraph("Key Performance Indicators", h1))
    kpi_data = [
        ["Metric", "Value"],
        ["Total Students", str(kpis["total"])],
        ["Average Percentage", f"{kpis['avg_pct']}%"],
        ["Average Total Marks", str(kpis["avg_total"])],
        ["Pass Rate", f"{kpis['pass_rate']}%"],
        ["At-Risk Students", str(kpis["at_risk_n"])],
        ["Detained Students", str(kpis.get("detained_n", "N/A"))],
        ["Top Scorer", f"{kpis['top_name']}  ({kpis['top_marks']} marks)"],
        ["Lowest Scorer", f"{kpis['bot_name']}  ({kpis['bot_marks']} marks)"],
    ]
    kpi_table = Table(kpi_data, colWidths=[2.5*inch, 4*inch])
    kpi_table.setStyle(TableStyle([
        ("BACKGROUND",  (0,0), (-1,0), colors.HexColor("#f97316")),
        ("TEXTCOLOR",   (0,0), (-1,0), colors.white),
        ("FONTNAME",    (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE",    (0,0), (-1,-1), 10),
        ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.HexColor("#f8fafc"), colors.white]),
        ("GRID",        (0,0), (-1,-1), 0.5, colors.HexColor("#e2e8f0")),
        ("ALIGN",       (1,0), (1,-1), "CENTER"),
        ("VALIGN",      (0,0), (-1,-1), "MIDDLE"),
        ("TOPPADDING",  (0,0), (-1,-1), 5),
        ("BOTTOMPADDING",(0,0),(-1,-1), 5),
    ]))
    story.append(kpi_table)
    story.append(Spacer(1, 14))

    # ── Grade Distribution (table + pie chart side note) ──
    story.append(Paragraph("Grade Distribution", h1))
    gd = kpis.get("grade_dist", {})
    grade_data = [["Grade","Count"]] + [[g, str(c)] for g, c in sorted(gd.items())]
    if len(grade_data) > 1:
        gt = Table(grade_data, colWidths=[1.5*inch, 1.5*inch])
        gt.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#ea580c")),
            ("TEXTCOLOR",  (0,0), (-1,0), colors.white),
            ("FONTNAME",   (0,0), (-1,0), "Helvetica-Bold"),
            ("FONTSIZE",   (0,0), (-1,-1), 10),
            ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.HexColor("#f5f3ff"), colors.white]),
            ("GRID", (0,0), (-1,-1), 0.5, colors.HexColor("#e2e8f0")),
            ("ALIGN", (0,0), (-1,-1), "CENTER"),
            ("TOPPADDING", (0,0),(-1,-1), 4),
            ("BOTTOMPADDING",(0,0),(-1,-1), 4),
        ]))
        story.append(gt)
    story.append(Spacer(1, 10))

    # ── Visual charts, embedded as images (best-effort — needs kaleido) ──
    chart_imgs = []
    pie_img = _fig_to_pdf_image(chart_grade_pie(df), width=3.1*inch, height=2.4*inch,
                                 margin=dict(l=10, r=10, t=44, b=10))
    dist_img = _fig_to_pdf_image(chart_score_distribution(df), width=3.1*inch, height=2.4*inch,
                                  margin=dict(l=50, r=10, t=44, b=50))
    if pie_img and dist_img:
        chart_row = Table([[dist_img, pie_img]], colWidths=[3.2*inch, 3.2*inch])
        chart_row.setStyle(TableStyle([("VALIGN", (0,0), (-1,-1), "MIDDLE")]))
        story.append(chart_row)
        story.append(Spacer(1, 8))

    if mapping and mapping.get("marks") and len(mapping["marks"]) > 1:
        subj_img = _fig_to_pdf_image(chart_subject_bar(df, mapping["marks"]), width=6.3*inch, height=2.6*inch, show_title=False)
        if subj_img:
            story.append(Paragraph("Average Score per Subject", h1))
            story.append(subj_img)
            story.append(Spacer(1, 10))

    top_img = _fig_to_pdf_image(
        chart_top_n_students(df, min(10, len(df))),
        width=6.3*inch, height=3.4*inch,
        show_title=False,
        margin=dict(l=160, r=20, t=24, b=50),
    )
    if top_img:
        story.append(Paragraph("Top Performers", h1))
        story.append(top_img)
        story.append(Spacer(1, 10))

    # ── AI Insights — parse markdown into clean ReportLab paragraphs ──
    if insights and "Enter your Groq" not in insights and "❌ Groq" not in insights:
        story.append(Paragraph("AI-Powered Insights (Groq LLaMA 8B)", h1))
        story.append(Spacer(1, 4))

        # ReportLab doesn't understand markdown. Convert the common patterns
        # the LLM produces (**bold**, ### headers, bullet lines) into proper
        # styled Paragraphs so the PDF looks clean.
        bullet_style = ParagraphStyle(
            "Bullet", parent=styles["Normal"],
            fontSize=10, leading=15, textColor=colors.HexColor("#1e293b"),
            leftIndent=14, firstLineIndent=-10, spaceBefore=3,
        )
        section_style = ParagraphStyle(
            "InsightSection", parent=styles["Normal"],
            fontSize=11, leading=14, textColor=colors.HexColor("#4f46e5"),
            fontName="Helvetica-Bold", spaceBefore=8, spaceAfter=2,
        )
        import re as _re

        def _md_to_rl(text: str) -> str:
            """Convert inline markdown to ReportLab XML tags."""
            # **bold** → <b>bold</b>
            text = _re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
            # *italic* → <i>italic</i>
            text = _re.sub(r"\*(.+?)\*", r"<i>\1</i>", text)
            # strip stray leading #, *, - markers already handled per-line
            return text

        for raw_line in insights.splitlines():
            line = raw_line.strip()
            if not line:
                story.append(Spacer(1, 4))
                continue
            # Heading lines: ## or ### prefix, or lines that look like **📋 Title**
            if _re.match(r"^#{1,3}\s+", line) or _re.match(r"^\*\*[^\*]+\*\*\s*$", line):
                clean = _re.sub(r"^#+\s+", "", line)
                clean = _re.sub(r"\*\*(.+?)\*\*", r"\1", clean).strip()
                story.append(Paragraph(clean, section_style))
            # Bullet lines: - or * or numbered
            elif _re.match(r"^[-*•]\s+", line) or _re.match(r"^\d+\.\s+", line):
                clean = _re.sub(r"^[-*•\d.]+\s+", "", line)
                story.append(Paragraph("• " + _md_to_rl(clean), bullet_style))
            else:
                story.append(Paragraph(_md_to_rl(line), body))
        story.append(Spacer(1, 14))

    # ── At-Risk Students Table (colour-coded grades) ──
    risk_df = df[df["Risk"] == "High"][["Student_Name","Student_ID","Total_Marks","Percentage","Grade"]].head(40)
    if not risk_df.empty:
        story.append(Paragraph(f"At-Risk Students — {len(risk_df)} shown (Percentage &lt; 40%)", h1))
        risk_data = [["Name","ID","Total Marks","Percentage","Grade"]]
        for _, row in risk_df.iterrows():
            grade_p = Paragraph(str(row["Grade"]),
                                 ParagraphStyle("g", parent=grade_cell,
                                                textColor=GRADE_COLORS.get(row["Grade"], colors.black)))
            risk_data.append([
                str(row["Student_Name"]), str(row["Student_ID"]),
                str(row["Total_Marks"]), f"{row['Percentage']}%", grade_p
            ])
        rt = Table(risk_data, colWidths=[2*inch, 0.9*inch, 1.2*inch, 1.1*inch, 0.8*inch])
        rt.setStyle(TableStyle([
            ("BACKGROUND",  (0,0), (-1,0), colors.HexColor("#ef4444")),
            ("TEXTCOLOR",   (0,0), (-1,0), colors.white),
            ("FONTNAME",    (0,0), (-1,0), "Helvetica-Bold"),
            ("FONTSIZE",    (0,0), (-1,-1), 9),
            ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.HexColor("#fff5f5"), colors.white]),
            ("GRID", (0,0), (-1,-1), 0.5, colors.HexColor("#fca5a5")),
            ("ALIGN", (1,0), (-1,-1), "CENTER"),
            ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
            ("TOPPADDING", (0,0),(-1,-1), 4),
            ("BOTTOMPADDING",(0,0),(-1,-1), 4),
        ]))
        story.append(rt)
        story.append(Spacer(1, 14))

    # ── Full Data Table (first 50 rows), colour-coded grade column ──
    story.append(PageBreak())
    story.append(Paragraph("Full Student Data (first 50 rows)", h1))
    show_cols = ["Student_Name","Student_ID","Total_Marks","Percentage","Grade","Risk"]
    show_cols = [c for c in show_cols if c in df.columns]
    sub_df = df[show_cols].head(50)
    grade_idx = show_cols.index("Grade") if "Grade" in show_cols else None
    table_data = [show_cols]
    for _, row in sub_df.iterrows():
        row_cells = []
        for c in show_cols:
            val = row[c]
            if c == "Grade":
                row_cells.append(Paragraph(str(val),
                                  ParagraphStyle("g2", parent=grade_cell,
                                                 textColor=GRADE_COLORS.get(val, colors.black))))
            else:
                row_cells.append(str(val))
        table_data.append(row_cells)
    col_w = [inch * 6.5 / len(show_cols)] * len(show_cols)
    ft = Table(table_data, colWidths=col_w, repeatRows=1)
    ft.setStyle(TableStyle([
        ("BACKGROUND",  (0,0), (-1,0), colors.HexColor("#4f46e5")),
        ("TEXTCOLOR",   (0,0), (-1,0), colors.white),
        ("FONTNAME",    (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE",    (0,0), (-1,-1), 8),
        ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.HexColor("#f8fafc"), colors.white]),
        ("GRID", (0,0), (-1,-1), 0.4, colors.HexColor("#e2e8f0")),
        ("ALIGN", (2,0), (-1,-1), "CENTER"),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("TOPPADDING", (0,0),(-1,-1), 3),
        ("BOTTOMPADDING",(0,0),(-1,-1), 3),
    ]))
    story.append(ft)

    def _make_canvas(*args, **kwargs):
        return _FooterCanvas(*args, report_title=f"Studora Dashboard · {exam_label}", **kwargs)

    doc.build(story, canvasmaker=_make_canvas)
    buffer.seek(0)
    return buffer.read()