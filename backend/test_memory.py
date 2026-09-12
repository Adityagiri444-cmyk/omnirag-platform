from nodes import node_coordinator

history = "Q: What is RAG?\nA: RAG is Retrieval-Augmented Generation, combining a retriever with a generator model."
state = {"query": "explain that in more detail", "history_text": history}
result = node_coordinator(state)
print("Resolved question:", result["resolved_query"])
print("Type:", result["question_type"])