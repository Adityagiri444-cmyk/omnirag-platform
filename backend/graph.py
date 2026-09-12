from typing import TypedDict, Optional
from langgraph.graph import StateGraph, END
from nodes import (
    node_coordinator, route_after_coordinator,
    node_retrieval, node_summarizer, node_evaluator, route_after_evaluator,
    node_multi_hop, node_synthesize,
    node_compute
)

class GraphState(TypedDict):
    query: str
    history_text: Optional[str]
    resolved_query: Optional[str]
    question_type: Optional[str]
    search_query: Optional[str]
    retrieved_docs: Optional[list]
    final_answer: Optional[str]
    evaluation: Optional[str]
    attempts: int
    sub_questions: Optional[list]
    sub_answers: Optional[list]
    compute_code: Optional[str]

builder = StateGraph(GraphState)

builder.add_node("coordinator", node_coordinator)
builder.add_node("retrieval", node_retrieval)
builder.add_node("summarizer", node_summarizer)
builder.add_node("evaluator", node_evaluator)
builder.add_node("multi_hop", node_multi_hop)
builder.add_node("synthesize", node_synthesize)
builder.add_node("compute", node_compute)

builder.set_entry_point("coordinator")

builder.add_conditional_edges(
    "coordinator",
    route_after_coordinator,
    {
        "simple": "retrieval",
        "complex": "multi_hop",
        "ambiguous": END,
        "compute": "compute"
    }
)

builder.add_edge("retrieval", "summarizer")
builder.add_edge("summarizer", "evaluator")
builder.add_conditional_edges(
    "evaluator",
    route_after_evaluator,
    {
        "retry": "retrieval",
        "done": END
    }
)

builder.add_edge("multi_hop", "synthesize")
builder.add_edge("synthesize", END)

builder.add_edge("compute", END)

graph = builder.compile()

if __name__ == "__main__":
    print("=== Turn 1 ===")
    result1 = graph.invoke({"query": "What is RAG?", "attempts": 0, "history_text": "(no prior conversation)"})
    print(result1.get("final_answer"))

    print("\n=== Turn 2 (follow-up) ===")
    history = f"Q: What is RAG?\nA: {result1.get('final_answer')}"
    result2 = graph.invoke({"query": "explain that in more detail", "attempts": 0, "history_text": history})
    print("Resolved:", result2.get("resolved_query"))
    print(result2.get("final_answer"))