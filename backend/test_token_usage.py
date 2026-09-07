from graph import graph
from token_tracker import TokenUsageTracker

def run_with_tracking(question: str):
    tracker = TokenUsageTracker()
    state = {"query": question, "attempts": 0}
    config = {"callbacks": [tracker]}

    result = graph.invoke(state, config=config)
    usage = tracker.summary()

    print(f"Question: {question}")
    print(f"  LLM calls: {usage['llm_calls']}")
    print(f"  Prompt tokens: {usage['prompt_tokens']}")
    print(f"  Completion tokens: {usage['completion_tokens']}")
    print(f"  Total tokens: {usage['total_tokens']}")
    print()
    return usage

if __name__ == "__main__":
    run_with_tracking("What is RAG?")
    run_with_tracking("Compare SQL comparison operators with logical operators and explain when you would use BETWEEN vs a nested subquery")
    run_with_tracking("tell me about it")