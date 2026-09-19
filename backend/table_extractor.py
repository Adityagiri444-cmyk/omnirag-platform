"""
table_extractor.py
Shared table-extraction helper for OmniRAG's ingestion pipeline.
Used by both build_retriever.py (bulk index build) and retriever.py
(single-document add), so table handling is identical everywhere
instead of being duplicated and drifting apart.
"""

import pdfplumber
from langchain_core.documents import Document

# Tables wider than this are almost always false positives from pdfplumber
# detecting a PDF form's bordered field boxes as one giant table, rather
# than an actual data table. Real tables in these documents (comparison
# tables, roadmap timelines) are rarely wider than this.
MAX_TABLE_COLUMNS = 8

# If more than this fraction of cells in a detected table are empty, it's
# very likely a form layout rather than real tabular data.
MAX_EMPTY_CELL_RATIO = 0.6


def _is_low_quality_table(table: list) -> bool:
    """
    Heuristic filter for pdfplumber false positives. PDF forms with lots of
    bordered boxes (e.g. government registration forms) often get detected
    as one huge, mostly-empty table — that's a form layout, not tabular
    data. Including it as a chunk pollutes retrieval with noise, and can
    also produce a table too wide to render legibly (or even without
    crashing) in a PDF report.
    """
    if not table or not table[0]:
        return True

    num_cols = len(table[0])
    if num_cols > MAX_TABLE_COLUMNS:
        return True

    total_cells = sum(len(row) for row in table)
    empty_cells = sum(1 for row in table for cell in row if not cell or not cell.strip())
    if total_cells > 0 and (empty_cells / total_cells) > MAX_EMPTY_CELL_RATIO:
        return True

    return False


def _table_to_markdown(table: list) -> str:
    """Convert a raw pdfplumber table (list of rows) into a Markdown table."""
    if not table or not table[0]:
        return ""
    cleaned = [[cell if cell is not None else "" for cell in row] for row in table]
    header = cleaned[0]
    rows = cleaned[1:]

    md_lines = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join(["---"] * len(header)) + " |",
    ]
    for row in rows:
        if len(row) < len(header):
            row = row + [""] * (len(header) - len(row))
        else:
            row = row[:len(header)]
        md_lines.append("| " + " | ".join(row) + " |")
    return "\n".join(md_lines)


def extract_tables_from_pdf(filepath: str, source_label: str) -> list:
    """
    Extract tables from a PDF and return them as LangChain Document objects,
    ready to hand straight to Chroma.from_documents() or
    vectorstore.add_documents() alongside text chunks.

    Each Document is tagged metadata={"chunk_type": "table", ...} so
    downstream code (retriever.py, nodes.py) can tell it apart from a
    regular text chunk and treat it differently at answer time.

    Tables that look like pdfplumber misdetections (form grids, mostly
    empty, unreasonably wide) are skipped — see _is_low_quality_table().
    """
    table_docs = []
    with pdfplumber.open(filepath) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            for t_idx, raw_table in enumerate(page.extract_tables()):
                if _is_low_quality_table(raw_table):
                    continue

                md_table = _table_to_markdown(raw_table)
                if not md_table:
                    continue
                caption = f"Table from {source_label}, page {page_num}."
                content = f"{caption}\n\n{md_table}"
                table_docs.append(Document(
                    page_content=content,
                    metadata={
                        "source": source_label,
                        "chunk_type": "table",
                        "page": page_num,
                        "table_index": t_idx,
                    }
                ))
    return table_docs