from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain_core.documents import Document

CACHE_CHROMA_DIR = "chroma_query_cache_db"

embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
cache_vectorstore = Chroma(persist_directory=CACHE_CHROMA_DIR, embedding_function=embeddings)

# Distance threshold below which two questions are considered "the same" -
# calibrated empirically; lower = stricter match required
SIMILARITY_DISTANCE_THRESHOLD = 0.15

def add_to_cache(question: str, answer: str, question_type: str, evaluation: str):
    # Only cache genuinely resolved answers, not clarification requests or
    # ambiguous non-answers, since those aren't reusable for a different asker
    if question_type == "AMBIGUOUS":
        return
    cache_vectorstore.add_documents([
        Document(
            page_content=question,
            metadata={"answer": answer, "question_type": question_type, "evaluation": evaluation}
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
        return {
            "answer": doc.metadata.get("answer"),
            "question_type": doc.metadata.get("question_type"),
            "evaluation": doc.metadata.get("evaluation"),
            "matched_question": doc.page_content,
            "distance": distance,
        }
    return None