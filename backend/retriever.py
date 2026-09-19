from pypdf import PdfReader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain_core.documents import Document
from table_extractor import extract_tables_from_pdf
from image_extractor import extract_images_from_pdf

CHROMA_DIR = "chroma_db"
SUMMARY_CHROMA_DIR = "chroma_summaries_db"

embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
vectorstore = Chroma(persist_directory=CHROMA_DIR, embedding_function=embeddings)
summary_vectorstore = Chroma(persist_directory=SUMMARY_CHROMA_DIR, embedding_function=embeddings)

def _doc_to_dict(doc: Document) -> dict:
    """Normalize a retrieved Chroma Document into a plain dict, carrying
    chunk_type along so callers (nodes.py) can tell table chunks from
    regular text chunks instead of getting back a bare string."""
    return {
        "content": doc.page_content,
        "chunk_type": doc.metadata.get("chunk_type", "text"),
        "source": doc.metadata.get("source"),
    }

def retrieve(query: str, k: int = 3) -> list[dict]:
    results = vectorstore.similarity_search(query, k=k)
    return [_doc_to_dict(doc) for doc in results]

def add_document_to_index(filepath: str, filename: str):
    """Extract, chunk, and embed a single PDF into the existing Chroma index.
    Handles body text, tables, and images, same as the bulk build_retriever.py
    path, so a document added later behaves identically to one added at build time.

    Note: this does NOT generate a document-level summary itself - the
    /documents/upload route in documents.py already calls summarize_document()
    and add_summary_to_index() right after calling this function, so doing it
    here too would silently double the LLM calls made on every single upload."""
    reader = PdfReader(filepath)
    text = ""
    for page in reader.pages:
        text += page.extract_text() or ""

    text_doc = Document(page_content=text, metadata={"source": filename, "chunk_type": "text"})
    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=150)
    text_chunks = splitter.split_documents([text_doc])

    table_docs = extract_tables_from_pdf(filepath, filename)
    image_docs = extract_images_from_pdf(filepath, filename)

    all_chunks = text_chunks + table_docs + image_docs
    vectorstore.add_documents(all_chunks)

    return len(all_chunks)

def get_document_text(filename: str) -> str:
    """Fetch all indexed chunks for a specific document and join them back together."""
    results = vectorstore._collection.get(where={"source": filename})
    documents = results.get("documents", [])
    return "\n\n".join(documents)

def add_summary_to_index(filename: str, summary: str):
    """Store a document-level summary in the top-level (hierarchical) summary
    index. Deletes any existing summary for this filename first, so
    re-summarizing (via build_summary_index.py, or on re-upload) never leaves
    a stale duplicate entry that could outrank the document's real, current
    summary during hierarchical_retrieve()'s document-selection step."""
    summary_vectorstore._collection.delete(where={"source": filename})
    summary_vectorstore.add_documents([Document(page_content=summary, metadata={"source": filename})])

def get_relevant_documents(query: str, k: int = 2) -> list[str]:
    """Search only the document-level summary index to find which document(s) are most relevant."""
    results = summary_vectorstore.similarity_search(query, k=k)
    seen = []
    for doc in results:
        source = doc.metadata.get("source")
        if source and source not in seen:
            seen.append(source)
    return seen

def hierarchical_retrieve(query: str, k_docs: int = 2, k_chunks: int = 3) -> list[dict]:
    """
    RAPTOR-inspired two-stage retrieval:
    1. Search document-level summaries to find the most relevant document(s).
    2. Search only within those documents' chunks for precise passages.
    Falls back to flat retrieval if no summaries are indexed yet, OR if the
    selected document(s) turn out to have no chunks in the current index
    (e.g. a stale/orphaned summary pointing at a document that no longer
    exists there) - otherwise a bad document match would return zero chunks
    instead of gracefully degrading to a flat search.
    """
    top_docs = get_relevant_documents(query, k=k_docs)
    if not top_docs:
        return retrieve(query, k=k_chunks)

    results = vectorstore.similarity_search(
        query, k=k_chunks, filter={"source": {"$in": top_docs}}
    )
    if not results:
        return retrieve(query, k=k_chunks)

    return [_doc_to_dict(doc) for doc in results]

def list_all_indexed_documents() -> list[str]:
    """Return the unique set of document filenames currently in the chunk-level index."""
    results = vectorstore._collection.get()
    sources = set()
    for metadata in results.get("metadatas", []):
        if metadata and metadata.get("source"):
            sources.add(metadata["source"])
    return list(sources)

def get_documents_metadata() -> list[dict]:
    """
    Return safe, non-sensitive metadata about every indexed document
    (filename, word count, character count) - used as the only data
    exposed to the sandboxed computation agent. No raw file access,
    no file paths, nothing beyond these simple counts.
    """
    metadata = []
    for filename in list_all_indexed_documents():
        text = get_document_text(filename)
        metadata.append({
            "filename": filename,
            "word_count": len(text.split()),
            "char_count": len(text),
        })
    return metadata

if __name__ == "__main__":
    test_query = "What is RAG?"
    chunks = retrieve(test_query)
    for i, chunk in enumerate(chunks, 1):
        print(f"--- Result {i} ({chunk['chunk_type']}) ---")
        print(chunk["content"])
        print()