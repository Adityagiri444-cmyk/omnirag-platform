from nodes import node_decompose, node_multi_hop, node_synthesize

state = {"query": "Compare SQL comparison operators with logical operators and explain when you would use BETWEEN vs a nested subquery"}
state.update(node_decompose(state))
print("Sub-questions:", state["sub_questions"])

state.update(node_multi_hop(state))
state.update(node_synthesize(state))
print("\nFinal Answer:\n", state["final_answer"])