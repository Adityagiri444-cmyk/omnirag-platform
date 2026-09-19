from retriever import list_all_indexed_documents, add_summary_to_index, summary_vectorstore
from nodes import summarize_document

def prune_orphaned_summaries(current_filenames):
    """
    Remove summary entries for documents that no longer exist in the main
    chunk-level index (chroma_db) - e.g. after a document was deleted, or
    after build_retriever.py rebuilt chroma_db from a different set of
    uploaded files than last time. Without this, an orphaned summary can
    still win hierarchical_retrieve()'s document-selection step for a query
    about a totally unrelated (or nonexistent) document, since it may be the
    closest - or only - match available in chroma_summaries_db.
    """
    existing = summary_vectorstore._collection.get()
    orphans = set()
    for metadata in existing.get("metadatas", []):
        source = metadata.get("source") if metadata else None
        if source and source not in current_filenames:
            orphans.add(source)

    for filename in orphans:
        print(f"Removing orphaned summary for: {filename}")
        summary_vectorstore._collection.delete(where={"source": filename})

def build_summary_index():
    filenames = list_all_indexed_documents()
    print(f"Found {len(filenames)} documents to summarize")

    prune_orphaned_summaries(filenames)

    for filename in filenames:
        print(f"Summarizing: {filename}")
        summary = summarize_document(filename)
        add_summary_to_index(filename, summary)
        print(f"  -> {summary[:100]}...")

    print("Done. Summary index built.")

if __name__ == "__main__":
    build_summary_index()