from query_cache import add_to_cache, get_cached_answer, cache_vectorstore

add_to_cache("What is RAG?", "RAG is Retrieval-Augmented Generation.", "SIMPLE", "YES")

test_questions = [
    "What is RAG?",                          # exact duplicate
    "what is rag?",                          # case difference
    "What is RAG",                           # no question mark
    "Can you explain what RAG is?",          # paraphrase, same meaning
    "What is a Support Vector Machine?",     # different topic entirely
]

for q in test_questions:
    results = cache_vectorstore.similarity_search_with_score(q, k=1)
    distance = results[0][1] if results else None
    cached = get_cached_answer(q)
    print(f"Query: {q!r}")
    print(f"  Distance: {distance}")
    print(f"  Cache hit: {cached is not None}")
    print()