import re
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
import io
from datetime import datetime

def sanitize_text(text: str) -> str:
    if not text:
        return text
    replacements = {
        "\u2010": "-", "\u2011": "-", "\u2012": "-", "\u2013": "-",
        "\u2014": "-", "\u2015": "-", "\u2212": "-", "\u00ad": "-",
        "\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"',
        "\u2022": "-", "\u2026": "...", "\u00a0": " ",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    text = re.sub(r"[^\x00-\xFF]", "", text)
    return text

def _inline_markdown_to_html(text: str) -> str:
    """Converts basic inline Markdown (bold, italic) to ReportLab-compatible tags."""
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"\*(.+?)\*", r"<i>\1</i>", text)
    text = re.sub(r"`(.+?)`", r"<font face='Courier'>\1</font>", text)
    return text

def _parse_markdown_table_lines(table_lines: list) -> list:
    """Parse pipe-delimited Markdown table lines into rows of cell strings,
    skipping the '---' separator row."""
    rows = []
    for row_line in table_lines:
        if re.match(r"^\|?[\s\-:|]+\|?$", row_line):
            continue
        cells = [c.strip() for c in row_line.strip().strip("|").split("|")]
        rows.append(cells)
    return rows

# Usable content width at letter size with this app's default 1in side
# margins (8.5in page - 2*1in margins = 6.5in).
PAGE_CONTENT_WIDTH = 6.5 * inch

def _rows_to_reportlab_table(rows: list, body_style, available_width=PAGE_CONTENT_WIDTH) -> Table:
    """
    Turn parsed row data into an actual ReportLab Table. Column widths are
    divided evenly across available_width explicitly, instead of left to
    ReportLab's auto-sizing — auto-sizing can compute a negative available
    width and crash doc.build() outright on a table with many columns or
    long unbreakable content (this happened with an 18-column table from a
    misdetected PDF form). table_extractor.py now filters tables that wide
    out at the source, but this stays as a defensive backstop regardless.
    """
    max_cols = max(len(r) for r in rows)
    rows = [r + [""] * (max_cols - len(r)) for r in rows]
    col_width = available_width / max_cols
    wrapped_rows = [
        [Paragraph(_inline_markdown_to_html(cell), body_style) for cell in row]
        for row in rows
    ]
    t = Table(wrapped_rows, colWidths=[col_width] * max_cols, hAlign="LEFT")
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EDEFFB")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CCCCCC")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
    ]))
    return t

def render_markdown_to_elements(markdown_text: str, h2_style, h3_style, body_style, bullet_style) -> list:
    """
    Parse a Markdown string into ReportLab flowables: headers, bullets,
    bold/italic/code inline formatting, and pipe-delimited tables rendered
    as real Table() objects instead of flattened pipe-text.

    Shared by generate_query_report's Answer section and
    generate_research_report_pdf's report body, so a Markdown table (or
    bold text, or a header) renders the same in every PDF this app
    produces instead of only being parsed properly in one of the two.
    """
    elements = []
    clean_markdown = sanitize_text(markdown_text)
    lines = clean_markdown.split("\n")

    table_buffer = []
    in_table = False

    def flush_table():
        nonlocal table_buffer, in_table
        if not table_buffer:
            in_table = False
            return
        rows = _parse_markdown_table_lines(table_buffer)
        if rows:
            elements.append(_rows_to_reportlab_table(rows, body_style))
            elements.append(Spacer(1, 8))
        table_buffer = []
        in_table = False

    for line in lines:
        stripped = line.strip()

        if stripped.startswith("|"):
            table_buffer.append(stripped)
            in_table = True
            continue
        elif in_table:
            flush_table()

        if not stripped or stripped == "---":
            continue
        elif stripped.startswith("### "):
            elements.append(Paragraph(_inline_markdown_to_html(stripped[4:]), h3_style))
        elif stripped.startswith("## "):
            elements.append(Paragraph(_inline_markdown_to_html(stripped[3:]), h2_style))
        elif stripped.startswith("# "):
            elements.append(Paragraph(_inline_markdown_to_html(stripped[2:]), h2_style))
        elif stripped.startswith(("- ", "* ")):
            elements.append(Paragraph(_inline_markdown_to_html(stripped[2:]), bullet_style, bulletText="-"))
        elif re.match(r"^\d+\.\s", stripped):
            text = re.sub(r"^\d+\.\s", "", stripped)
            elements.append(Paragraph(_inline_markdown_to_html(text), bullet_style))
        else:
            elements.append(Paragraph(_inline_markdown_to_html(stripped), body_style))

    if in_table:
        flush_table()

    return elements

