from pypdf import PdfReader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain_core.documents import Document

CHROMA_DIR = "chroma_db"
SUMMARY_CHROMA_DIR = "chroma_summaries_db"

embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
vectorstore = Chroma(persist_directory=CHROMA_DIR, embedding_function=embeddings)
summary_vectorstore = Chroma(persist_directory=SUMMARY_CHROMA_DIR, embedding_function=embeddings)

def retrieve(query: str, k: int = 3) -> list[str]:
    results = vectorstore.similarity_search(query, k=k)
    return [doc.page_content for doc in results]

def add_document_to_index(filepath: str, filename: str):
    """Extract, chunk, and embed a single PDF into the existing Chroma index."""
    reader = PdfReader(filepath)
    text = ""
    for page in reader.pages:
        text += page.extract_text() or ""

    doc = Document(page_content=text, metadata={"source": filename})
    splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    chunks = splitter.split_documents([doc])

    vectorstore.add_documents(chunks)
    return len(chunks)

def get_document_text(filename: str) -> str:
    """Fetch all indexed chunks for a specific document and join them back together."""
    results = vectorstore._collection.get(where={"source": filename})
    documents = results.get("documents", [])
    return "\n\n".join(documents)

def add_summary_to_index(filename: str, summary: str):
    """Store a document-level summary in the top-level (hierarchical) summary index."""
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

def hierarchical_retrieve(query: str, k_docs: int = 2, k_chunks: int = 3) -> list[str]:
    """
    RAPTOR-inspired two-stage retrieval:
    1. Search document-level summaries to find the most relevant document(s).
    2. Search only within those documents' chunks for precise passages.
    Falls back to flat retrieval if no summaries are indexed yet.
    """
    top_docs = get_relevant_documents(query, k=k_docs)
    if not top_docs:
        return retrieve(query, k=k_chunks)

    results = vectorstore.similarity_search(
        query, k=k_chunks, filter={"source": {"$in": top_docs}}
    )
    return [doc.page_content for doc in results]

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
        print(f"--- Result {i} ---")
        print(chunk)
        print()