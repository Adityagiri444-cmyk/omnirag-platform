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

# Simple path: retrieval -> summarizer -> evaluator, with retry
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

# Complex path: multi-hop -> synthesize
builder.add_edge("multi_hop", "synthesize")
builder.add_edge("synthesize", END)

# Compute path: straight to END after execution
builder.add_edge("compute", END)

graph = builder.compile()

if __name__ == "__main__":
    print("=== SIMPLE ===")
    result = graph.invoke({"query": "What is RAG?", "attempts": 0})
    print(result.get("final_answer"))

    print("\n=== COMPLEX ===")
    result = graph.invoke({
        "query": "Compare SQL comparison operators with logical operators and explain when you would use BETWEEN vs a nested subquery",
        "attempts": 0
    })
    print(result.get("final_answer"))

    print("\n=== AMBIGUOUS ===")
    result = graph.invoke({"query": "tell me about it", "attempts": 0})
    print(result.get("final_answer"))

    print("\n=== COMPUTE ===")
    result = graph.invoke({"query": "How many documents do I have?", "attempts": 0})
    print(result.get("final_answer"))