def render_table_chunk_content(content: str, body_style) -> list:
    """
    Given a table chunk's content as produced by table_extractor.py
    ("Table from <source>, page <n>.\n\n<markdown table>"), render it as
    a caption Paragraph plus a real ReportLab Table. Falls back to plain
    text if the content isn't actually a Markdown table.
    """
    content = sanitize_text(content)
    lines = content.split("\n")
    table_line_idx = [i for i, l in enumerate(lines) if l.strip().startswith("|")]

    if not table_line_idx:
        return [Paragraph(content.replace("\n", "<br/>"), body_style)]

    caption_lines = lines[:table_line_idx[0]]
    table_lines = [lines[i].strip() for i in table_line_idx]

    elements = []
    caption_text = " ".join(l.strip() for l in caption_lines if l.strip())
    if caption_text:
        elements.append(Paragraph(f"<i>{caption_text}</i>", body_style))

    rows = _parse_markdown_table_lines(table_lines)
    if rows:
        elements.append(_rows_to_reportlab_table(rows, body_style))

    return elements

def generate_query_report(task_data: dict) -> io.BytesIO:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.75*inch, bottomMargin=0.75*inch)
    styles = getSampleStyleSheet()

    heading_style = ParagraphStyle(
        "SectionHeading", parent=styles["Heading2"], spaceBefore=16, spaceAfter=8,
        textColor=colors.HexColor("#1E40AF")
    )
    body_style = ParagraphStyle(
        "Body", parent=styles["Normal"], spaceAfter=8, leading=16
    )
    bullet_style = ParagraphStyle(
        "Bullet", parent=body_style, leftIndent=16, bulletIndent=4
    )

    elements = []

    elements.append(Paragraph("OmniRAG Query Report", styles["Title"]))
    elements.append(Paragraph(
        datetime.now().strftime("Generated on %B %d, %Y at %I:%M %p"),
        styles["Normal"]
    ))
    elements.append(Spacer(1, 16))

    elements.append(Paragraph("Question", heading_style))
    elements.append(Paragraph(sanitize_text(task_data.get("question", "N/A")), body_style))

    if task_data.get("search_query"):
        elements.append(Paragraph("Refined Search Query", heading_style))
        elements.append(Paragraph(sanitize_text(task_data["search_query"]), body_style))

    elements.append(Paragraph("Retrieved Context", heading_style))
    retrieved_docs = task_data.get("retrieved_docs") or []
    if retrieved_docs:
        for i, chunk in enumerate(retrieved_docs, 1):
            # chunk is a dict: {"content", "chunk_type", "source"} — see retriever.py
            content = chunk.get("content", "")
            chunk_type = chunk.get("chunk_type", "text")
            if chunk_type == "table":
                label = "Table"
            elif chunk_type == "image":
                label = "Image"
            else:
                label = "Passage"

            elements.append(Paragraph(f"<b>{label} {i}:</b>", body_style))
            if chunk_type == "table":
                elements.extend(render_table_chunk_content(content, body_style))
            else:
                clean_chunk = sanitize_text(content).replace("\n", "<br/>")
                elements.append(Paragraph(clean_chunk, body_style))
            elements.append(Spacer(1, 6))
    else:
        elements.append(Paragraph("No context retrieved.", body_style))

    elements.append(Paragraph("Answer", heading_style))
    # Parsed as Markdown, not flattened — the answer can now contain a table
    # appended by nodes.py's append_tables(), and plain sanitize_text() alone
    # would dump that as literal pipe characters instead of a real table.
    elements.extend(render_markdown_to_elements(
        task_data.get("answer", "N/A"), heading_style, heading_style, body_style, bullet_style
    ))

    elements.append(Paragraph("Evaluation", heading_style))
    elements.append(Paragraph(
        f"Result: {task_data.get('evaluation', 'N/A')} &nbsp;&nbsp;|&nbsp;&nbsp; "
        f"Attempts: {task_data.get('attempts', 'N/A')}",
        body_style
    ))

    doc.build(elements)
    buffer.seek(0)
    return buffer

def generate_research_report_pdf(topic: str, report_markdown: str, sources_used: int) -> io.BytesIO:
    """
    Renders a topic-based research report (Markdown, with headers/tables/bold)
    into a formatted PDF.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.75*inch, bottomMargin=0.75*inch)
    styles = getSampleStyleSheet()

    title_style = styles["Title"]
    h2_style = ParagraphStyle(
        "H2", parent=styles["Heading2"], spaceBefore=14, spaceAfter=8,
        textColor=colors.HexColor("#1E40AF")
    )
    h3_style = ParagraphStyle(
        "H3", parent=styles["Heading3"], spaceBefore=10, spaceAfter=6,
        textColor=colors.HexColor("#1E40AF")
    )
    body_style = ParagraphStyle("Body", parent=styles["Normal"], spaceAfter=6, leading=15)
    bullet_style = ParagraphStyle("Bullet", parent=body_style, leftIndent=16, bulletIndent=4)

    elements = []
    elements.append(Paragraph("OmniRAG Research Report", title_style))
    elements.append(Paragraph(f"Topic: {sanitize_text(topic)}", styles["Normal"]))
    elements.append(Paragraph(
        datetime.now().strftime("Generated on %B %d, %Y at %I:%M %p")
        + f" &nbsp;&nbsp;|&nbsp;&nbsp; {sources_used} source passages used",
        styles["Normal"]
    ))
    elements.append(Spacer(1, 16))

    elements.extend(render_markdown_to_elements(report_markdown, h2_style, h3_style, body_style, bullet_style))

    doc.build(elements)
    buffer.seek(0)
    return buffer