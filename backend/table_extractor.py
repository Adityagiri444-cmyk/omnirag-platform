"""
table_extractor.py
Shared table-extraction helper for OmniRAG's ingestion pipeline.
Used by both build_retriever.py (bulk index build) and retriever.py
(single-document add), so table handling is identical everywhere
instead of being duplicated and drifting apart.
"""

import pdfplumber
from langchain_core.documents import Document


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
    Extract all tables from a PDF and return them as LangChain Document
    objects, ready to hand straight to Chroma.from_documents() or
    vectorstore.add_documents() alongside text chunks.

    Each Document is tagged metadata={"chunk_type": "table", ...} so
    downstream code (retriever.py, nodes.py) can tell it apart from a
    regular text chunk and treat it differently at answer time.
    """
    table_docs = []
    with pdfplumber.open(filepath) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            for t_idx, raw_table in enumerate(page.extract_tables()):
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