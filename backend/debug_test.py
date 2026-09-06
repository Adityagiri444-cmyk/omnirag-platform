from nodes import node_planner
from retriever import get_relevant_documents, hierarchical_retrieve

state = {"query": "What is RAG?"}
state.update(node_planner(state))
print("Rewritten search query:", state["search_query"])
print()
print("Relevant docs for rewritten query:", get_relevant_documents(state["search_query"]))
print()
chunks = hierarchical_retrieve(state["search_query"])
for i, c in enumerate(chunks, 1):
    print(f"--- {i} ---")
    print(c[:200])
    print()