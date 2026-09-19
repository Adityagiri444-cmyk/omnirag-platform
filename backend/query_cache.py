import json
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain_core.documents import Document

CACHE_CHROMA_DIR = "chroma_query_cache_db"

embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
cache_vectorstore = Chroma(persist_directory=CACHE_CHROMA_DIR, embedding_function=embeddings)

# Distance threshold below which two questions are considered "the same" -
# calibrated empirically; lower = stricter match required
SIMILARITY_DISTANCE_THRESHOLD = 0.15

def add_to_cache(question: str, answer: str, question_type: str, evaluation: str,
                  retrieved_docs: list = None, search_query: str = None):
    """
    Cache a resolved answer for reuse by similar future questions.

    retrieved_docs is JSON-serialized before storing, since Chroma metadata
    values must be scalars (str/int/float/bool), not lists of dicts. Without
    this, a cache hit had nothing to give back for the PDF report's
    "Retrieved Context" section — it always showed "No context retrieved."
    even when the original (uncached) answer had real context behind it.
    """
    # Only cache genuinely resolved answers, not clarification requests or
    # ambiguous non-answers, since those aren't reusable for a different asker
    if question_type == "AMBIGUOUS":
        return
    cache_vectorstore.add_documents([
        Document(
            page_content=question,
            metadata={
                "answer": answer,
                "question_type": question_type,
                "evaluation": evaluation,
                "retrieved_docs": json.dumps(retrieved_docs or []),
                "search_query": search_query or "",
            }
        )
    ])

def get_cached_answer(question: str):
    """
    Returns a dict with the cached answer/metadata if a sufficiently similar
    question exists in the cache, otherwise None.
    """
    results = cache_vectorstore.similarity_search_with_score(question, k=1)
    if not results:
        return None
    doc, distance = results[0]
    if distance <= SIMILARITY_DISTANCE_THRESHOLD:
        raw_docs = doc.metadata.get("retrieved_docs")
        try:
            retrieved_docs = json.loads(raw_docs) if raw_docs else []
        except (TypeError, json.JSONDecodeError):
            # Entries cached before this field existed won't parse - fall
            # back to empty rather than crashing on an old cache entry.
            retrieved_docs = []

        return {
            "answer": doc.metadata.get("answer"),
            "question_type": doc.metadata.get("question_type"),
            "evaluation": doc.metadata.get("evaluation"),
            "matched_question": doc.page_content,
            "distance": distance,
            "retrieved_docs": retrieved_docs,
            "search_query": doc.metadata.get("search_query") or None,
        }
    return None