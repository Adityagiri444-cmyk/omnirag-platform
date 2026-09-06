from retriever import list_all_indexed_documents, add_summary_to_index
from nodes import summarize_document

def build_summary_index():
    filenames = list_all_indexed_documents()
    print(f"Found {len(filenames)} documents to summarize")

    for filename in filenames:
        print(f"Summarizing: {filename}")
        summary = summarize_document(filename)
        add_summary_to_index(filename, summary)
        print(f"  -> {summary[:100]}...")

    print("Done. Summary index built.")

if __name__ == "__main__":
    build_summary_index()