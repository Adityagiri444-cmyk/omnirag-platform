from nodes import generate_research_report

result = generate_research_report("SQL query operators and their use cases")
print("Sources used:", result["sources_used"])
print()
print(result["report"])